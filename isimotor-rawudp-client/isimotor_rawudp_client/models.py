"""
Data models and wrapped structures for isiMotor-RawUDP-Plugin telemetry.

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

from dataclasses import dataclass
from typing import Tuple, Optional
import math


@dataclass(frozen=True)
class TelemVect3:
    """3D Vector in isiMotor coordinates (meters or rad/s or m/s)."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @property
    def magnitude(self) -> float:
        """Euclidean norm / magnitude of the vector."""
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class TelemWheel:
    """
    Wheel and tire telemetry for an individual wheel (TelemWheelV01).
    Struct size: 260 bytes (#pragma pack(4)).
    """
    suspension_deflection: float = 0.0     # meters
    ride_height: float = 0.0               # meters
    susp_force: float = 0.0                # pushrod load in Newtons
    brake_temp: float = 0.0                # Celsius
    brake_pressure: float = 0.0            # 0.0 to 1.0 depending on input and brake balance

    rotation: float = 0.0                  # radians/sec
    lateral_patch_vel: float = 0.0         # lateral velocity at contact patch (m/s)
    longitudinal_patch_vel: float = 0.0    # longitudinal velocity at contact patch (m/s)
    lateral_ground_vel: float = 0.0        # lateral ground velocity at contact patch (m/s)
    longitudinal_ground_vel: float = 0.0   # longitudinal ground velocity at contact patch (m/s)
    camber: float = 0.0                    # radians (positive is left for left-side wheels, right for right-side wheels)
    lateral_force: float = 0.0             # Newtons
    longitudinal_force: float = 0.0        # Newtons
    tire_load: float = 0.0                 # Newtons

    grip_fraction: float = 0.0             # an approximation of what fraction of the contact patch is sliding (0.0-1.0)
    pressure: float = 0.0                  # kPa (tire pressure)
    temperature: Tuple[float, float, float] = (0.0, 0.0, 0.0) # Kelvin: left/center/right (not inside/center/outside!)
    wear: float = 0.0                      # wear (0.0-1.0, fraction of maximum)
    terrain_name: str = ""                 # material prefix from the TDF file (up to 16 chars)
    surface_type: int = 0                  # 0=dry, 1=wet, 2=grass, 3=dirt, 4=gravel, 5=rumblestrip, 6=special
    flat: bool = False                     # whether tire is flat
    detached: bool = False                 # whether wheel is detached
    static_undeflected_radius: int = 0     # tire radius in centimeters

    vertical_tire_deflection: float = 0.0  # tire deflection from its speed-sensitive radius
    wheel_y_location: float = 0.0          # wheel's y location relative to vehicle y location
    toe: float = 0.0                       # current toe angle w.r.t vehicle (radians)

    tire_carcass_temperature: float = 0.0  # rough average temperature of carcass (Kelvin)
    tire_inner_layer_temperature: Tuple[float, float, float] = (0.0, 0.0, 0.0) # Kelvin: rubber before carcass

    # Convenience properties
    @property
    def temperature_celsius(self) -> Tuple[float, float, float]:
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
        """Longitudinal ground speed in km/h."""
        return self.longitudinal_ground_vel * 3.6

    @property
    def slip_ratio(self) -> float:
        """Longitudinal slip ratio ((patch_vel - ground_vel) / max(ground_vel, 1.0))."""
        denom = max(abs(self.longitudinal_ground_vel), 1.0)
        return (self.longitudinal_patch_vel - self.longitudinal_ground_vel) / denom


@dataclass
class TelemInfo:
    """
    Complete physical vehicle telemetry frame (TelemInfoV01).
    Direct native memory dump from isiMotor / LMU / rFactor 2.
    Struct size: 1904 bytes (#pragma pack(4)).
    """
    # Time & Session
    slot_id: int = 0                       # slot ID (can be re-used in multiplayer)
    delta_time: float = 0.0                # time since last update in seconds
    elapsed_time: float = 0.0              # game session time in seconds
    lap_number: int = 0                    # current lap number
    lap_start_et: float = 0.0              # session time this lap was started
    vehicle_name: str = ""                 # current vehicle name
    track_name: str = ""                   # current track name

    # Position and derivatives (isiMotor coordinate system)
    pos: TelemVect3 = TelemVect3()         # world position in meters
    local_vel: TelemVect3 = TelemVect3()   # velocity (m/s) in local vehicle coordinates (+x left, +y up, +z rear)
    local_accel: TelemVect3 = TelemVect3() # acceleration (m/s^2) in local vehicle coordinates

    # Orientation and derivatives
    ori: Tuple[TelemVect3, TelemVect3, TelemVect3] = (TelemVect3(), TelemVect3(), TelemVect3()) # 3x3 orientation matrix
    local_rot: TelemVect3 = TelemVect3()       # rotation (rad/s) in local coordinates (+x pitch up, +y yaw right, +z roll right)
    local_rot_accel: TelemVect3 = TelemVect3() # rotational acceleration (rad/s^2)

    # Vehicle status
    gear: int = 0                          # -1=reverse, 0=neutral, 1+=forward gears
    engine_rpm: float = 0.0                # engine RPM
    engine_water_temp: float = 0.0         # Celsius
    engine_oil_temp: float = 0.0           # Celsius
    clutch_rpm: float = 0.0                # clutch RPM

    # Driver input (unfiltered)
    unfiltered_throttle: float = 0.0       # 0.0 to 1.0
    unfiltered_brake: float = 0.0          # 0.0 to 1.0
    unfiltered_steering: float = 0.0       # -1.0 to 1.0 (left to right)
    unfiltered_clutch: float = 0.0         # 0.0 to 1.0

    # Filtered input (speed sensitive steering, TC, ABS, etc.)
    filtered_throttle: float = 0.0         # 0.0 to 1.0
    filtered_brake: float = 0.0            # 0.0 to 1.0
    filtered_steering: float = 0.0         # -1.0 to 1.0
    filtered_clutch: float = 0.0           # 0.0 to 1.0

    # Misc mechanics
    steering_shaft_torque: float = 0.0     # torque around steering shaft
    front_3rd_deflection: float = 0.0      # deflection at front 3rd spring (m)
    rear_3rd_deflection: float = 0.0       # deflection at rear 3rd spring (m)

    # Aerodynamics
    front_wing_height: float = 0.0         # meters
    front_ride_height: float = 0.0         # meters
    rear_ride_height: float = 0.0          # meters
    drag: float = 0.0                      # aerodynamic drag force
    front_downforce: float = 0.0           # front aerodynamic downforce
    rear_downforce: float = 0.0            # rear aerodynamic downforce

    # State & damage info
    fuel: float = 0.0                      # remaining fuel in liters
    engine_max_rpm: float = 7500.0         # rev limiter RPM
    scheduled_stops: int = 0               # number of scheduled pitstops
    overheating: bool = False              # whether overheating icon is shown
    detached: bool = False                 # whether any parts are detached
    headlights: bool = False               # whether headlights are active
    dent_severity: Tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0, 0) # dent severity at 8 body locations (0=none..2)
    last_impact_et: float = 0.0            # time of last impact
    last_impact_magnitude: float = 0.0     # magnitude of last impact
    last_impact_pos: TelemVect3 = TelemVect3() # location of last impact

    # Expanded fields
    engine_torque: float = 0.0             # current engine torque
    current_sector: int = 0                # current sector (zero-based; pitlane stored in sign bit: 0x80000002)
    speed_limiter: int = 0                 # speed limiter active flag
    max_gears: int = 6                     # maximum forward gears
    front_tire_compound_index: int = 0     # front tire compound index
    rear_tire_compound_index: int = 0      # rear tire compound index
    fuel_capacity: float = 100.0           # fuel tank capacity in liters
    front_flap_activated: int = 0
    rear_flap_activated: int = 0
    rear_flap_legal_status: int = 0        # 0=disallowed, 1=criteria detected, 2=allowed
    ignition_starter: int = 0              # 0=off, 1=ignition, 2=ignition+starter
    front_tire_compound_name: str = ""
    rear_tire_compound_name: str = ""
    speed_limiter_available: int = 0
    anti_stall_activated: int = 0
    visual_steering_wheel_range: float = 0.0
    rear_brake_bias: float = 0.5           # fraction of brake force on rear
    turbo_boost_pressure: float = 0.0
    physics_to_graphics_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    physical_steering_wheel_range: float = 0.0
    battery_charge_fraction: float = 0.0   # Hybrid battery state [0.0 - 1.0]

    # Electric boost motor (Hypercar / Hybrid / Formula E)
    electric_boost_motor_torque: float = 0.0
    electric_boost_motor_rpm: float = 0.0
    electric_boost_motor_temperature: float = 0.0
    electric_boost_water_temperature: float = 0.0
    electric_boost_motor_state: int = 0    # 0=unavailable, 1=inactive, 2=propulsion, 3=regeneration

    # Wheels (FL, FR, RL, RR)
    wheels: Tuple[TelemWheel, TelemWheel, TelemWheel, TelemWheel] = (
        TelemWheel(), TelemWheel(), TelemWheel(), TelemWheel()
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


@dataclass
class CompactScoring:
    """
    Compact scoring and timing update (SIMP Type 2, 176 bytes).
    Updated at 1-5 Hz.
    """
    track_name: str = ""                   # Track name string
    session: int = 0                       # 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race
    current_et: float = 0.0                # Current session elapsed time in seconds
    lap_dist: float = 0.0                  # Track total lap distance in meters
    max_laps: int = 0                      # Session maximum laps
    in_realtime: bool = True               # True if currently in active driving mode
    total_laps: int = 0                    # Player completed laps
    sector: int = 1                        # Current sector: 0=sector3, 1=sector1, 2=sector2
    in_garage_stall: bool = False          # True if inside pit garage
    count_lap_flag: int = 2                # 0=invalid lap, 1=lap count only, 2=valid lap and time

    cur_sector1: float = 0.0               # Current sector 1 time (seconds)
    cur_sector2: float = 0.0               # Current sector 2 cumulative time (S1 + S2)
    last_sector1: float = 0.0              # Last lap sector 1 time
    last_sector2: float = 0.0              # Last lap sector 2 cumulative time
    last_lap_time: float = 0.0             # Last lap total time
    best_sector1: float = 0.0              # Personal best sector 1 time
    best_sector2: float = 0.0              # Personal best sector 2 cumulative time
    best_lap_time: float = 0.0             # Personal best lap time

    @property
    def cur_sector2_individual(self) -> float:
        """Current Sector 2 standalone duration (S2_cum - S1)."""
        return max(0.0, self.cur_sector2 - self.cur_sector1) if self.cur_sector2 > 0 and self.cur_sector1 > 0 else 0.0

    @property
    def last_sector2_individual(self) -> float:
        """Last lap Sector 2 standalone duration."""
        return max(0.0, self.last_sector2 - self.last_sector1) if self.last_sector2 > 0 and self.last_sector1 > 0 else 0.0

    @property
    def last_sector3_individual(self) -> float:
        """Last lap Sector 3 standalone duration (LastLap - S2_cum)."""
        return max(0.0, self.last_lap_time - self.last_sector2) if self.last_lap_time > 0 and self.last_sector2 > 0 else 0.0

    @property
    def is_race_session(self) -> bool:
        """True if current session is a race."""
        return 10 <= self.session <= 13

    @property
    def is_qualifying_session(self) -> bool:
        """True if current session is qualifying."""
        return 5 <= self.session <= 8


@dataclass(frozen=True)
class SystemEvent:
    """
    System state event packet (SIMP Type 3, 6 bytes).
    """
    event_id: int = 0                      # 1=EnterRealtime, 2=ExitRealtime, 3=StartSession, 4=EndSession

    @property
    def name(self) -> str:
        names = {
            1: "EnterRealtime",
            2: "ExitRealtime",
            3: "StartSession",
            4: "EndSession"
        }
        return names.get(self.event_id, f"Unknown({self.event_id})")

    @property
    def in_realtime(self) -> Optional[bool]:
        if self.event_id in (1, 3):
            return True
        elif self.event_id in (2, 4):
            return False
        return None
