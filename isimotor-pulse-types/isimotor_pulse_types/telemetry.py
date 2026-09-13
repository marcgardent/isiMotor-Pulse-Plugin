"""
High-frequency vehicle and wheel telemetry data models.
"""

from dataclasses import dataclass, field

from .common import TelemVect3
from .ecu import EcuState
from .enums import (
    GEAR_NEUTRAL,
    GEAR_REVERSE,
    KELVIN_TO_CELSIUS_OFFSET,
    MS_TO_KMH,
    ElectricBoostMotorState,
    IgnitionStarterState,
    RearFlapLegalStatus,
    SpeedLimiterState,
    SurfaceType,
)
from .lmu import LMUTelemetryExtension, LMUWheelExtension


@dataclass
class TelemWheel:
    """
    Wheel and tire telemetry for an individual wheel (TelemWheelV01).
    Struct size: 260 bytes (#pragma pack(4)).
    """

    suspension_deflection: float = 0.0
    """Meters."""
    ride_height: float = 0.0
    """Meters."""
    susp_force: float = 0.0
    """Pushrod load in Newtons."""
    brake_temp: float = 0.0
    """Celsius."""
    brake_pressure: float = 0.0
    """0.0 to 1.0 depending on input and brake balance."""

    rotation: float = 0.0
    """Radians/sec."""
    lateral_patch_vel: float = 0.0
    """Lateral velocity at contact patch (m/s)."""
    longitudinal_patch_vel: float = 0.0
    """Longitudinal velocity at contact patch (m/s)."""
    lateral_ground_vel: float = 0.0
    """Lateral ground velocity at contact patch (m/s)."""
    longitudinal_ground_vel: float = 0.0
    """Longitudinal ground velocity at contact patch (m/s)."""
    camber: float = 0.0
    """Radians (positive is left for left-side wheels, right for right-side wheels)."""
    lateral_force: float = 0.0
    """Newtons."""
    longitudinal_force: float = 0.0
    """Newtons."""
    tire_load: float = 0.0
    """Newtons."""

    grip_fraction: float = 0.0
    """An approximation of what fraction of the contact patch is sliding (0.0-1.0)."""
    pressure: float = 0.0
    """kPa (tire pressure)."""
    temperature: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Kelvin: left/center/right (not inside/center/outside!)."""
    wear: float = 0.0
    """Wear (0.0-1.0, fraction of maximum)."""
    terrain_name: str = ""
    """Material prefix from the TDF file (up to 16 chars)."""
    surface_type: int = SurfaceType.DRY
    """See `SurfaceType`."""
    flat: bool = False
    """Whether tire is flat."""
    detached: bool = False
    """Whether wheel is detached."""
    static_undeflected_radius: int = 0
    """Tire radius in centimeters."""

    vertical_tire_deflection: float = 0.0
    """Tire deflection from its speed-sensitive radius."""
    wheel_y_location: float = 0.0
    """Wheel's y location relative to vehicle y location."""
    toe: float = 0.0
    """Current toe angle w.r.t vehicle (radians)."""

    tire_carcass_temperature: float = 0.0
    """Rough average temperature of carcass (Kelvin)."""
    tire_inner_layer_temperature: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Kelvin: rubber before carcass."""

    # Le Mans Ultimate wheel telemetry extensions (compound enum, brake wear)
    lmu: LMUWheelExtension = field(default_factory=LMUWheelExtension)

    # Convenience properties
    @property
    def temperature_celsius(self) -> tuple[float, float, float]:
        """Tire surface temperatures in Celsius (left, center, right)."""
        return (
            self.temperature[0] - KELVIN_TO_CELSIUS_OFFSET,
            self.temperature[1] - KELVIN_TO_CELSIUS_OFFSET,
            self.temperature[2] - KELVIN_TO_CELSIUS_OFFSET,
        )

    @property
    def carcass_temp_celsius(self) -> float:
        """Tire carcass temperature in Celsius."""
        return self.tire_carcass_temperature - KELVIN_TO_CELSIUS_OFFSET

    @property
    def patch_speed_kmh(self) -> float:
        """Longitudinal contact patch speed in km/h."""
        return self.longitudinal_patch_vel * MS_TO_KMH

    @property
    def ground_speed_kmh(self) -> float:
        """Longitudinal ground surface speed in km/h."""
        return self.longitudinal_ground_vel * MS_TO_KMH

    @property
    def slip_ratio(self) -> float:
        """Longitudinal tire slip ratio ((patch - ground) / ground)."""
        if abs(self.longitudinal_ground_vel) < 1e-4:
            return 0.0
        return (self.longitudinal_patch_vel - self.longitudinal_ground_vel) / self.longitudinal_ground_vel


# Alias for backward-compatibility
WheelInfo = TelemWheel


@dataclass
class TelemInfo:
    """
    High-frequency raw physics and vehicle telemetry (TelemInfoV01).
    Total binary size: 1888 bytes (#pragma pack(4)).
    """

    slot_id: int = 0
    """Vehicle slot ID (mID)."""
    delta_time: float = 0.0
    """Time passed since last update."""
    elapsed_time: float = 0.0
    """Current session elapsed time."""
    lap_number: int = 0
    """Current lap number."""
    lap_start_et: float = 0.0
    """Time at start of current lap."""
    vehicle_name: str = ""
    """Vehicle name (up to 64 chars)."""
    track_name: str = ""
    """Track name (up to 64 chars)."""

    pos: TelemVect3 = field(default_factory=TelemVect3)
    """World position (meters)."""
    local_vel: TelemVect3 = field(default_factory=TelemVect3)
    """Local velocity (m/s)."""
    local_accel: TelemVect3 = field(default_factory=TelemVect3)
    """Local acceleration (m/s^2)."""
    ori: tuple[TelemVect3, TelemVect3, TelemVect3] = (
        TelemVect3(1, 0, 0),
        TelemVect3(0, 1, 0),
        TelemVect3(0, 0, 1),
    )
    """3x3 orientation matrix."""
    local_rot: TelemVect3 = field(default_factory=TelemVect3)
    """Rotation (rad/s)."""
    local_rot_accel: TelemVect3 = field(default_factory=TelemVect3)
    """Rotational acceleration (rad/s^2)."""

    gear: int = GEAR_NEUTRAL
    """GEAR_REVERSE (-1), GEAR_NEUTRAL (0), or 1+ for forward gears."""
    engine_rpm: float = 0.0
    """Engine RPM."""
    engine_water_temp: float = 0.0
    """Celsius."""
    engine_oil_temp: float = 0.0
    """Celsius."""
    clutch_rpm: float = 0.0
    """Clutch RPM."""

    unfiltered_throttle: float = 0.0
    """0.0 - 1.0 (raw input)."""
    unfiltered_brake: float = 0.0
    """0.0 - 1.0 (raw input)."""
    unfiltered_steering: float = 0.0
    """-1.0 (full left) to +1.0 (full right)."""
    unfiltered_clutch: float = 0.0
    """0.0 - 1.0 (raw input)."""

    filtered_throttle: float = 0.0
    """0.0 - 1.0 (after driving aids)."""
    filtered_brake: float = 0.0
    """0.0 - 1.0 (after driving aids)."""
    filtered_steering: float = 0.0
    """-1.0 to +1.0 (after driving aids)."""
    filtered_clutch: float = 0.0
    """0.0 - 1.0 (after driving aids)."""

    steering_shaft_torque: float = 0.0
    """Torque on steering shaft (Nm)."""
    front_3rd_deflection: float = 0.0
    """Front heave / 3rd element deflection (m)."""
    rear_3rd_deflection: float = 0.0
    """Rear heave / 3rd element deflection (m)."""

    front_wing_height: float = 0.0
    """Front wing height (m)."""
    front_ride_height: float = 0.0
    """Front ride height (m)."""
    rear_ride_height: float = 0.0
    """Rear ride height (m)."""
    drag: float = 0.0
    """Total aerodynamic drag (N)."""
    front_downforce: float = 0.0
    """Front aerodynamic downforce (N)."""
    rear_downforce: float = 0.0
    """Rear aerodynamic downforce (N)."""

    fuel: float = 0.0
    """Current fuel in liters."""
    engine_max_rpm: float = 0.0
    """Rev limiter RPM."""
    scheduled_stops: int = 0
    """Planned pit stops."""
    overheating: bool = False
    """Engine overheating flag."""
    detached: bool = False
    """Severed component flag."""
    headlights: bool = False
    """Headlights active."""
    dent_severity: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0, 0)
    """8 body sectors."""

    last_impact_et: float = 0.0
    """Time of most recent impact (seconds)."""
    last_impact_magnitude: float = 0.0
    """Impact magnitude (N)."""
    last_impact_pos: TelemVect3 = field(default_factory=TelemVect3)
    """Impact location."""

    engine_torque: float = 0.0
    """Current output torque (Nm)."""
    current_sector: int = 1
    """1=Sector 1, 2=Sector 2, 3=Sector 3."""
    speed_limiter: int = SpeedLimiterState.OFF
    """See `SpeedLimiterState` (pit limiter)."""
    max_gears: int = 6
    """Forward gear count."""
    front_tire_compound_index: int = 0
    rear_tire_compound_index: int = 0
    fuel_capacity: float = 0.0
    """Fuel tank max capacity (liters)."""
    front_flap_activated: int = 0
    rear_flap_activated: int = 0
    """DRS / active aero."""
    rear_flap_legal_status: int = RearFlapLegalStatus.DISALLOWED
    """See `RearFlapLegalStatus` (DRS)."""
    ignition_starter: int = IgnitionStarterState.OFF
    """See `IgnitionStarterState`."""
    front_tire_compound_name: str = ""
    rear_tire_compound_name: str = ""

    speed_limiter_available: int = 0
    anti_stall_activated: int = 0
    visual_steering_wheel_range: float = 0.0
    rear_brake_bias: float = 0.5
    """Fraction of brake force on rear."""
    turbo_boost_pressure: float = 0.0
    physics_to_graphics_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    physical_steering_wheel_range: float = 0.0
    battery_charge_fraction: float = 0.0
    """Hybrid battery state [0.0 - 1.0]."""

    # Electric boost motor (Hypercar / Hybrid / Formula E)
    electric_boost_motor_torque: float = 0.0
    electric_boost_motor_rpm: float = 0.0
    electric_boost_motor_temperature: float = 0.0
    electric_boost_water_temperature: float = 0.0
    electric_boost_motor_state: int = ElectricBoostMotorState.UNAVAILABLE
    """See `ElectricBoostMotorState`."""

    # Le Mans Ultimate telemetry extensions (ECU, Hypercar virtual energy, regen, track cuts)
    lmu: LMUTelemetryExtension = field(default_factory=LMUTelemetryExtension)

    # Wheels (FL, FR, RL, RR)
    wheels: tuple[TelemWheel, TelemWheel, TelemWheel, TelemWheel] = (
        TelemWheel(),
        TelemWheel(),
        TelemWheel(),
        TelemWheel(),
    )

    # Convenience properties
    @property
    def ecu(self) -> EcuState:
        """Convenience property accessing the LMU/onboard ECU and driver aids state."""
        return self.lmu.ecu

    @property
    def speed_mps(self) -> float:
        """Vehicle 3D absolute speed in meters per second."""
        return self.local_vel.magnitude

    @property
    def speed_kmh(self) -> float:
        """Vehicle 3D absolute speed in km/h."""
        return self.speed_mps * MS_TO_KMH

    @property
    def forward_speed_mps(self) -> float:
        """Forward speed along car longitudinal axis in m/s (ISO +x = isiMotor -z)."""
        return -self.local_vel.z

    @property
    def forward_speed_kmh(self) -> float:
        """Forward speed in km/h."""
        return self.forward_speed_mps * MS_TO_KMH

    @property
    def gear_str(self) -> str:
        """Human-readable gear label ('R', 'N', '1', '2', etc.)."""
        if self.gear == GEAR_REVERSE:
            return "R"
        elif self.gear == GEAR_NEUTRAL:
            return "N"
        return str(self.gear)

    @property
    def fl_wheel(self) -> TelemWheel:
        """Front-Left wheel telemetry."""
        return self.wheels[0]

    @property
    def fr_wheel(self) -> TelemWheel:
        """Front-Right wheel telemetry."""
        return self.wheels[1]

    @property
    def rl_wheel(self) -> TelemWheel:
        """Rear-Left wheel telemetry."""
        return self.wheels[2]

    @property
    def rr_wheel(self) -> TelemWheel:
        """Rear-Right wheel telemetry."""
        return self.wheels[3]
