"""
Physics options, driving aids, impact and damage data models.
"""

from dataclasses import dataclass, field

from .enums import MS_TO_KMH, AntiLockBrakes, AutoShift, MechFailure, StabilityControl, TractionControl


@dataclass(frozen=True)
class PhysicsOptions:
    """
    Active driving aids, physics rules & multipliers (SIMP Type 8 Physics sub-block, 40 bytes).
    """

    traction_control: TractionControl = TractionControl.OFF
    """See `TractionControl`."""
    anti_lock_brakes: AntiLockBrakes = AntiLockBrakes.OFF
    """See `AntiLockBrakes`."""
    stability_control: StabilityControl = StabilityControl.OFF
    """See `StabilityControl`."""
    auto_shift: AutoShift = AutoShift.MANUAL
    """See `AutoShift`."""
    auto_clutch: int = 0
    """0 (off), 1 (on)."""
    invulnerable: int = 0
    """0 (off), 1 (on)."""
    opposite_lock: int = 0
    """0 (off), 1 (on)."""
    steering_help: int = 0
    """0 (off) - 3 (high)."""
    braking_help: int = 0
    """0 (off) - 2 (high)."""
    spin_recovery: int = 0
    """0 (off), 1 (on)."""
    auto_pit: int = 0
    """0 (off), 1 (on)."""
    auto_lift: int = 0
    """0 (off), 1 (on)."""
    auto_blip: int = 0
    """0 (off), 1 (on)."""
    fuel_mult: int = 1
    """Fuel usage multiplier (0x - 7x)."""
    tire_mult: int = 1
    """Tire wear multiplier (0x - 7x)."""
    mech_fail: MechFailure = MechFailure.NORMAL
    """See `MechFailure`."""
    allow_pitcrew_push: int = 0
    """0 (off), 1 (on)."""
    repeat_shifts: int = 0
    """Accidental repeat shift prevention."""
    hold_clutch: int = 0
    """Auto-shifters at start of race (0/1)."""
    auto_reverse: int = 0
    """0 (off), 1 (on)."""
    alternate_neutral: int = 0
    """0 (off), 1 (on)."""
    ai_control: int = 0
    """0 (player driving), 1 (AI driving)."""
    manual_shift_override_time: float = 0.0
    auto_shift_override_time: float = 0.0
    speed_sensitive_steering: float = 0.0
    """0.0 (off) to 1.0."""
    steer_ratio_speed: float = 0.0
    """Speed (m/s) under which lock gets expanded."""

    @property
    def traction_control_str(self) -> str:
        return {
            TractionControl.OFF: "Off",
            TractionControl.LOW: "Low",
            TractionControl.MEDIUM: "Medium",
            TractionControl.HIGH: "High",
        }.get(self.traction_control, f"TC({self.traction_control})")

    @property
    def anti_lock_brakes_str(self) -> str:
        return {
            AntiLockBrakes.OFF: "Off",
            AntiLockBrakes.LOW: "Low",
            AntiLockBrakes.HIGH: "High",
        }.get(self.anti_lock_brakes, f"ABS({self.anti_lock_brakes})")

    @property
    def stability_control_str(self) -> str:
        return {
            StabilityControl.OFF: "Off",
            StabilityControl.LOW: "Low",
            StabilityControl.MEDIUM: "Medium",
            StabilityControl.HIGH: "High",
        }.get(self.stability_control, f"ESC({self.stability_control})")

    @property
    def auto_shift_str(self) -> str:
        return {
            AutoShift.MANUAL: "Manual",
            AutoShift.AUTO_UP: "Auto Up",
            AutoShift.AUTO_DOWN: "Auto Down",
            AutoShift.FULL_AUTO: "Full Auto",
        }.get(self.auto_shift, f"Shift({self.auto_shift})")


@dataclass(frozen=True)
class ExtendedState:
    """
    Extended game state, driving aids, accumulated damage & session transitions (SIMP Type 8, 68 bytes).
    """

    physics: PhysicsOptions = field(default_factory=PhysicsOptions)
    max_impact_magnitude: float = 0.0
    """Max collision impact recorded in session."""
    accumulated_impact_magnitude: float = 0.0
    """Cumulative collision damage energy."""
    in_realtime_fc: bool = True
    """In cockpit / track vs UI monitor."""
    session_started: bool = True
    """Session started event state."""
    session: int = 0
    """Current session index."""
    current_pit_speed_limit: float = 16.67
    """Speed limit in pit lane (m/s)."""

    @property
    def current_pit_speed_limit_kmh(self) -> float:
        """Pit lane speed limit in km/h."""
        return self.current_pit_speed_limit * MS_TO_KMH
