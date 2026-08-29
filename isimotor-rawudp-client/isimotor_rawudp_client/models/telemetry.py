"""
High-frequency vehicle and wheel telemetry data models.
"""

from dataclasses import dataclass, field

from .common import TelemVect3


@dataclass
class TelemWheel:
    """
    Wheel and tire telemetry for an individual wheel (TelemWheelV01).
    Struct size: 260 bytes (#pragma pack(4)).
    """

    suspension_deflection: float = 0.0  # meters
    ride_height: float = 0.0  # meters
    susp_force: float = 0.0  # pushrod load in Newtons
    brake_temp: float = 0.0  # Celsius
    brake_pressure: float = 0.0  # 0.0 to 1.0 depending on input and brake balance

    rotation: float = 0.0  # radians/sec
    lateral_patch_vel: float = 0.0  # lateral velocity at contact patch (m/s)
    longitudinal_patch_vel: float = 0.0  # longitudinal velocity at contact patch (m/s)
    lateral_ground_vel: float = 0.0  # lateral ground velocity at contact patch (m/s)
    longitudinal_ground_vel: float = 0.0  # longitudinal ground velocity at contact patch (m/s)
    camber: float = 0.0  # radians (positive is left for left-side wheels, right for right-side wheels)
    lateral_force: float = 0.0  # Newtons
    longitudinal_force: float = 0.0  # Newtons
    tire_load: float = 0.0  # Newtons

    grip_fraction: float = 0.0  # an approximation of what fraction of the contact patch is sliding (0.0-1.0)
    pressure: float = 0.0  # kPa (tire pressure)
    temperature: tuple[float, float, float] = (0.0, 0.0, 0.0)  # Kelvin: left/center/right (not inside/center/outside!)
    wear: float = 0.0  # wear (0.0-1.0, fraction of maximum)
    terrain_name: str = ""  # material prefix from the TDF file (up to 16 chars)
    surface_type: int = 0  # 0=dry, 1=wet, 2=grass, 3=dirt, 4=gravel, 5=rumblestrip, 6=special
    flat: bool = False  # whether tire is flat
    detached: bool = False  # whether wheel is detached
    static_undeflected_radius: int = 0  # tire radius in centimeters

    vertical_tire_deflection: float = 0.0  # tire deflection from its speed-sensitive radius
    wheel_y_location: float = 0.0  # wheel's y location relative to vehicle y location
    toe: float = 0.0  # current toe angle w.r.t vehicle (radians)

    tire_carcass_temperature: float = 0.0  # rough average temperature of carcass (Kelvin)
    tire_inner_layer_temperature: tuple[float, float, float] = (0.0, 0.0, 0.0)  # Kelvin: rubber before carcass

    # Convenience properties
    @property
    def temperature_celsius(self) -> tuple[float, float, float]:
        """Tire surface temperatures in Celsius (left, center, right)."""
        return (self.temperature[0] - 273.15, self.temperature[1] - 273.15, self.temperature[2] - 273.15)

    @property
    def carcass_temp_celsius(self) -> float:
        """Tire carcass temperature in Celsius."""
        return self.tire_carcass_temperature - 273.15

    @property
    def patch_speed_kmh(self) -> float:
        """Longitudinal contact patch speed in km/h."""
        return self.longitudinal_patch_vel * 3.6

    @property
    def ground_speed_kmh(self) -> float:
        """Longitudinal ground surface speed in km/h."""
        return self.longitudinal_ground_vel * 3.6

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

    slot_id: int = 0  # Vehicle slot ID (mID)
    delta_time: float = 0.0  # Time passed since last update
    elapsed_time: float = 0.0  # Current session elapsed time
    lap_number: int = 0  # Current lap number
    lap_start_et: float = 0.0  # Time at start of current lap
    vehicle_name: str = ""  # Vehicle name (up to 64 chars)
    track_name: str = ""  # Track name (up to 64 chars)

    pos: TelemVect3 = field(default_factory=TelemVect3)  # World position (meters)
    local_vel: TelemVect3 = field(default_factory=TelemVect3)  # Local velocity (m/s)
    local_accel: TelemVect3 = field(default_factory=TelemVect3)  # Local acceleration (m/s^2)
    ori: tuple[TelemVect3, TelemVect3, TelemVect3] = (  # 3x3 Orientation Matrix
        TelemVect3(1, 0, 0),
        TelemVect3(0, 1, 0),
        TelemVect3(0, 0, 1),
    )
    local_rot: TelemVect3 = field(default_factory=TelemVect3)  # Rotation (rad/s)
    local_rot_accel: TelemVect3 = field(default_factory=TelemVect3)  # Rotational acceleration (rad/s^2)

    gear: int = 0  # -1=Reverse, 0=Neutral, 1+=Forward
    engine_rpm: float = 0.0  # Engine RPM
    engine_water_temp: float = 0.0  # Celsius
    engine_oil_temp: float = 0.0  # Celsius
    clutch_rpm: float = 0.0  # Clutch RPM

    unfiltered_throttle: float = 0.0  # 0.0 - 1.0 (raw input)
    unfiltered_brake: float = 0.0  # 0.0 - 1.0 (raw input)
    unfiltered_steering: float = 0.0  # -1.0 (full left) to +1.0 (full right)
    unfiltered_clutch: float = 0.0  # 0.0 - 1.0 (raw input)

    filtered_throttle: float = 0.0  # 0.0 - 1.0 (after driving aids)
    filtered_brake: float = 0.0  # 0.0 - 1.0 (after driving aids)
    filtered_steering: float = 0.0  # -1.0 to +1.0 (after driving aids)
    filtered_clutch: float = 0.0  # 0.0 - 1.0 (after driving aids)

    steering_shaft_torque: float = 0.0  # Torque on steering shaft (Nm)
    front_3rd_deflection: float = 0.0  # Front heave / 3rd element deflection (m)
    rear_3rd_deflection: float = 0.0  # Rear heave / 3rd element deflection (m)

    front_wing_height: float = 0.0  # Front wing height (m)
    front_ride_height: float = 0.0  # Front ride height (m)
    rear_ride_height: float = 0.0  # Rear ride height (m)
    drag: float = 0.0  # Total aerodynamic drag (N)
    front_downforce: float = 0.0  # Front aerodynamic downforce (N)
    rear_downforce: float = 0.0  # Rear aerodynamic downforce (N)

    fuel: float = 0.0  # Current fuel in liters
    engine_max_rpm: float = 0.0  # Rev limiter RPM
    scheduled_stops: int = 0  # Planned pit stops
    overheating: bool = False  # Engine overheating flag
    detached: bool = False  # Severed component flag
    headlights: bool = False  # Headlights active
    dent_severity: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0, 0)  # 8 body sectors

    last_impact_et: float = 0.0  # Time of most recent impact (seconds)
    last_impact_magnitude: float = 0.0  # Impact magnitude (N)
    last_impact_pos: TelemVect3 = field(default_factory=TelemVect3)  # Impact location

    engine_torque: float = 0.0  # Current output torque (Nm)
    current_sector: int = 1  # 1=Sector 1, 2=Sector 2, 3=Sector 3
    speed_limiter: int = 0  # 0=off, 1=on (pit limiter)
    max_gears: int = 6  # Forward gear count
    front_tire_compound_index: int = 0
    rear_tire_compound_index: int = 0
    fuel_capacity: float = 0.0  # Fuel tank max capacity (liters)
    front_flap_activated: int = 0
    rear_flap_activated: int = 0  # DRS / active aero
    rear_flap_legal_status: int = 0  # 0=disallowed, 1=detected, 2=allowed (DRS enabled)
    ignition_starter: int = 0  # 0=off, 1=ignition, 2=ignition+starter
    front_tire_compound_name: str = ""
    rear_tire_compound_name: str = ""

    speed_limiter_available: int = 0
    anti_stall_activated: int = 0
    visual_steering_wheel_range: float = 0.0
    rear_brake_bias: float = 0.5  # fraction of brake force on rear
    turbo_boost_pressure: float = 0.0
    physics_to_graphics_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    physical_steering_wheel_range: float = 0.0
    battery_charge_fraction: float = 0.0  # Hybrid battery state [0.0 - 1.0]

    # Electric boost motor (Hypercar / Hybrid / Formula E)
    electric_boost_motor_torque: float = 0.0
    electric_boost_motor_rpm: float = 0.0
    electric_boost_motor_temperature: float = 0.0
    electric_boost_water_temperature: float = 0.0
    electric_boost_motor_state: int = 0  # 0=unavailable, 1=inactive, 2=propulsion, 3=regeneration

    # Wheels (FL, FR, RL, RR)
    wheels: tuple[TelemWheel, TelemWheel, TelemWheel, TelemWheel] = (
        TelemWheel(),
        TelemWheel(),
        TelemWheel(),
        TelemWheel(),
    )

    # Convenience properties
    @property
    def speed_mps(self) -> float:
        """Vehicle 3D absolute speed in meters per second."""
        return self.local_vel.magnitude

    @property
    def speed_kmh(self) -> float:
        """Vehicle 3D absolute speed in km/h."""
        return self.speed_mps * 3.6

    @property
    def forward_speed_mps(self) -> float:
        """Forward speed along car longitudinal axis in m/s (ISO +x = isiMotor -z)."""
        return -self.local_vel.z

    @property
    def forward_speed_kmh(self) -> float:
        """Forward speed in km/h."""
        return self.forward_speed_mps * 3.6

    @property
    def gear_str(self) -> str:
        """Human-readable gear label ('R', 'N', '1', '2', etc.)."""
        if self.gear == -1:
            return "R"
        elif self.gear == 0:
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
