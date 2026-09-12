"""
Non-blocking ZeroMQ SUB receiver, chunk reassembly and packet ingestion engine.
"""

import time

from isimotor_rawudp_client.decoder import (
    HEADER_SIZE,
    TELEMINFO_SIZE,
    decode_compact_scoring,
    decode_extended_state,
    decode_force_feedback,
    decode_full_scoring,
    decode_graphics,
    decode_header,
    decode_system_event,
    decode_telemetry,
    decode_weather,
    encode_hw_control,
    encode_weather_control,
)
from isimotor_rawudp_client.transport import ZmqPublisher, ZmqSubscriber
from isimotor_rawudp_types import (
    CompactScoring,
    ExtendedState,
    ForceFeedback,
    FullScoringSession,
    Graphics,
    HWControlCommand,
    SystemEvent,
    TelemInfo,
    WeatherControl,
    WeatherControlCommand,
)

from ..constants import (
    PKT_COMPACT_SCORING,
    PKT_EXTENDED_STATE,
    PKT_FORCE_FEEDBACK,
    PKT_FOREIGN,
    PKT_FULL_SCORING,
    PKT_GRAPHICS,
    PKT_HW_CONTROL,
    PKT_RAW_TELEMETRY,
    PKT_SYSTEM_EVENT,
    PKT_WEATHER,
    PKT_WEATHER_CONTROL,
)
from .stats import PacketStats


class TelemetryEngine:
    """Non-blocking ZeroMQ SUB receiver, stream demultiplexer and packet decoder."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        self.host = host
        self.port = port  # Base port; ZmqSubscriber connects one SUB per packet type on port + packet_type.
        self.start_time = time.time()
        self.total_packets = 0
        self.total_bytes = 0
        self.running = False
        self._subscriber: ZmqSubscriber | None = None
        self._publisher = ZmqPublisher()

        self.stats: dict[str, PacketStats] = {
            PKT_RAW_TELEMETRY: PacketStats(PKT_RAW_TELEMETRY, "Sliced/Raw SIMP", "1888/1904 B"),
            PKT_COMPACT_SCORING: PacketStats(PKT_COMPACT_SCORING, "Binary SIMP", "160 B"),
            PKT_FULL_SCORING: PacketStats(PKT_FULL_SCORING, "Sliced SIMP", "Multi-KB"),
            PKT_WEATHER: PacketStats(PKT_WEATHER, "Binary SIMP", "108 B"),
            PKT_EXTENDED_STATE: PacketStats(PKT_EXTENDED_STATE, "Binary SIMP", "68 B"),
            PKT_FORCE_FEEDBACK: PacketStats(PKT_FORCE_FEEDBACK, "Binary SIMP", "8 B"),
            PKT_GRAPHICS: PacketStats(PKT_GRAPHICS, "Binary SIMP", "128 B"),
            PKT_SYSTEM_EVENT: PacketStats(PKT_SYSTEM_EVENT, "Binary SIMP", "2 B"),
            PKT_HW_CONTROL: PacketStats(PKT_HW_CONTROL, "Binary SIMP", "44 B"),
            PKT_WEATHER_CONTROL: PacketStats(PKT_WEATHER_CONTROL, "Binary SIMP", "64 B"),
            PKT_FOREIGN: PacketStats(PKT_FOREIGN, "Raw/Other", "Variable"),
        }

        self.latest_telemetry: TelemInfo | None = None
        self.latest_scoring: CompactScoring | None = None
        self.latest_full_scoring: FullScoringSession | None = None
        self.latest_weather: WeatherControl | None = None
        self.latest_extended_state: ExtendedState | None = None
        self.latest_force_feedback: ForceFeedback | None = None
        self.latest_graphics: Graphics | None = None
        self.latest_event: SystemEvent | None = None
        self.latest_event_time: float = 0.0
        self.latest_hw_control: HWControlCommand | None = None
        self.latest_weather_control: WeatherControlCommand | None = None
        self.inbound_target_host: str = "127.0.0.1"
        self.inbound_target_port: int = 5101
        self.last_inbound_cmd_sent: str = "None"
        self.last_inbound_cmd_time: float = 0.0
        self.reassembly_buffers: dict[tuple, dict] = {}
        self.last_cleanup_time: float = 0.0
        self._pending: list[tuple[int, bytes]] = []

    def send_hw_control(self, control_name: str, control_value: float = 1.0, duration_ms: int = 50) -> bool:
        """Publishes an inbound Type 100 control packet."""
        pkt = encode_hw_control(
            control_name=control_name,
            control_value=control_value,
            duration_ms=duration_ms,
        )
        ok = self._publisher.send_raw(pkt, self.inbound_target_host, self.inbound_target_port)
        if ok:
            self.last_inbound_cmd_sent = f"{control_name} (val={control_value}, dur={duration_ms}ms)"
        else:
            self.last_inbound_cmd_sent = "Error: publish failed"
        self.last_inbound_cmd_time = time.time()
        return ok

    def send_weather_override(self, ambient_temp: float = 20.0, raining: float = 0.0) -> bool:
        """Publishes an inbound Type 101 weather control packet."""
        pkt = encode_weather_control(
            ambient_temp=ambient_temp,
            track_temp=ambient_temp + 5.0,
            dark_cloud=min(1.0, raining * 1.2),
            raining=raining,
            wind_speed=2.5,
            wind_direction=0.0,
            min_path_wetness=raining * 0.8,
            max_path_wetness=raining,
        )
        ok = self._publisher.send_raw(pkt, self.inbound_target_host, self.inbound_target_port)
        if ok:
            self.last_inbound_cmd_sent = f"WeatherOverride (Temp={ambient_temp:.1f}°C, Rain={raining * 100:.0f}%)"
        else:
            self.last_inbound_cmd_sent = "Error: publish failed"
        self.last_inbound_cmd_time = time.time()
        return ok

    def start(self) -> None:
        """Starts the background ZeroMQ SUB receiver (connects to the plugin's telemetry PUB)."""
        self._pending = []
        self._subscriber = ZmqSubscriber(host=self.host, port=self.port)
        self._subscriber.start(lambda packet_type, data, _timestamp: self._pending.append((packet_type, data)))
        self.running = True

    def stop(self) -> None:
        """Stops the background receiver and closes the publisher socket."""
        self.running = False
        if self._subscriber:
            self._subscriber.stop()
            self._subscriber = None
        self._publisher.close()

    def poll(self) -> None:
        """Drains pending packets received by the background subscriber thread."""
        if not self.running:
            return

        pending, self._pending = self._pending, []
        for packet_type, data in pending:
            self._process_packet(packet_type, data)

    def _process_packet(self, packet_type: int, data: bytes) -> None:
        """Decodes an incoming binary packet and dispatches to models and stats."""
        now = time.time()
        size = len(data)
        self.total_packets += 1
        self.total_bytes += size

        # Cleanup stale multipart frame fragments
        if now - self.last_cleanup_time > 1.0:
            self.last_cleanup_time = now
            stale = [k for k, v in self.reassembly_buffers.items() if now - v.get("timestamp", 0) > 1.0]
            for k in stale:
                del self.reassembly_buffers[k]

        pkt_type = PKT_FOREIGN

        # SystemEvent (3) and ForceFeedback (9) are header-less FlatBuffers,
        # each on its own port: the packet type is known from the socket the
        # message arrived on, so decode them directly (no SIMP header at all).
        if packet_type == 3:
            pkt_type = PKT_SYSTEM_EVENT
            ev = decode_system_event(data)
            if ev:
                self.latest_event = ev
                self.latest_event_time = now
        elif packet_type == 9:
            pkt_type = PKT_FORCE_FEEDBACK
            ffb = decode_force_feedback(data)
            if ffb:
                self.latest_force_feedback = ffb
        # 1. Standardized 24-byte Header (remaining legacy packet types)
        elif data.startswith(b"SIMP") and size >= HEADER_SIZE and data[4] == 1:
            hdr = decode_header(data)
            if hdr:
                payload = data[HEADER_SIZE : HEADER_SIZE + hdr.payload_size]
                if hdr.packet_type == 1:
                    pkt_type = PKT_RAW_TELEMETRY
                    if hdr.total_chunks == 1:
                        telem = decode_telemetry(payload)
                        if telem:
                            self.latest_telemetry = telem
                    else:
                        key = (hdr.packet_type, hdr.sequence_number)
                        if key not in self.reassembly_buffers:
                            self.reassembly_buffers[key] = {
                                "total_chunks": hdr.total_chunks,
                                "chunks": {},
                                "timestamp": now,
                            }
                        buf = self.reassembly_buffers[key]
                        buf["chunks"][hdr.chunk_index] = payload
                        if len(buf["chunks"]) == buf["total_chunks"]:
                            ordered = [buf["chunks"][i] for i in range(buf["total_chunks"]) if i in buf["chunks"]]
                            del self.reassembly_buffers[key]
                            telem = decode_telemetry(b"".join(ordered))
                            if telem:
                                self.latest_telemetry = telem
                elif hdr.packet_type == 2:
                    pkt_type = PKT_COMPACT_SCORING
                    scoring = decode_compact_scoring(payload)
                    if scoring:
                        self.latest_scoring = scoring
                elif hdr.packet_type == 4:
                    pkt_type = PKT_FULL_SCORING
                    if hdr.total_chunks == 1:
                        fs = decode_full_scoring(payload)
                        if fs:
                            self.latest_full_scoring = fs
                            self.stats[PKT_FULL_SCORING].record_logical(now)
                    else:
                        key = (hdr.packet_type, hdr.sequence_number)
                        if key not in self.reassembly_buffers:
                            self.reassembly_buffers[key] = {
                                "total_chunks": hdr.total_chunks,
                                "chunks": {},
                                "timestamp": now,
                            }
                        buf = self.reassembly_buffers[key]
                        buf["chunks"][hdr.chunk_index] = payload
                        if len(buf["chunks"]) == buf["total_chunks"]:
                            ordered = [buf["chunks"][i] for i in range(buf["total_chunks"]) if i in buf["chunks"]]
                            del self.reassembly_buffers[key]
                            fs = decode_full_scoring(b"".join(ordered))
                            if fs:
                                self.latest_full_scoring = fs
                                self.stats[PKT_FULL_SCORING].record_logical(now)
                elif hdr.packet_type == 7:
                    pkt_type = PKT_WEATHER
                    w = decode_weather(payload)
                    if w:
                        self.latest_weather = w
                elif hdr.packet_type == 8:
                    pkt_type = PKT_EXTENDED_STATE
                    ext = decode_extended_state(payload)
                    if ext:
                        self.latest_extended_state = ext
                elif hdr.packet_type == 10:
                    pkt_type = PKT_GRAPHICS
                    gfx = decode_graphics(payload)
                    if gfx:
                        self.latest_graphics = gfx
                elif hdr.packet_type == 100:
                    pkt_type = PKT_HW_CONTROL
                elif hdr.packet_type == 101:
                    pkt_type = PKT_WEATHER_CONTROL
        elif size == TELEMINFO_SIZE or size == 1904 or size == 2024:
            telem = decode_telemetry(data)
            if telem:
                pkt_type = PKT_RAW_TELEMETRY
                self.latest_telemetry = telem

        self.stats[pkt_type].record(size, now)

    def reset_stats(self) -> None:
        """Resets all throughput and packet counters."""
        self.total_packets = 0
        self.total_bytes = 0
        self.start_time = time.time()
        for s in self.stats.values():
            s.reset()
