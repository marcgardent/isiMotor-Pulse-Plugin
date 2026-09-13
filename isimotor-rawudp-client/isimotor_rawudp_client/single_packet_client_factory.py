"""
Factory building a `SinglePacketClient[T]` pinned to one domain packet type.

Each method below pins its packet_type + decoder pair once, here, at the
call site that names the type - never inferred or re-decided at runtime.
"""

from isimotor_rawudp_types import (
    CompactScoring,
    ExtendedState,
    ForceFeedback,
    FullScoringSession,
    Graphics,
    SystemEvent,
    TelemInfo,
    WeatherControl,
)

from .constants import (
    PKT_TYPE_COMPACT_SCORING,
    PKT_TYPE_EXTENDED_STATE,
    PKT_TYPE_FORCE_FEEDBACK,
    PKT_TYPE_FULL_SCORING,
    PKT_TYPE_GRAPHICS,
    PKT_TYPE_SYSTEM_EVENT,
    PKT_TYPE_TELEMETRY,
    PKT_TYPE_WEATHER,
)
from .decoder.events import decode_system_event
from .decoder.feedback import decode_force_feedback
from .decoder.graphics import decode_graphics
from .decoder.physics import decode_extended_state
from .decoder.scoring import decode_compact_scoring, decode_full_scoring
from .decoder.telemetry import decode_telemetry
from .decoder.weather import decode_weather
from .single_packet_client import SinglePacketClient


class SinglePacketClientFactory:
    """Builds a `SinglePacketClient[T]` for exactly one outbound packet type."""

    @staticmethod
    def telemetry(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[TelemInfo]:
        """Builds a client that only listens to TelemInfo."""
        return SinglePacketClient(
            packet_type=PKT_TYPE_TELEMETRY, decoder=decode_telemetry, host=host, base_port=base_port
        )

    @staticmethod
    def scoring(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[CompactScoring]:
        """Builds a client that only listens to CompactScoring."""
        return SinglePacketClient(
            packet_type=PKT_TYPE_COMPACT_SCORING, decoder=decode_compact_scoring, host=host, base_port=base_port
        )

    @staticmethod
    def system_event(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[SystemEvent]:
        """Builds a client that only listens to SystemEvent."""
        return SinglePacketClient(
            packet_type=PKT_TYPE_SYSTEM_EVENT, decoder=decode_system_event, host=host, base_port=base_port
        )

    @staticmethod
    def full_scoring(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[FullScoringSession]:
        """Builds a client that only listens to FullScoringSession."""
        return SinglePacketClient(
            packet_type=PKT_TYPE_FULL_SCORING, decoder=decode_full_scoring, host=host, base_port=base_port
        )

    @staticmethod
    def weather(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[WeatherControl]:
        """Builds a client that only listens to WeatherControl."""
        return SinglePacketClient(packet_type=PKT_TYPE_WEATHER, decoder=decode_weather, host=host, base_port=base_port)

    @staticmethod
    def extended_state(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[ExtendedState]:
        """Builds a client that only listens to ExtendedState."""
        return SinglePacketClient(
            packet_type=PKT_TYPE_EXTENDED_STATE, decoder=decode_extended_state, host=host, base_port=base_port
        )

    @staticmethod
    def force_feedback(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[ForceFeedback]:
        """Builds a client that only listens to ForceFeedback."""
        return SinglePacketClient(
            packet_type=PKT_TYPE_FORCE_FEEDBACK, decoder=decode_force_feedback, host=host, base_port=base_port
        )

    @staticmethod
    def graphics(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[Graphics]:
        """Builds a client that only listens to Graphics."""
        return SinglePacketClient(
            packet_type=PKT_TYPE_GRAPHICS, decoder=decode_graphics, host=host, base_port=base_port
        )
