"""
Factory building a `DomainSinglePacketClient[T]` pinned to one domain packet type.

Each method below pins its packet_type + decoder pair once, here, at the
call site that names the type - never inferred or re-decided at runtime.
"""

from isimotor_pulse_types import (
    CompactScoring,
    ExtendedState,
    ForceFeedback,
    FullScoringSession,
    Graphics,
    SystemEvent,
    TelemInfo,
    WeatherControl,
)

from ._internal.constants import (
    PKT_TYPE_COMPACT_SCORING,
    PKT_TYPE_EXTENDED_STATE,
    PKT_TYPE_FORCE_FEEDBACK,
    PKT_TYPE_FULL_SCORING,
    PKT_TYPE_GRAPHICS,
    PKT_TYPE_SYSTEM_EVENT,
    PKT_TYPE_TELEMETRY,
    PKT_TYPE_WEATHER,
)
from ._internal.decoder.events import decode_system_event
from ._internal.decoder.feedback import decode_force_feedback
from ._internal.decoder.graphics import decode_graphics
from ._internal.decoder.physics import decode_extended_state
from ._internal.decoder.scoring import decode_compact_scoring, decode_full_scoring
from ._internal.decoder.telemetry import decode_telemetry
from ._internal.decoder.weather import decode_weather
from ._internal.domain_single_packet_client import DomainSinglePacketClient


class DomainSinglePacketClientFactory:
    """Builds a `DomainSinglePacketClient[T]` for exactly one outbound packet type."""

    @staticmethod
    def telemetry(host: str = "127.0.0.1", base_port: int = 5000) -> DomainSinglePacketClient[TelemInfo]:
        """Builds a client that only listens to TelemInfo."""
        return DomainSinglePacketClient(
            packet_type=PKT_TYPE_TELEMETRY, decoder=decode_telemetry, host=host, base_port=base_port
        )

    @staticmethod
    def scoring(host: str = "127.0.0.1", base_port: int = 5000) -> DomainSinglePacketClient[CompactScoring]:
        """Builds a client that only listens to CompactScoring."""
        return DomainSinglePacketClient(
            packet_type=PKT_TYPE_COMPACT_SCORING, decoder=decode_compact_scoring, host=host, base_port=base_port
        )

    @staticmethod
    def system_event(host: str = "127.0.0.1", base_port: int = 5000) -> DomainSinglePacketClient[SystemEvent]:
        """Builds a client that only listens to SystemEvent."""
        return DomainSinglePacketClient(
            packet_type=PKT_TYPE_SYSTEM_EVENT, decoder=decode_system_event, host=host, base_port=base_port
        )

    @staticmethod
    def full_scoring(host: str = "127.0.0.1", base_port: int = 5000) -> DomainSinglePacketClient[FullScoringSession]:
        """Builds a client that only listens to FullScoringSession."""
        return DomainSinglePacketClient(
            packet_type=PKT_TYPE_FULL_SCORING, decoder=decode_full_scoring, host=host, base_port=base_port
        )

    @staticmethod
    def weather(host: str = "127.0.0.1", base_port: int = 5000) -> DomainSinglePacketClient[WeatherControl]:
        """Builds a client that only listens to WeatherControl."""
        return DomainSinglePacketClient(
            packet_type=PKT_TYPE_WEATHER, decoder=decode_weather, host=host, base_port=base_port
        )

    @staticmethod
    def extended_state(host: str = "127.0.0.1", base_port: int = 5000) -> DomainSinglePacketClient[ExtendedState]:
        """Builds a client that only listens to ExtendedState."""
        return DomainSinglePacketClient(
            packet_type=PKT_TYPE_EXTENDED_STATE, decoder=decode_extended_state, host=host, base_port=base_port
        )

    @staticmethod
    def force_feedback(host: str = "127.0.0.1", base_port: int = 5000) -> DomainSinglePacketClient[ForceFeedback]:
        """Builds a client that only listens to ForceFeedback."""
        return DomainSinglePacketClient(
            packet_type=PKT_TYPE_FORCE_FEEDBACK, decoder=decode_force_feedback, host=host, base_port=base_port
        )

    @staticmethod
    def graphics(host: str = "127.0.0.1", base_port: int = 5000) -> DomainSinglePacketClient[Graphics]:
        """Builds a client that only listens to Graphics."""
        return DomainSinglePacketClient(
            packet_type=PKT_TYPE_GRAPHICS, decoder=decode_graphics, host=host, base_port=base_port
        )
