"""
High-level UDP Client for receiving isiMotor telemetry, scoring, track rules, pit menu, and weather packets.
"""

import socket
import select
import threading
import time
from typing import Optional, Callable, Dict, List, Union
from .models import (
    TelemInfo,
    CompactScoring,
    FullScoringSession,
    TrackRulesSession,
    PitMenu,
    WeatherControl,
    PhysicsOptions,
    ExtendedState,
    ForceFeedback,
    Graphics,
    SystemEvent,
    RawUdpHeader,
    PitAction,
    HWControlCommand,
    WeatherControlCommand,
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
    decode_hw_control,
    decode_weather_control,
    encode_hw_control,
    encode_weather_control,
    HEADER_SIZE,
)


class IsiMotorClient:
    """
    Ultra-low latency UDP client for isiMotor / LMU telemetry and scoring.

    Usage examples:
    1. Callback-based:
        client = IsiMotorClient(port=5000)
        client.on_telemetry = lambda t: print(f"RPM: {t.engine_rpm}, Speed: {t.speed_kmh:.1f}")
        client.on_full_scoring = lambda s: print(f"Leader: {s.leaderboard[0].driver_name}")
        client.on_track_rules = lambda r: print(f"FCY: {r.is_caution_active}, SC: {r.is_safety_car_active}")
        client.on_pit_menu = lambda p: print(f"Pit Menu: {p.category_name} -> {p.choice_string}")
        client.on_weather = lambda w: print(f"Track Temp: {w.ambient_temp_c:.1f} °C, Rain: {w.origin_raining * 100:.0f}%")
        client.on_extended_state = lambda e: print(f"TC: {e.physics.traction_control_str}, Damage: {e.accumulated_impact_magnitude:.1f}")
        client.on_force_feedback = lambda f: print(f"FFB: {f.percentage:.1f}%")
        client.on_graphics = lambda g: print(f"Cam: {g.camera_type_str}")
        client.start()
        ...
        client.stop()

    2. Context Manager / Polling:
        with IsiMotorClient(port=5000) as client:
            while True:
                telem = client.get_latest_telemetry()
                rules = client.get_latest_track_rules()
                ffb = client.get_latest_force_feedback()
                if telem:
                    print(telem.gear_str, telem.speed_kmh)
                time.sleep(0.01)
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        inbound_host: str = "127.0.0.1",
        inbound_port: int = 5001,
    ):
        self.host = host
        self.port = port
        self.inbound_host = inbound_host
        self.inbound_port = inbound_port

        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._inbound_seq = 0

        # Cached latest frames
        self._latest_telemetry: Optional[TelemInfo] = None
        self._latest_scoring: Optional[CompactScoring] = None
        self._latest_full_scoring: Optional[FullScoringSession] = None
        self._latest_track_rules: Optional[TrackRulesSession] = None
        self._latest_pit_menu: Optional[PitMenu] = None
        self._latest_weather: Optional[WeatherControl] = None
        self._latest_extended_state: Optional[ExtendedState] = None
        self._latest_force_feedback: Optional[ForceFeedback] = None
        self._latest_graphics: Optional[Graphics] = None
        self._latest_system_event: Optional[SystemEvent] = None
        self._latest_hw_control: Optional[HWControlCommand] = None
        self._latest_weather_control: Optional[WeatherControlCommand] = None
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
        self.on_extended_state: Optional[Callable[[ExtendedState], None]] = None
        self.on_force_feedback: Optional[Callable[[ForceFeedback], None]] = None
        self.on_graphics: Optional[Callable[[Graphics], None]] = None
        self.on_system_event: Optional[Callable[[SystemEvent], None]] = None
        self.on_hw_control: Optional[Callable[[HWControlCommand], None]] = None
        self.on_weather_control: Optional[Callable[[WeatherControlCommand], None]] = None
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
                        ExtendedState,
                        ForceFeedback,
                        Graphics,
                        SystemEvent,
                        HWControlCommand,
                        WeatherControlCommand,
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
                                    elif isinstance(pkt, ExtendedState):
                                        self._latest_extended_state = pkt
                                    elif isinstance(pkt, ForceFeedback):
                                        self._latest_force_feedback = pkt
                                    elif isinstance(pkt, Graphics):
                                        self._latest_graphics = pkt
                                    elif isinstance(pkt, SystemEvent):
                                        self._latest_system_event = pkt
                                    elif isinstance(pkt, HWControlCommand):
                                        self._latest_hw_control = pkt
                                    elif isinstance(pkt, WeatherControlCommand):
                                        self._latest_weather_control = pkt

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
                                    isinstance(pkt, ExtendedState)
                                    and self.on_extended_state
                                ):
                                    self.on_extended_state(pkt)
                                elif (
                                    isinstance(pkt, ForceFeedback)
                                    and self.on_force_feedback
                                ):
                                    self.on_force_feedback(pkt)
                                elif (
                                    isinstance(pkt, Graphics)
                                    and self.on_graphics
                                ):
                                    self.on_graphics(pkt)
                                elif (
                                    isinstance(pkt, SystemEvent)
                                    and self.on_system_event
                                ):
                                    self.on_system_event(pkt)
                                elif (
                                    isinstance(pkt, HWControlCommand)
                                    and self.on_hw_control
                                ):
                                    self.on_hw_control(pkt)
                                elif (
                                    isinstance(pkt, WeatherControlCommand)
                                    and self.on_weather_control
                                ):
                                    self.on_weather_control(pkt)

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

    def get_latest_extended_state(self) -> Optional[ExtendedState]:
        """Returns the most recently received ExtendedState frame thread-safely."""
        with self._lock:
            return self._latest_extended_state

    def get_latest_force_feedback(self) -> Optional[ForceFeedback]:
        """Returns the most recently received ForceFeedback frame thread-safely."""
        with self._lock:
            return self._latest_force_feedback

    def get_latest_graphics(self) -> Optional[Graphics]:
        """Returns the most recently received Graphics frame thread-safely."""
        with self._lock:
            return self._latest_graphics

    def get_latest_system_event(self) -> Optional[SystemEvent]:
        """Returns the most recently received SystemEvent thread-safely."""
        with self._lock:
            return self._latest_system_event

    def get_latest_hw_control(self) -> Optional[HWControlCommand]:
        """Returns the most recently received HWControlCommand thread-safely."""
        with self._lock:
            return self._latest_hw_control

    def get_latest_weather_control(self) -> Optional[WeatherControlCommand]:
        """Returns the most recently received WeatherControlCommand thread-safely."""
        with self._lock:
            return self._latest_weather_control

    def send_hw_control(
        self,
        control_name: str,
        control_value: float = 1.0,
        duration_ms: int = 50,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> bool:
        """
        Transmits a hardware / pit menu control command (SIMP Type 100) to the game plugin.

        :param control_name: Control name (e.g. "PitMenuUp", "PitMenuSelect", "TCIncrease", "ABSDecrease").
        :param control_value: 1.0 = press/activate, 0.0 = release, or analog value.
        :param duration_ms: Pulse duration in milliseconds (default: 50ms).
        :param host: Destination IP (defaults to self.inbound_host).
        :param port: Destination inbound port (defaults to self.inbound_port).
        """
        dest_host = host or self.inbound_host
        dest_port = port or self.inbound_port

        with self._lock:
            self._inbound_seq += 1
            seq = self._inbound_seq

        packet = encode_hw_control(
            control_name=control_name,
            control_value=control_value,
            duration_ms=duration_ms,
            with_header=True,
            sequence_number=seq,
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(packet, (dest_host, dest_port))
            return True
        except Exception:
            return False
        finally:
            sock.close()

    def send_pit_action(
        self,
        action: Union[PitAction, str],
        duration_ms: int = 50,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> bool:
        """
        Convenience helper to send pit menu navigation actions (Up, Down, Prev, Next, Select).
        """
        name = action.value if isinstance(action, PitAction) else str(action)
        return self.send_hw_control(
            control_name=name,
            control_value=1.0,
            duration_ms=duration_ms,
            host=host,
            port=port,
        )

    def send_weather_override(
        self,
        ambient_temp: float = 20.0,
        track_temp: float = 25.0,
        dark_cloud: float = 0.0,
        raining: float = 0.0,
        wind_speed: float = 0.0,
        wind_direction: float = 0.0,
        min_path_wetness: float = 0.0,
        max_path_wetness: float = 0.0,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> bool:
        """
        Injects dynamic weather and ambient environmental conditions (SIMP Type 101) into the game session.

        :param ambient_temp: Ambient air temperature in °C.
        :param track_temp: Track surface temperature in °C.
        :param dark_cloud: Cloudiness / overcast fraction (0.0 to 1.0).
        :param raining: Rain intensity (0.0 to 1.0).
        :param wind_speed: Wind speed in m/s.
        :param wind_direction: Wind direction in radians.
        :param min_path_wetness: Minimum path wetness (0.0 to 1.0).
        :param max_path_wetness: Maximum off-line wetness (0.0 to 1.0).
        :param host: Destination IP (defaults to self.inbound_host).
        :param port: Destination inbound port (defaults to self.inbound_port).
        """
        dest_host = host or self.inbound_host
        dest_port = port or self.inbound_port

        with self._lock:
            self._inbound_seq += 1
            seq = self._inbound_seq

        packet = encode_weather_control(
            ambient_temp=ambient_temp,
            track_temp=track_temp,
            dark_cloud=dark_cloud,
            raining=raining,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            min_path_wetness=min_path_wetness,
            max_path_wetness=max_path_wetness,
            with_header=True,
            sequence_number=seq,
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(packet, (dest_host, dest_port))
            return True
        except Exception:
            return False
        finally:
            sock.close()

    @property
    def packet_count(self) -> int:
        with self._lock:
            return self._packet_count

    @property
    def last_packet_time(self) -> float:
        with self._lock:
            return self._last_packet_time
