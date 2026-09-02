"""
Electronic Control Unit (ECU) and onboard driver aids data models.
Provides native telemetry for Le Mans Ultimate (LMU) and modern isiMotor simulations.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class EcuState:
    """
    Onboard vehicle electronics, ECU maps, and active driver aids.
    Extracted from the 111-byte extended telemetry section (mExpansion / LMUExtendedTelemetry).
    """

    tc_active: bool = False  # True if Traction Control is actively cutting/intervening
    abs_active: bool = False  # True if Anti-lock Braking System is actively modulating pressure

    tc_level: int = -1  # TC level (-1 if unavailable, 0=off or 1..tc_max)
    tc_max: int = 0  # Maximum TC setting available
    tc_cut: int = -1  # TC engine power cut level (-1 if unavailable)
    tc_cut_max: int = 0  # Maximum TC cut setting
    tc_slip: int = -1  # TC slip angle allowance level (-1 if unavailable)
    tc_slip_max: int = 0  # Maximum TC slip setting

    abs_level: int = -1  # ABS level (-1 if unavailable, 0=off or 1..abs_max)
    abs_max: int = 0  # Maximum ABS setting available

    motor_map: int = -1  # Engine / Motor power map level (-1 if unavailable)
    motor_map_max: int = 0  # Maximum motor map setting

    brake_migration: int = -1  # Dynamic brake migration level (-1 if unavailable)
    brake_migration_max: int = 0  # Maximum brake migration setting

    front_arb: int = -1  # Onboard adjustable front anti-roll bar level (-1 if unavailable)
    front_arb_max: int = 0  # Maximum front ARB setting
    rear_arb: int = -1  # Onboard adjustable rear anti-roll bar level (-1 if unavailable)
    rear_arb_max: int = 0  # Maximum rear ARB setting

    wiper_state: int = 0  # Windshield wiper state (0=off, 1=auto, 2=slow, 3=fast)
    lift_and_coast: float = 0.0  # Lift and coast target progress (fraction: 0.0 to 1.0)

    @property
    def has_tc(self) -> bool:
        """Whether the vehicle is equipped with onboard Traction Control."""
        return self.tc_max > 0

    @property
    def has_abs(self) -> bool:
        """Whether the vehicle is equipped with onboard Anti-lock Braking System."""
        return self.abs_max > 0

    @property
    def has_motor_map(self) -> bool:
        """Whether the vehicle has adjustable engine / motor maps."""
        return self.motor_map_max > 0

    @property
    def has_brake_migration(self) -> bool:
        """Whether the vehicle has adjustable brake migration."""
        return self.brake_migration_max > 0
