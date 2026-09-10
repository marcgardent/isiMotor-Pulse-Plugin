"""
Named enums and unit-conversion constants for magic values used throughout the
SIMP RawUDP protocol wire formats.

All enums subclass `IntEnum` so they stay binary/JSON compatible with the raw
integer fields they replace (an IntEnum member compares equal to, hashes like,
and packs/unpacks exactly like the plain `int` it replaces).
"""

from enum import IntEnum
from typing import Final

# ---------------------------------------------------------------------------
# Unit-conversion constants (previously repeated magic numbers)
# ---------------------------------------------------------------------------

MS_TO_KMH: Final[float] = 3.6
"""Multiplier to convert meters/second to kilometers/hour."""

KELVIN_TO_CELSIUS_OFFSET: Final[float] = 273.15
"""Offset to convert Kelvin to Celsius (celsius = kelvin - offset)."""

SECONDS_PER_DAY: Final[int] = 86400
SECONDS_PER_HOUR: Final[int] = 3600
SECONDS_PER_MINUTE: Final[int] = 60


# ---------------------------------------------------------------------------
# SIMP packet types (RawUdpHeader.packet_type)
# ---------------------------------------------------------------------------


class PacketType(IntEnum):
    """SIMP RawUDP packet type discriminant (`RawUdpHeader.packet_type`)."""

    TELEM_INFO = 1
    COMPACT_SCORING = 2
    SYSTEM_EVENT = 3
    FULL_SCORING_SESSION = 4
    WEATHER_CONTROL = 7
    EXTENDED_STATE = 8
    FORCE_FEEDBACK = 9
    GRAPHICS = 10
    HW_CONTROL_COMMAND = 100
    WEATHER_CONTROL_COMMAND = 101


# ---------------------------------------------------------------------------
# common.py
# ---------------------------------------------------------------------------


class SystemEventType(IntEnum):
    """`SystemEvent.event_id` values (SIMP Type 3)."""

    ENTER_REALTIME = 1
    EXIT_REALTIME = 2
    START_SESSION = 3
    END_SESSION = 4


# ---------------------------------------------------------------------------
# ecu.py
# ---------------------------------------------------------------------------


class WiperState(IntEnum):
    """`EcuState.wiper_state` windshield wiper state."""

    OFF = 0
    AUTO = 1
    SLOW = 2
    FAST = 3


# ---------------------------------------------------------------------------
# graphics.py
# ---------------------------------------------------------------------------


class CameraType(IntEnum):
    """`Graphics.camera_type` viewpoint. Values >= ONBOARD are onboard camera slots."""

    TV_COCKPIT = 0
    COCKPIT = 1
    NOSE = 2
    SWINGMAN = 3
    TRACKSIDE = 4
    ONBOARD = 5
    """Onboard camera base index; camera_type - ONBOARD gives the onboard slot number."""


# ---------------------------------------------------------------------------
# lmu.py
# ---------------------------------------------------------------------------


class TrackGripLevel(IntEnum):
    """`LMUScoringExtension.track_grip_level`."""

    DEFAULT = 0
    GREEN = 1
    FAST = 2
    OPTIMUM = 3
    RUBBERED = 4


TRACK_GRIP_FRACTION: Final[dict[int, float]] = {
    TrackGripLevel.DEFAULT: 0.0,
    TrackGripLevel.GREEN: 0.25,
    TrackGripLevel.FAST: 0.50,
    TrackGripLevel.OPTIMUM: 0.75,
    TrackGripLevel.RUBBERED: 0.90,
}
"""Continuous grip fraction approximation for each `TrackGripLevel`."""


# ---------------------------------------------------------------------------
# physics.py
# ---------------------------------------------------------------------------


class TractionControl(IntEnum):
    """`PhysicsOptions.traction_control`."""

    OFF = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class AntiLockBrakes(IntEnum):
    """`PhysicsOptions.anti_lock_brakes`."""

    OFF = 0
    LOW = 1
    HIGH = 2


class StabilityControl(IntEnum):
    """`PhysicsOptions.stability_control`."""

    OFF = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class AutoShift(IntEnum):
    """`PhysicsOptions.auto_shift`."""

    MANUAL = 0
    AUTO_UP = 1
    AUTO_DOWN = 2
    FULL_AUTO = 3


class MechFailure(IntEnum):
    """`PhysicsOptions.mech_fail`."""

    OFF = 0
    NORMAL = 1
    TIMESCALED = 2


# ---------------------------------------------------------------------------
# scoring.py
# ---------------------------------------------------------------------------


class SessionType(IntEnum):
    """
    `CompactScoring.session` / `FullScoringSession.session` session index.

    Practice is 1-4, qualifying is 5-8, and race is 10-13; use the numeric
    ranges below (`PRACTICE_RANGE`, `QUALIFYING_RANGE`, `RACE_RANGE`) for
    membership checks rather than comparing against a single member.
    """

    TEST_DAY = 0
    PRACTICE_1 = 1
    PRACTICE_2 = 2
    PRACTICE_3 = 3
    PRACTICE_4 = 4
    QUALIFYING_1 = 5
    QUALIFYING_2 = 6
    QUALIFYING_3 = 7
    QUALIFYING_4 = 8
    WARMUP = 9
    RACE_1 = 10
    RACE_2 = 11
    RACE_3 = 12
    RACE_4 = 13


QUALIFYING_SESSION_RANGE: Final[range] = range(SessionType.QUALIFYING_1, SessionType.QUALIFYING_4 + 1)
"""Inclusive range of `session` values considered qualifying (5-8)."""

RACE_SESSION_RANGE: Final[range] = range(SessionType.RACE_1, SessionType.RACE_4 + 1)
"""Inclusive range of `session` values considered a race (10-13)."""


class SectorId(IntEnum):
    """Current/reported sector identifier."""

    SECTOR_3 = 0
    SECTOR_1 = 1
    SECTOR_2 = 2


class CountLapFlag(IntEnum):
    """`CompactScoring.count_lap_flag` / `VehicleScoring.count_lap_flag`."""

    INVALID = 0
    LAP_COUNT_ONLY = 1
    VALID_LAP_AND_TIME = 2


class FinishStatus(IntEnum):
    """`VehicleScoring.finish_status`."""

    RUNNING = 0
    FINISHED = 1
    DNF = 2
    DQ = 3


class VehicleControl(IntEnum):
    """`VehicleScoring.control`."""

    NOBODY = -1
    PLAYER = 0
    AI = 1
    REMOTE = 2
    REPLAY = 3


class PitState(IntEnum):
    """`VehicleScoring.pit_state`."""

    NONE = 0
    REQUEST = 1
    ENTERING = 2
    STOPPED = 3
    EXITING = 4


class Flag(IntEnum):
    """`VehicleScoring.flag` primary flag shown to the vehicle."""

    GREEN = 0
    BLUE = 6


class GamePhase(IntEnum):
    """`FullScoringSession.game_phase`."""

    GARAGE = 0
    WARMUP = 1
    GRID_WALK = 2
    FORMATION = 3
    COUNTDOWN = 4
    GREEN_FLAG = 5
    FULL_COURSE_YELLOW = 6
    SESSION_STOPPED = 7
    SESSION_OVER = 8


class YellowFlagState(IntEnum):
    """`FullScoringSession.yellow_flag_state`."""

    INVALID = -1
    NONE = 0
    PENDING = 1
    PIT_CLOSED = 2
    PIT_LEAD_LAP = 3
    PIT_OPEN = 4
    LAST_LAP = 5
    RESUME = 6


# ---------------------------------------------------------------------------
# telemetry.py
# ---------------------------------------------------------------------------


class SurfaceType(IntEnum):
    """`TelemWheel.surface_type`."""

    DRY = 0
    WET = 1
    GRASS = 2
    DIRT = 3
    GRAVEL = 4
    RUMBLESTRIP = 5
    SPECIAL = 6


GEAR_REVERSE: Final[int] = -1
GEAR_NEUTRAL: Final[int] = 0
"""`TelemInfo.gear` sentinels; positive values are forward gears (1+)."""


class SpeedLimiterState(IntEnum):
    """`TelemInfo.speed_limiter`."""

    OFF = 0
    ON = 1


class RearFlapLegalStatus(IntEnum):
    """`TelemInfo.rear_flap_legal_status` (DRS)."""

    DISALLOWED = 0
    DETECTED = 1
    ALLOWED = 2


class IgnitionStarterState(IntEnum):
    """`TelemInfo.ignition_starter`."""

    OFF = 0
    IGNITION = 1
    IGNITION_AND_STARTER = 2


class ElectricBoostMotorState(IntEnum):
    """`TelemInfo.electric_boost_motor_state`."""

    UNAVAILABLE = 0
    INACTIVE = 1
    PROPULSION = 2
    REGENERATION = 3
