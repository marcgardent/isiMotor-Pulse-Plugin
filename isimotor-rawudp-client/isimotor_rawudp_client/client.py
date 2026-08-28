"""
High-level UDP Client for receiving isiMotor telemetry, scoring, track rules, pit menu, and weather packets.
"""

import socket
import select
import threading
import time
from typing import Optional, Callable, Dict, List, Union
from .models import (
    RawUdpHeader,
    TelemInfo,
    CompactScoring,
    FullScoringSession,
    TrackRulesSession,
    PitMenu,
    WeatherControl,
    SystemEvent,
)
from .decoder import (
    decode_header,
    decode_packet,
    decode_telemetry,
    decode_compact_scoring,
    decode_full_scoring,
    decode_track_rules,
    decode_pit_menu,
    decode_weather,
    decode_system_event,
    HEADER_SIZE,
)


class IsiMotorClient:
    """
    Thread-safe UDP Client for isiMotor-RawUDP-Plugin.

    Usage Examples:

    1. Callback-based:
        client = IsiMotorClient(port=5000)
        client.on_telemetry = lambda t: print(f"RPM: {t.engine_rpm}, Speed: {t.speed_kmh:.1f}")
        client.on_full_scoring = lambda s: print(f"Leader: {s.leaderboard[0].driver_name}")
        client.on_track_rules = lambda r: print(f"FCY: {r.is_caution_active}, SC: {r.is_safety_car_active}")
        client.on_pit_menu = lambda p: print(f"Pit Menu: {p.category_name} -> {p.choice_string}")
        client.on_weather = lambda w: print(f"Track Temp: {w.ambient_temp_c:.1f} °C, Rain: {w.origin_raining * 100:.0f}%")
        client.start()
        ...
        client.stop()

    2. Context Manager / Polling:
        with IsiMotorClient(port=5000) as client:
            while True:
                telem = client.get_latest_telemetry()
                rules = client.get_latest_track_rules()
                if telem:
                    print(telem.gear_str, telem.speed_kmh)
                time.sleep(0.01)
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        self.host = host
        self.port = port

        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Cached latest frames
        self._latest_telemetry: Optional[TelemInfo] = None
        self._latest_scoring: Optional[CompactScoring] = None
        self._latest_full_scoring: Optional[FullScoringSession] = None
        self._latest_track_rules: Optional[TrackRulesSession] = None
        self._latest_pit_menu: Optional[PitMenu] = None
        self._latest_weather: Optional[WeatherControl] = None
        self._latest_system_event: Optional[SystemEvent] = None
        self._last_packet_time: float = 0.0
        self._packet_count: int = 0

        # Chunk reassembly buffer: (packet_type, sequence_number) -> dict
        self._reassembly_buffers: Dict[tuple, dict] = {}
        self._last_reassembly_cleanup: float = 0.0

        # Callbacks
        self.on_telemetry: Optional[Callable[[TelemInfo], None]] = None
        self.on_scoring: Optional[Callable[[CompactScoring], None]] = None
        self.on_full_scoring: Optional[Callable[[FullScoringSession], None]] = None
        self.on_track_rules: Optional[Callable[[TrackRulesSession], None]] = None
        self.on_pit_menu: Optional[Callable[[PitMenu], None]] = None
        self.on_weather: Optional[Callable[[WeatherControl], None]] = None
        self.on_system_event: Optional[Callable[[SystemEvent], None]] = None
        self.on_packet: Optional[
            Callable[
                [
                    Union[
                        TelemInfo,
                        CompactScoring,
                        FullScoringSession,
                        TrackRulesSession,
                        PitMenu,
                        WeatherControl,
                        SystemEvent,
                    ]
                ],
                None,
            ]
        ] = None

    def __enter__(self) -> "IsiMotorClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def start(self) -> "IsiMotorClient":
        """Starts the background receiver thread."""
        if self._running:
            return self

        self._running = True
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        self._socket.bind((self.host, self.port))

        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="IsiMotorUdpReceiver"
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stops the background receiver thread and closes socket."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def _cleanup_old_reassemblies(self, now: float) -> None:
        """Prunes incomplete multipart frames older than 1.0 second."""
        if now - self._last_reassembly_cleanup < 0.5:
            return
        self._last_reassembly_cleanup = now
        stale_keys = [
            k
            for k, v in self._reassembly_buffers.items()
            if now - v.get("timestamp", 0) > 1.0
        ]
        for k in stale_keys:
            del self._reassembly_buffers[k]

    def _process_chunk(
        self, data: bytes, now: float
    ) -> Optional[Union[FullScoringSession, TrackRulesSession]]:
        """Handles sliced multipart packet reassembly."""
        if len(data) < HEADER_SIZE:
            return None

        hdr = decode_header(data)
        if not hdr:
            return None

        payload = data[HEADER_SIZE : HEADER_SIZE + hdr.payload_size]

        if hdr.total_chunks == 1:
            if hdr.packet_type == 4:
                return decode_full_scoring(payload)
            elif hdr.packet_type == 5:
                return decode_track_rules(payload)
            return None

        key = (hdr.packet_type, hdr.sequence_number)
        if key not in self._reassembly_buffers:
            self._reassembly_buffers[key] = {
                "total_chunks": hdr.total_chunks,
                "chunks": {},
                "timestamp": now,
            }

        buf = self._reassembly_buffers[key]
        buf["chunks"][hdr.chunk_index] = payload

        if len(buf["chunks"]) == buf["total_chunks"]:
            # All slices received in full
            ordered_slices = [
                buf["chunks"][i]
                for i in range(buf["total_chunks"])
                if i in buf["chunks"]
            ]
            del self._reassembly_buffers[key]
            assembled_payload = b"".join(ordered_slices)

            if hdr.packet_type == 4:
                return decode_full_scoring(assembled_payload)
            elif hdr.packet_type == 5:
                return decode_track_rules(assembled_payload)

        return None

    def _listen_loop(self) -> None:
        """Internal ultra-low latency receive loop."""
        while self._running:
            if not self._socket:
                time.sleep(0.005)
                continue

            try:
                r, _, _ = select.select([self._socket], [], [], 0.01)
                if r:
                    while self._running:
                        try:
                            data, _ = self._socket.recvfrom(65535)
                            now = time.time()
                            self._cleanup_old_reassemblies(now)

                            # Handle sliced / chunked packets
                            pkt = None
                            if (
                                data.startswith(b"SIMP")
                                and len(data) >= HEADER_SIZE
                                and data[4] == 1
                            ):
                                hdr = decode_header(data)
                                if hdr and hdr.total_chunks > 1:
                                    pkt = self._process_chunk(data, now)
                                else:
                                    pkt = decode_packet(data)
                            else:
                                pkt = decode_packet(data)

                            if pkt is not None:
                                with self._lock:
                                    self._last_packet_time = now
                                    self._packet_count += 1

                                    if isinstance(pkt, TelemInfo):
                                        self._latest_telemetry = pkt
                                    elif isinstance(pkt, CompactScoring):
                                        self._latest_scoring = pkt
                                    elif isinstance(pkt, FullScoringSession):
                                        self._latest_full_scoring = pkt
                                    elif isinstance(pkt, TrackRulesSession):
                                        self._latest_track_rules = pkt
                                    elif isinstance(pkt, PitMenu):
                                        self._latest_pit_menu = pkt
                                    elif isinstance(pkt, WeatherControl):
                                        self._latest_weather = pkt
                                    elif isinstance(pkt, SystemEvent):
                                        self._latest_system_event = pkt

                                # Invoke callbacks outside lock
                                if self.on_packet:
                                    self.on_packet(pkt)

                                if (
                                    isinstance(pkt, TelemInfo)
                                    and self.on_telemetry
                                ):
                                    self.on_telemetry(pkt)
                                elif (
                                    isinstance(pkt, CompactScoring)
                                    and self.on_scoring
                                ):
                                    self.on_scoring(pkt)
                                elif (
                                    isinstance(pkt, FullScoringSession)
                                    and self.on_full_scoring
                                ):
                                    self.on_full_scoring(pkt)
                                elif (
                                    isinstance(pkt, TrackRulesSession)
                                    and self.on_track_rules
                                ):
                                    self.on_track_rules(pkt)
                                elif (
                                    isinstance(pkt, PitMenu)
                                    and self.on_pit_menu
                                ):
                                    self.on_pit_menu(pkt)
                                elif (
                                    isinstance(pkt, WeatherControl)
                                    and self.on_weather
                                ):
                                    self.on_weather(pkt)
                                elif (
                                    isinstance(pkt, SystemEvent)
                                    and self.on_system_event
                                ):
                                    self.on_system_event(pkt)

                        except (BlockingIOError, socket.error):
                            break
            except Exception:
                if not self._running:
                    break

    def get_latest_telemetry(self) -> Optional[TelemInfo]:
        """Returns the most recently received TelemInfo frame thread-safely."""
        with self._lock:
            return self._latest_telemetry

    def get_latest_scoring(self) -> Optional[CompactScoring]:
        """Returns the most recently received CompactScoring frame thread-safely."""
        with self._lock:
            return self._latest_scoring

    def get_latest_full_scoring(self) -> Optional[FullScoringSession]:
        """Returns the most recently received FullScoringSession frame thread-safely."""
        with self._lock:
            return self._latest_full_scoring

    def get_latest_track_rules(self) -> Optional[TrackRulesSession]:
        """Returns the most recently received TrackRulesSession frame thread-safely."""
        with self._lock:
            return self._latest_track_rules

    def get_latest_pit_menu(self) -> Optional[PitMenu]:
        """Returns the most recently received PitMenu frame thread-safely."""
        with self._lock:
            return self._latest_pit_menu

    def get_latest_weather(self) -> Optional[WeatherControl]:
        """Returns the most recently received WeatherControl frame thread-safely."""
        with self._lock:
            return self._latest_weather

    def get_latest_system_event(self) -> Optional[SystemEvent]:
        """Returns the most recently received SystemEvent thread-safely."""
        with self._lock:
            return self._latest_system_event

    @property
    def packet_count(self) -> int:
        with self._lock:
            return self._packet_count

    @property
    def last_packet_time(self) -> float:
        with self._lock:
            return self._last_packet_time
