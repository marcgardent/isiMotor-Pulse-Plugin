"""
Factory building a `FlatBufferSinglePacketClient[F]` pinned to one domain packet type.

Each method below pins its packet_type + FlatBuffer root parser pair once,
here, at the call site that names the type - never inferred or re-decided
at runtime.
"""

from isimotor_rawudp_types.fbs_generated.isimotor.fbs import CompactScoring as _CompactScoringFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import ExtendedState as _ExtendedStateFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import ForceFeedback as _ForceFeedbackFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import FullScoringSession as _FullScoringSessionFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import Graphics as _GraphicsFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import SystemEvent as _SystemEventFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import TelemInfo as _TelemInfoFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import WeatherControl as _WeatherControlFB

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
from .flatbuffer_single_packet_client import FlatBufferSinglePacketClient


class FlatBufferSinglePacketClientFactory:
    """Builds a `FlatBufferSinglePacketClient[F]` for exactly one outbound packet type."""

    @staticmethod
    def telemetry(
        host: str = "127.0.0.1", base_port: int = 5000
    ) -> FlatBufferSinglePacketClient[_TelemInfoFB.TelemInfo]:
        """Builds a client that only listens to TelemInfo, yielding its raw FlatBuffer root."""
        return FlatBufferSinglePacketClient(
            packet_type=PKT_TYPE_TELEMETRY,
            root_parser=lambda data: _TelemInfoFB.TelemInfo.GetRootAs(data, 0),
            host=host,
            base_port=base_port,
        )

    @staticmethod
    def scoring(
        host: str = "127.0.0.1", base_port: int = 5000
    ) -> FlatBufferSinglePacketClient[_CompactScoringFB.CompactScoring]:
        """Builds a client that only listens to CompactScoring, yielding its raw FlatBuffer root."""
        return FlatBufferSinglePacketClient(
            packet_type=PKT_TYPE_COMPACT_SCORING,
            root_parser=lambda data: _CompactScoringFB.CompactScoring.GetRootAs(data, 0),
            host=host,
            base_port=base_port,
        )

    @staticmethod
    def system_event(
        host: str = "127.0.0.1", base_port: int = 5000
    ) -> FlatBufferSinglePacketClient[_SystemEventFB.SystemEvent]:
        """Builds a client that only listens to SystemEvent, yielding its raw FlatBuffer root."""
        return FlatBufferSinglePacketClient(
            packet_type=PKT_TYPE_SYSTEM_EVENT,
            root_parser=lambda data: _SystemEventFB.SystemEvent.GetRootAs(data, 0),
            host=host,
            base_port=base_port,
        )

    @staticmethod
    def full_scoring(
        host: str = "127.0.0.1", base_port: int = 5000
    ) -> FlatBufferSinglePacketClient[_FullScoringSessionFB.FullScoringSession]:
        """Builds a client that only listens to FullScoringSession, yielding its raw FlatBuffer root."""
        return FlatBufferSinglePacketClient(
            packet_type=PKT_TYPE_FULL_SCORING,
            root_parser=lambda data: _FullScoringSessionFB.FullScoringSession.GetRootAs(data, 0),
            host=host,
            base_port=base_port,
        )

    @staticmethod
    def weather(
        host: str = "127.0.0.1", base_port: int = 5000
    ) -> FlatBufferSinglePacketClient[_WeatherControlFB.WeatherControl]:
        """Builds a client that only listens to WeatherControl, yielding its raw FlatBuffer root."""
        return FlatBufferSinglePacketClient(
            packet_type=PKT_TYPE_WEATHER,
            root_parser=lambda data: _WeatherControlFB.WeatherControl.GetRootAs(data, 0),
            host=host,
            base_port=base_port,
        )

    @staticmethod
    def extended_state(
        host: str = "127.0.0.1", base_port: int = 5000
    ) -> FlatBufferSinglePacketClient[_ExtendedStateFB.ExtendedState]:
        """Builds a client that only listens to ExtendedState, yielding its raw FlatBuffer root."""
        return FlatBufferSinglePacketClient(
            packet_type=PKT_TYPE_EXTENDED_STATE,
            root_parser=lambda data: _ExtendedStateFB.ExtendedState.GetRootAs(data, 0),
            host=host,
            base_port=base_port,
        )

    @staticmethod
    def force_feedback(
        host: str = "127.0.0.1", base_port: int = 5000
    ) -> FlatBufferSinglePacketClient[_ForceFeedbackFB.ForceFeedback]:
        """Builds a client that only listens to ForceFeedback, yielding its raw FlatBuffer root."""
        return FlatBufferSinglePacketClient(
            packet_type=PKT_TYPE_FORCE_FEEDBACK,
            root_parser=lambda data: _ForceFeedbackFB.ForceFeedback.GetRootAs(data, 0),
            host=host,
            base_port=base_port,
        )

    @staticmethod
    def graphics(host: str = "127.0.0.1", base_port: int = 5000) -> FlatBufferSinglePacketClient[_GraphicsFB.Graphics]:
        """Builds a client that only listens to Graphics, yielding its raw FlatBuffer root."""
        return FlatBufferSinglePacketClient(
            packet_type=PKT_TYPE_GRAPHICS,
            root_parser=lambda data: _GraphicsFB.Graphics.GetRootAs(data, 0),
            host=host,
            base_port=base_port,
        )
