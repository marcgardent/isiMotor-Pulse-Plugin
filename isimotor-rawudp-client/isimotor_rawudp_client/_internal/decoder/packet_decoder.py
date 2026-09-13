"""
Shared packet type union for decoded isiMotor / LMU FlatBuffer packets.
"""

from typing import Union

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
