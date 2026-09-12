"""
High-level ZeroMQ Client for receiving isiMotor telemetry, scoring, track rules, pit menu, and weather packets.

Architectural Design:
- SOLID & SRP: Single-responsibility decoupled sub-components (Transport, Codec, Reassembly, StateStore, EventDispatcher).
- SLAP: High-level methods orchestrating workflow at a uniform abstraction level.
- OCP: Extensible packet decoder registry and event subscription bus.
"""

from collections.abc import Callable
from typing import Any

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

from .decoder.events import decode_system_event
from .decoder.feedback import decode_force_feedback
from .decoder.graphics import decode_graphics
from .decoder.packet_decoder import AnyPacket, PacketDecoderRegistry
from .decoder.physics import decode_extended_state
from .decoder.scoring import decode_compact_scoring
from .decoder.weather import decode_weather
from .dispatcher import EventDispatcher, PacketCallback
from .reassembly import ChunkReassembler
from .state import StateStore
from .transport import ZmqPublisher, ZmqSubscriber

# Packet types published as header-less FlatBuffers, dispatched directly by
# packet type/socket rather than through the header-based decoder registry
# (see decoder/fbs_codec.py).
_FBS_DECODERS: dict[int, Callable[[bytes], AnyPacket | None]] = {
    2: decode_compact_scoring,
    3: decode_system_event,
    7: decode_weather,
    8: decode_extended_state,
    9: decode_force_feedback,
    10: decode_graphics,
}


class IsiMotorClient:
    """
    Ultra-low latency ZeroMQ client for isiMotor / LMU telemetry and scoring.

    Each outbound packet type is published by the plugin on its own TCP port
    (base_port + packet_type; e.g. base_port=5000 puts TelemInfo on 5001,
    CompactScoring on 5002, ...) so that consumers can subscribe to only the
    stream(s) they need. Ports are hardcoded arithmetically for now, pending
    a future service registry that will allocate them dynamically.

    Usage examples:
    1. Callback-based:
        client = IsiMotorClient(base_port=5000)
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
        with IsiMotorClient(base_port=5000) as client:
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
        host: str = "127.0.0.1",
        base_port: int = 5000,
        inbound_host: str = "127.0.0.1",
        inbound_port: int = 5101,
        reassembly_timeout: float = 1.0,
    ) -> None:
        self.host = host
        self.base_port = base_port
        self.inbound_host = inbound_host
        self.inbound_port = inbound_port

        # Subsystems (Single Responsibility Principle)
        # The plugin binds one telemetry PUB socket per packet type (base_port + packet
        # type), so the client connects one SUB per type; the plugin binds a single
        # grouped inbound commands SUB socket, so the client connects as PUB.
        self._receiver = ZmqSubscriber(host=self.host, port=self.base_port)
        self._sender = ZmqPublisher(default_host=self.inbound_host, default_port=self.inbound_port)
        self._decoder_registry = PacketDecoderRegistry()
        self._reassembler = ChunkReassembler(registry=self._decoder_registry, timeout_seconds=reassembly_timeout)
        self._state = StateStore()
        self._dispatcher = EventDispatcher()

    # ── Context Manager Protocol ───────────────────────────────────────────────

    def __enter__(self) -> "IsiMotorClient":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    # ── Lifecycle Orchestration (SLAP) ─────────────────────────────────────────

    def start(self) -> "IsiMotorClient":
        """Starts the background ZeroMQ SUB receiver thread."""
        self._receiver.start(self._on_datagram_received)
        return self

    def stop(self) -> None:
        """Stops the background ZeroMQ SUB receiver thread and releases network sockets."""
        self._receiver.stop()
        self._sender.close()

    @property
    def is_running(self) -> bool:
        """True if the ZeroMQ background listener thread is active."""
        return self._receiver.is_running

    @property
    def reassembler(self) -> ChunkReassembler:
        """Multipart packet chunk reassembler."""
        return self._reassembler

    # ── Internal Ingestion Pipeline (SLAP) ─────────────────────────────────────

    def _on_datagram_received(self, packet_type: int, data: bytes, timestamp: float) -> None:
        """
        Coordinates datagram processing at a single level of abstraction:
        1. Decode a FlatBuffer directly, or reassemble/decode a legacy chunked frame
        2. Store latest packet into thread-safe state cache
        3. Dispatch event to registered callbacks
        """
        packet = self._decode_or_reassemble(packet_type, data, timestamp)
        if packet is not None:
            self._state.update(packet, timestamp)
            self._dispatcher.dispatch(packet)

    def _decode_or_reassemble(self, packet_type: int, data: bytes, timestamp: float) -> AnyPacket | None:
        """Decodes header-less FlatBuffer types directly; reassembles/decodes legacy chunked frames otherwise."""
        fbs_decoder = _FBS_DECODERS.get(packet_type)
        if fbs_decoder is not None:
            return fbs_decoder(data)
        return self._reassembler.process(data, timestamp)

    # ── State Accessors (Thread-Safe) ──────────────────────────────────────────

    def get_latest_telemetry(self) -> TelemInfo | None:
        """Returns the most recently received TelemInfo frame thread-safely."""
        return self._state.get_telemetry()

    def get_latest_scoring(self) -> CompactScoring | None:
        """Returns the most recently received CompactScoring frame thread-safely."""
        return self._state.get_scoring()

    def get_latest_full_scoring(self) -> FullScoringSession | None:
        """Returns the most recently received FullScoringSession frame thread-safely."""
        return self._state.get_full_scoring()

    def get_latest_weather(self) -> WeatherControl | None:
        """Returns the most recently received WeatherControl frame thread-safely."""
        return self._state.get_weather()

    def get_latest_extended_state(self) -> ExtendedState | None:
        """Returns the most recently received ExtendedState frame thread-safely."""
        return self._state.get_extended_state()

    def get_latest_force_feedback(self) -> ForceFeedback | None:
        """Returns the most recently received ForceFeedback frame thread-safely."""
        return self._state.get_force_feedback()

    def get_latest_graphics(self) -> Graphics | None:
        """Returns the most recently received Graphics frame thread-safely."""
        return self._state.get_graphics()

    def get_latest_system_event(self) -> SystemEvent | None:
        """Returns the most recently received SystemEvent thread-safely."""
        return self._state.get_system_event()

    def get_latest_hw_control(self) -> HWControlCommand | None:
        """Returns the most recently received HWControlCommand thread-safely."""
        return self._state.get_hw_control()

    def get_latest_weather_control(self) -> WeatherControlCommand | None:
        """Returns the most recently received WeatherControlCommand thread-safely."""
        return self._state.get_weather_control()

    @property
    def packet_count(self) -> int:
        """Total number of valid packets decoded and ingested."""
        return self._state.packet_count

    @property
    def last_packet_time(self) -> float:
        """Timestamp of the most recent packet received."""
        return self._state.last_packet_time

    # ── Outbound Commands (Inbound to Game) ─────────────────────────────────────

    def send_hw_control(
        self,
        control_name: str,
        control_value: float = 1.0,
        duration_ms: int = 50,
        host: str | None = None,
        port: int | None = None,
    ) -> bool:
        """
        Transmits a hardware / pit menu control command (SIMP Type 100) to the game plugin.

        :param control_name: Control name (e.g. "PitMenuUp", "PitMenuSelect", "TCIncrease", "ABSDecrease").
        :param control_value: 1.0 = press/activate, 0.0 = release, or analog value.
        :param duration_ms: Pulse duration in milliseconds (default: 50ms).
        :param host: Destination IP (defaults to self.inbound_host).
        :param port: Destination inbound port (defaults to self.inbound_port).
        """
        return self._sender.send_hw_control(
            control_name=control_name,
            control_value=control_value,
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
        host: str | None = None,
        port: int | None = None,
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
        return self._sender.send_weather_override(
            ambient_temp=ambient_temp,
            track_temp=track_temp,
            dark_cloud=dark_cloud,
            raining=raining,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            min_path_wetness=min_path_wetness,
            max_path_wetness=max_path_wetness,
            host=host,
            port=port,
        )

    # ── Extensible Event Dispatching (Open/Closed Principle) ───────────────────

    def subscribe(self, packet_cls: type, callback: PacketCallback) -> None:
        """Subscribes a callback to a specific packet type."""
        self._dispatcher.subscribe(packet_cls, callback)

    def unsubscribe(self, packet_cls: type, callback: PacketCallback) -> None:
        """Unsubscribes a callback from a specific packet type."""
        self._dispatcher.unsubscribe(packet_cls, callback)

    def register_decoder(self, packet_type: int, decoder: Callable[[bytes], AnyPacket | None]) -> None:
        """Registers or overrides a payload decoder for a given packet type."""
        self._decoder_registry.register(packet_type, decoder)

    # ── Property Delegations for Direct Callbacks ──────────────────────────────

    @property
    def on_telemetry(self) -> Callable[[TelemInfo], None] | None:
        return self._dispatcher.on_telemetry

    @on_telemetry.setter
    def on_telemetry(self, value: Callable[[TelemInfo], None] | None) -> None:
        self._dispatcher.on_telemetry = value

    @property
    def on_scoring(self) -> Callable[[CompactScoring], None] | None:
        return self._dispatcher.on_scoring

    @on_scoring.setter
    def on_scoring(self, value: Callable[[CompactScoring], None] | None) -> None:
        self._dispatcher.on_scoring = value

    @property
    def on_full_scoring(self) -> Callable[[FullScoringSession], None] | None:
        return self._dispatcher.on_full_scoring

    @on_full_scoring.setter
    def on_full_scoring(self, value: Callable[[FullScoringSession], None] | None) -> None:
        self._dispatcher.on_full_scoring = value

    @property
    def on_weather(self) -> Callable[[WeatherControl], None] | None:
        return self._dispatcher.on_weather

    @on_weather.setter
    def on_weather(self, value: Callable[[WeatherControl], None] | None) -> None:
        self._dispatcher.on_weather = value

    @property
    def on_extended_state(self) -> Callable[[ExtendedState], None] | None:
        return self._dispatcher.on_extended_state

    @on_extended_state.setter
    def on_extended_state(self, value: Callable[[ExtendedState], None] | None) -> None:
        self._dispatcher.on_extended_state = value

    @property
    def on_force_feedback(self) -> Callable[[ForceFeedback], None] | None:
        return self._dispatcher.on_force_feedback

    @on_force_feedback.setter
    def on_force_feedback(self, value: Callable[[ForceFeedback], None] | None) -> None:
        self._dispatcher.on_force_feedback = value

    @property
    def on_graphics(self) -> Callable[[Graphics], None] | None:
        return self._dispatcher.on_graphics

    @on_graphics.setter
    def on_graphics(self, value: Callable[[Graphics], None] | None) -> None:
        self._dispatcher.on_graphics = value

    @property
    def on_system_event(self) -> Callable[[SystemEvent], None] | None:
        return self._dispatcher.on_system_event

    @on_system_event.setter
    def on_system_event(self, value: Callable[[SystemEvent], None] | None) -> None:
        self._dispatcher.on_system_event = value

    @property
    def on_hw_control(self) -> Callable[[HWControlCommand], None] | None:
        return self._dispatcher.on_hw_control

    @on_hw_control.setter
    def on_hw_control(self, value: Callable[[HWControlCommand], None] | None) -> None:
        self._dispatcher.on_hw_control = value

    @property
    def on_weather_control(self) -> Callable[[WeatherControlCommand], None] | None:
        return self._dispatcher.on_weather_control

    @on_weather_control.setter
    def on_weather_control(self, value: Callable[[WeatherControlCommand], None] | None) -> None:
        self._dispatcher.on_weather_control = value

    @property
    def on_packet(self) -> Callable[[AnyPacket], None] | None:
        return self._dispatcher.on_packet

    @on_packet.setter
    def on_packet(self, value: Callable[[AnyPacket], None] | None) -> None:
        self._dispatcher.on_packet = value
