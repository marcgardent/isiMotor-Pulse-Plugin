"""
Physics options, driving aids, impact and damage data models.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PhysicsOptions:
    """
    Active driving aids, physics rules & multipliers (SIMP Type 8 Physics sub-block, 40 bytes).
    """
    traction_control: int = 0              # 0 (off) - 3 (high)
    anti_lock_brakes: int = 0              # 0 (off) - 2 (high)
    stability_control: int = 0             # 0 (off) - 2 (high)
    auto_shift: int = 0                    # 0 (off), 1 (upshifts), 2 (downshifts), 3 (all)
    auto_clutch: int = 0                   # 0 (off), 1 (on)
    invulnerable: int = 0                  # 0 (off), 1 (on)
    opposite_lock: int = 0                 # 0 (off), 1 (on)
    steering_help: int = 0                 # 0 (off) - 3 (high)
    braking_help: int = 0                  # 0 (off) - 2 (high)
    spin_recovery: int = 0                 # 0 (off), 1 (on)
    auto_pit: int = 0                      # 0 (off), 1 (on)
    auto_lift: int = 0                     # 0 (off), 1 (on)
    auto_blip: int = 0                     # 0 (off), 1 (on)
    fuel_mult: int = 1                     # Fuel usage multiplier (0x - 7x)
    tire_mult: int = 1                     # Tire wear multiplier (0x - 7x)
    mech_fail: int = 1                     # 0 (off), 1 (normal), 2 (timescaled)
    allow_pitcrew_push: int = 0            # 0 (off), 1 (on)
    repeat_shifts: int = 0                 # Accidental repeat shift prevention
    hold_clutch: int = 0                   # Auto-shifters at start of race (0/1)
    auto_reverse: int = 0                  # 0 (off), 1 (on)
    alternate_neutral: int = 0             # 0 (off), 1 (on)
    ai_control: int = 0                    # 0 (player driving), 1 (AI driving)
    manual_shift_override_time: float = 0.0
    auto_shift_override_time: float = 0.0
    speed_sensitive_steering: float = 0.0  # 0.0 (off) to 1.0
    steer_ratio_speed: float = 0.0         # Speed (m/s) under which lock gets expanded

    @property
    def traction_control_str(self) -> str:
        return {0: "Off", 1: "Low", 2: "Medium", 3: "High"}.get(self.traction_control, f"TC({self.traction_control})")

    @property
    def anti_lock_brakes_str(self) -> str:
        return {0: "Off", 1: "Low", 2: "High"}.get(self.anti_lock_brakes, f"ABS({self.anti_lock_brakes})")

    @property
    def auto_shift_str(self) -> str:
        return {0: "Manual", 1: "Auto Up", 2: "Auto Down", 3: "Full Auto"}.get(self.auto_shift, f"Shift({self.auto_shift})")


@dataclass(frozen=True)
class ExtendedState:
    """
    Extended game state, driving aids, accumulated damage & session transitions (SIMP Type 8, 68 bytes).
    """
    physics: PhysicsOptions = field(default_factory=PhysicsOptions)
    max_impact_magnitude: float = 0.0      # Max collision impact recorded in session
    accumulated_impact_magnitude: float = 0.0 # Cumulative collision damage energy
    in_realtime_fc: bool = True            # In cockpit / track vs UI monitor
    session_started: bool = True           # Session started event state
    session: int = 0                       # Current session index
    current_pit_speed_limit: float = 16.67 # Speed limit in pit lane (m/s)

    @property
    def current_pit_speed_limit_kmh(self) -> float:
        """Pit lane speed limit in km/h."""
        return self.current_pit_speed_limit * 3.6
