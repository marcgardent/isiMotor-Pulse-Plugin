"""
Factory building a `RawSinglePacketClient` pinned to one domain packet type.

Each method below pins its packet_type once, here, at the call site that
names the type - never inferred or re-decided at runtime. Unlike
`DomainSinglePacketClientFactory`, no decoder is involved: the caller gets the raw
message bytes for that one type.
"""

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
from ._internal.raw_single_packet_client import RawSinglePacketClient


class RawSinglePacketClientFactory:
    """Builds a `RawSinglePacketClient` for exactly one outbound packet type, undecoded."""

    @staticmethod
    def telemetry(host: str = "127.0.0.1", base_port: int = 5000) -> RawSinglePacketClient:
        """Builds a raw client that only listens to TelemInfo's packet type."""
        return RawSinglePacketClient(packet_type=PKT_TYPE_TELEMETRY, host=host, base_port=base_port)

    @staticmethod
    def scoring(host: str = "127.0.0.1", base_port: int = 5000) -> RawSinglePacketClient:
        """Builds a raw client that only listens to CompactScoring's packet type."""
        return RawSinglePacketClient(packet_type=PKT_TYPE_COMPACT_SCORING, host=host, base_port=base_port)

    @staticmethod
    def system_event(host: str = "127.0.0.1", base_port: int = 5000) -> RawSinglePacketClient:
        """Builds a raw client that only listens to SystemEvent's packet type."""
        return RawSinglePacketClient(packet_type=PKT_TYPE_SYSTEM_EVENT, host=host, base_port=base_port)

    @staticmethod
    def full_scoring(host: str = "127.0.0.1", base_port: int = 5000) -> RawSinglePacketClient:
        """Builds a raw client that only listens to FullScoringSession's packet type."""
        return RawSinglePacketClient(packet_type=PKT_TYPE_FULL_SCORING, host=host, base_port=base_port)

    @staticmethod
    def weather(host: str = "127.0.0.1", base_port: int = 5000) -> RawSinglePacketClient:
        """Builds a raw client that only listens to WeatherControl's packet type."""
        return RawSinglePacketClient(packet_type=PKT_TYPE_WEATHER, host=host, base_port=base_port)

    @staticmethod
    def extended_state(host: str = "127.0.0.1", base_port: int = 5000) -> RawSinglePacketClient:
        """Builds a raw client that only listens to ExtendedState's packet type."""
        return RawSinglePacketClient(packet_type=PKT_TYPE_EXTENDED_STATE, host=host, base_port=base_port)

    @staticmethod
    def force_feedback(host: str = "127.0.0.1", base_port: int = 5000) -> RawSinglePacketClient:
        """Builds a raw client that only listens to ForceFeedback's packet type."""
        return RawSinglePacketClient(packet_type=PKT_TYPE_FORCE_FEEDBACK, host=host, base_port=base_port)

    @staticmethod
    def graphics(host: str = "127.0.0.1", base_port: int = 5000) -> RawSinglePacketClient:
        """Builds a raw client that only listens to Graphics's packet type."""
        return RawSinglePacketClient(packet_type=PKT_TYPE_GRAPHICS, host=host, base_port=base_port)
