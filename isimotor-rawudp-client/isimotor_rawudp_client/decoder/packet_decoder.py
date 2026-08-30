"""
Central packet decoding dispatcher and registry.
Open/Closed Principle compliant: packet types and decoders can be registered and extended.
"""

from collections.abc import Callable
from typing import Any, Union

from ..constants import (
    HEADER_SIZE,
    PKT_TYPE_COMPACT_SCORING,
    PKT_TYPE_EXTENDED_STATE,
    PKT_TYPE_FORCE_FEEDBACK,
    PKT_TYPE_FULL_SCORING,
    PKT_TYPE_GRAPHICS,
    PKT_TYPE_HW_CONTROL,
    PKT_TYPE_SYSTEM_EVENT,
    PKT_TYPE_TELEMETRY,
    PKT_TYPE_WEATHER,
    PKT_TYPE_WEATHER_CONTROL,
)
from ..models import (
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
from .commands import decode_hw_control, decode_weather_control
from .events import decode_system_event
from .feedback import decode_force_feedback
from .graphics import decode_graphics
from .header import decode_header
from .physics import decode_extended_state
from .scoring import decode_compact_scoring, decode_full_scoring
from .telemetry import decode_telemetry
from .weather import decode_weather

AnyPacket = Union[
    TelemInfo,
    CompactScoring,
    FullScoringSession,
    WeatherControl,
    ExtendedState,
    ForceFeedback,
    Graphics,
    SystemEvent,
    HWControlCommand,
    WeatherControlCommand,
]

DecoderFunc = Callable[[bytes], Any | None]


class PacketDecoderRegistry:
    """
    Registry for binary packet payload decoders keyed by SIMP packet type.
    Enables extension of new packet types without modifying core dispatch logic (OCP).
    """

    def __init__(self) -> None:
        self._decoders: dict[int, DecoderFunc] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(PKT_TYPE_TELEMETRY, decode_telemetry)
        self.register(PKT_TYPE_COMPACT_SCORING, decode_compact_scoring)
        self.register(PKT_TYPE_SYSTEM_EVENT, decode_system_event)
        self.register(PKT_TYPE_FULL_SCORING, decode_full_scoring)
        self.register(PKT_TYPE_WEATHER, decode_weather)
        self.register(PKT_TYPE_EXTENDED_STATE, decode_extended_state)
        self.register(PKT_TYPE_FORCE_FEEDBACK, decode_force_feedback)
        self.register(PKT_TYPE_GRAPHICS, decode_graphics)
        self.register(PKT_TYPE_HW_CONTROL, decode_hw_control)
        self.register(PKT_TYPE_WEATHER_CONTROL, decode_weather_control)

    def register(self, packet_type: int, decoder: DecoderFunc) -> None:
        """Registers or overrides a payload decoder for a given packet type."""
        self._decoders[packet_type] = decoder

    def get_decoder(self, packet_type: int) -> DecoderFunc | None:
        """Retrieves registered decoder for a packet type."""
        return self._decoders.get(packet_type)

    def decode_standard_packet(self, data: bytes) -> AnyPacket | None:
        """Decodes a packet with a standardized 24-byte SIMP header."""
        if len(data) < HEADER_SIZE or not data.startswith(b"SIMP"):
            return None

        if data[4] != 1:  # Not protocol version 1
            return None

        hdr = decode_header(data)
        if not hdr:
            return None

        payload = data[HEADER_SIZE : HEADER_SIZE + hdr.payload_size]

        # Multi-chunk packets should be assembled before decoding full session
        if hdr.total_chunks > 1:
            return None

        decoder = self._decoders.get(hdr.packet_type)
        if decoder:
            return decoder(payload)

        return None


# Default global registry instance
_DEFAULT_REGISTRY = PacketDecoderRegistry()


def decode_packet(data: bytes, registry: PacketDecoderRegistry | None = None) -> AnyPacket | None:
    """
    Main decoder entrypoint. Identifies and parses standardized isiMotor SIMP UDP packets.
    Strictly decodes packets conforming to the 24-byte SIMP header protocol.
    """
    if not data or len(data) < HEADER_SIZE or not data.startswith(b"SIMP") or data[4] != 1:
        return None

    active_registry = registry or _DEFAULT_REGISTRY
    return active_registry.decode_standard_packet(data)
