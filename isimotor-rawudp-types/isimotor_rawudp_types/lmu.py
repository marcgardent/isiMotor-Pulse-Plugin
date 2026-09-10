"""
Le Mans Ultimate (LMU) and modern WEC simulation extended data models.
Explicitly isolates LMU-specific extensions from standard base isiMotor telemetry and scoring.
"""

from dataclasses import dataclass, field
from enum import IntEnum

from .ecu import EcuState


class LMUCompoundType(IntEnum):
    """LMU official tire compound enum (from wheel telemetry)."""

    UNKNOWN = 0
    SOFT = 1
    MEDIUM = 2
    HARD = 3
    WET = 4
    INTERMEDIATE = 5

    def __str__(self) -> str:
        return self.name.capitalize()


@dataclass(slots=True)
class LMUTelemetryExtension:
    """
    LMU-specific vehicle telemetry extensions (unpacked from mExpansion[111]).
    Separates WEC Hypercar energy, live regen, track cuts, and ECU from base physics.
    """

    ecu: EcuState = field(default_factory=EcuState)
    virtual_energy: float = 0.0
    """Hypercar remaining virtual energy fraction (0.0 to 1.0)."""
    regen_kw: float = 0.0
    """Instantaneous electrical regeneration power in kW."""
    track_limits_steps: int = 0
    """Accumulated track limits infraction steps."""
    vehicle_model: str = ""
    """Specific chassis/model designation (e.g. 'Ferrari 499P')."""

    @property
    def has_hypercar_energy(self) -> bool:
        """Whether the vehicle utilizes WEC Hypercar Virtual Energy management."""
        return self.virtual_energy > 0.0


@dataclass(slots=True)
class LMUWheelExtension:
    """
    LMU-specific wheel telemetry extensions (unpacked from wheel mExpansion[24]).
    """

    compound_type: LMUCompoundType = LMUCompoundType.UNKNOWN
    brake_wear_meters: float = 0.0
    """Residual pad/disc thickness in meters."""


@dataclass(slots=True)
class LMUScoringExtension:
    """
    LMU-specific global session scoring extensions (unpacked from scoring mExpansion[200]).
    """

    track_grip_level: int = 0
    """0=Default, 1=Green, 2=Fast, 3=Optimum, 4=Rubbered."""
    track_limits_steps_per_point: int = 0
    """Infraction steps required per penalty point."""
    track_limits_steps_per_penalty: int = 0
    """Step threshold triggering a DT / Stop&Go."""
    time_of_day_seconds: float = 0.0
    """Exact solar simulation time in seconds since midnight."""

    @property
    def grip_fraction(self) -> float:
        """Continuous grip level fraction (0.0 to 1.0)."""
        mapping = {0: 0.0, 1: 0.25, 2: 0.50, 3: 0.75, 4: 0.90}
        return mapping.get(self.track_grip_level, 0.0)

    @property
    def time_of_day_str(self) -> str:
        """Formatted 24h clock string 'HH:MM:SS'."""
        total_sec = int(self.time_of_day_seconds) % 86400
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        secs = total_sec % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass(slots=True)
class LMUVehicleScoringExtension:
    """
    LMU-specific per-vehicle scoring extensions (unpacked from vehicle scoring mExpansion[48]).
    """

    fuel_fraction: float = 0.0
    """Opponent estimated fuel fraction (0.0 to 1.0)."""
    track_limits_steps: int = 0
    """Vehicle cumulative cut count."""
