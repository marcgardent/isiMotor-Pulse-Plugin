"""
Data models and wrapped structures for isiMotor-RawUDP-Plugin telemetry & scoring.

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
from .feedback import (
    ForceFeedback,
)
from .graphics import (
    Graphics,
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

__all__ = [
    "CompactScoring",
    "ExtendedState",
    "ForceFeedback",
    "FullScoringSession",
    "Graphics",
    "HWControlCommand",
    "PhysicsOptions",
    "RawUdpHeader",
    "SystemEvent",
    "TelemInfo",
    "TelemVect3",
    "TelemWheel",
    "VehicleScoring",
    "WeatherControl",
    "WeatherControlCommand",
    "WheelInfo",
]
