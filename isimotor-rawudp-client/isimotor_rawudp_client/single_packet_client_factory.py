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
        """Builds a client that only listens to TelemInfo (packet type 1)."""
        return SinglePacketClient(packet_type=1, decoder=decode_telemetry, host=host, base_port=base_port)

    @staticmethod
    def scoring(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[CompactScoring]:
        """Builds a client that only listens to CompactScoring (packet type 2)."""
        return SinglePacketClient(packet_type=2, decoder=decode_compact_scoring, host=host, base_port=base_port)

    @staticmethod
    def system_event(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[SystemEvent]:
        """Builds a client that only listens to SystemEvent (packet type 3)."""
        return SinglePacketClient(packet_type=3, decoder=decode_system_event, host=host, base_port=base_port)

    @staticmethod
    def full_scoring(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[FullScoringSession]:
        """Builds a client that only listens to FullScoringSession (packet type 4)."""
        return SinglePacketClient(packet_type=4, decoder=decode_full_scoring, host=host, base_port=base_port)

    @staticmethod
    def weather(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[WeatherControl]:
        """Builds a client that only listens to WeatherControl (packet type 7)."""
        return SinglePacketClient(packet_type=7, decoder=decode_weather, host=host, base_port=base_port)

    @staticmethod
    def extended_state(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[ExtendedState]:
        """Builds a client that only listens to ExtendedState (packet type 8)."""
        return SinglePacketClient(packet_type=8, decoder=decode_extended_state, host=host, base_port=base_port)

    @staticmethod
    def force_feedback(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[ForceFeedback]:
        """Builds a client that only listens to ForceFeedback (packet type 9)."""
        return SinglePacketClient(packet_type=9, decoder=decode_force_feedback, host=host, base_port=base_port)

    @staticmethod
    def graphics(host: str = "127.0.0.1", base_port: int = 5000) -> SinglePacketClient[Graphics]:
        """Builds a client that only listens to Graphics (packet type 10)."""
        return SinglePacketClient(packet_type=10, decoder=decode_graphics, host=host, base_port=base_port)
