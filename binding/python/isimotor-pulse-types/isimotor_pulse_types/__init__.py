"""
Data models and wrapped structures for isiMotor-Pulse-Plugin telemetry & scoring.

COORDINATE SYSTEM NOTES (from isiMotor SDK InternalsPlugin.hpp):
================================================================
Our world coordinate system is left-handed, with +y pointing up.
The local vehicle coordinate system is as follows:
  +x points out the left side of the car (from the driver's perspective)
  +y points out the roof
  +z points out the back of the car

Rotations are as follows:
  +x pitches up
  +y yaws to the right
  +z rolls to the right

Note that ISO vehicle coordinates (+x forward, +y right, +z upward) are
right-handed. If you are using that system, be sure to negate any rotation
or torque data because things rotate in the opposite direction. In other
words:
  - a -z velocity in rFactor/LMU is a +x velocity in ISO
  - a -z rotation in rFactor/LMU is a -x rotation in ISO
"""

from .commands import (
    HWControlCommand,
    WeatherControlCommand,
)
from .common import (
    RawUdpHeader,
    SystemEvent,
    TelemVect3,
)
from .ecu import (
    EcuState,
)
from .enums import (
    KELVIN_TO_CELSIUS_OFFSET,
    MS_TO_KMH,
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    AntiLockBrakes,
    AutoShift,
    CameraType,
    CountLapFlag,
    ElectricBoostMotorState,
    FinishStatus,
    Flag,
    GamePhase,
    IgnitionStarterState,
    MechFailure,
    PacketType,
    PitState,
    RearFlapLegalStatus,
    SectorId,
    SessionType,
    SpeedLimiterState,
    StabilityControl,
    SurfaceType,
    SystemEventType,
    TrackGripLevel,
    TractionControl,
    VehicleControl,
    WiperState,
    YellowFlagState,
)
from .feedback import (
    ForceFeedback,
)
from .graphics import (
    Graphics,
)
from .lmu import (
    LMUCompoundType,
    LMUScoringExtension,
    LMUTelemetryExtension,
    LMUVehicleScoringExtension,
    LMUWheelExtension,
)
from .physics import (
    ExtendedState,
    PhysicsOptions,
)
from .scoring import (
    CompactScoring,
    FullScoringSession,
    VehicleScoring,
)
from .telemetry import (
    TelemInfo,
    TelemWheel,
    WheelInfo,
)
from .weather import (
    WeatherControl,
)

__version__ = "1.0.1"

__all__ = [
    "KELVIN_TO_CELSIUS_OFFSET",
    "MS_TO_KMH",
    "SECONDS_PER_DAY",
    "SECONDS_PER_HOUR",
    "SECONDS_PER_MINUTE",
    "AntiLockBrakes",
    "AutoShift",
    "CameraType",
    "CompactScoring",
    "CountLapFlag",
    "EcuState",
    "ElectricBoostMotorState",
    "ExtendedState",
    "FinishStatus",
    "Flag",
    "ForceFeedback",
    "FullScoringSession",
    "GamePhase",
    "Graphics",
    "HWControlCommand",
    "IgnitionStarterState",
    "LMUCompoundType",
    "LMUScoringExtension",
    "LMUTelemetryExtension",
    "LMUVehicleScoringExtension",
    "LMUWheelExtension",
    "MechFailure",
    "PacketType",
    "PhysicsOptions",
    "PitState",
    "RawUdpHeader",
    "RearFlapLegalStatus",
    "SectorId",
    "SessionType",
    "SpeedLimiterState",
    "StabilityControl",
    "SurfaceType",
    "SystemEvent",
    "SystemEventType",
    "TelemInfo",
    "TelemVect3",
    "TelemWheel",
    "TrackGripLevel",
    "TractionControl",
    "VehicleControl",
    "VehicleScoring",
    "WeatherControl",
    "WeatherControlCommand",
    "WheelInfo",
    "WiperState",
    "YellowFlagState",
]
