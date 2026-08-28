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

from dataclasses import dataclass, field
from typing import Tuple, List, Optional
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


@dataclass(frozen=True)
class RawUdpHeader:
    """
    Standard 24-byte UDP packet header (SIMP protocol).
    """
    magic: bytes = b"SIMP"
    protocol_version: int = 1
    packet_type: int = 0
    payload_size: int = 0
    sequence_number: int = 0
    session_et: float = 0.0
    chunk_index: int = 0
    total_chunks: int = 1
    sub_type_or_id: int = 0


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


@dataclass
class TelemInfo:
    """
    High-frequency raw physics and vehicle telemetry (TelemInfoV01).
    Total binary size: 1888 bytes (#pragma pack(4)).
    """
    slot_id: int = 0                       # Vehicle slot ID (mID)
    delta_time: float = 0.0                # Time passed since last update
    elapsed_time: float = 0.0              # Current session elapsed time
    lap_number: int = 0                    # Current lap number
    lap_start_et: float = 0.0              # Time at start of current lap
    vehicle_name: str = ""                 # Vehicle name (up to 64 chars)
    track_name: str = ""                   # Track name (up to 64 chars)

    pos: TelemVect3 = field(default_factory=TelemVect3)           # World position (meters)
    local_vel: TelemVect3 = field(default_factory=TelemVect3)     # Local velocity (m/s)
    local_accel: TelemVect3 = field(default_factory=TelemVect3)   # Local acceleration (m/s^2)
    ori: Tuple[TelemVect3, TelemVect3, TelemVect3] = (            # 3x3 Orientation Matrix
        TelemVect3(1, 0, 0), TelemVect3(0, 1, 0), TelemVect3(0, 0, 1)
    )
    local_rot: TelemVect3 = field(default_factory=TelemVect3)     # Rotation (rad/s)
    local_rot_accel: TelemVect3 = field(default_factory=TelemVect3) # Rotational acceleration (rad/s^2)

    gear: int = 0                          # -1=Reverse, 0=Neutral, 1+=Forward
    engine_rpm: float = 0.0                # Engine RPM
    engine_water_temp: float = 0.0         # Celsius
    engine_oil_temp: float = 0.0           # Celsius
    clutch_rpm: float = 0.0                # Clutch RPM

    unfiltered_throttle: float = 0.0       # 0.0 - 1.0 (raw input)
    unfiltered_brake: float = 0.0          # 0.0 - 1.0 (raw input)
    unfiltered_steering: float = 0.0       # -1.0 (full left) to +1.0 (full right)
    unfiltered_clutch: float = 0.0         # 0.0 - 1.0 (raw input)

    filtered_throttle: float = 0.0         # 0.0 - 1.0 (after driving aids)
    filtered_brake: float = 0.0            # 0.0 - 1.0 (after driving aids)
    filtered_steering: float = 0.0         # -1.0 to +1.0 (after driving aids)
    filtered_clutch: float = 0.0           # 0.0 - 1.0 (after driving aids)

    steering_shaft_torque: float = 0.0     # Torque on steering shaft (Nm)
    front_3rd_deflection: float = 0.0      # Front heave / 3rd element deflection (m)
    rear_3rd_deflection: float = 0.0       # Rear heave / 3rd element deflection (m)

    front_wing_height: float = 0.0         # Front wing height (m)
    front_ride_height: float = 0.0         # Front ride height (m)
    rear_ride_height: float = 0.0          # Rear ride height (m)
    drag: float = 0.0                      # Total aerodynamic drag (N)
    front_downforce: float = 0.0           # Front aerodynamic downforce (N)
    rear_downforce: float = 0.0            # Rear aerodynamic downforce (N)

    fuel: float = 0.0                      # Current fuel in liters
    engine_max_rpm: float = 0.0            # Rev limiter RPM
    scheduled_stops: int = 0               # Planned pit stops
    overheating: bool = False              # Engine overheating flag
    detached: bool = False                 # Severed component flag
    headlights: bool = False               # Headlights active
    dent_severity: Tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0, 0) # 8 body sectors

    last_impact_et: float = 0.0            # Time of most recent impact (seconds)
    last_impact_magnitude: float = 0.0     # Impact magnitude (N)
    last_impact_pos: TelemVect3 = field(default_factory=TelemVect3) # Impact location

    engine_torque: float = 0.0             # Current output torque (Nm)
    current_sector: int = 1                # 1=Sector 1, 2=Sector 2, 3=Sector 3
    speed_limiter: int = 0                 # 0=off, 1=on (pit limiter)
    max_gears: int = 6                     # Forward gear count
    front_tire_compound_index: int = 0
    rear_tire_compound_index: int = 0
    fuel_capacity: float = 0.0             # Fuel tank max capacity (liters)
    front_flap_activated: int = 0
    rear_flap_activated: int = 0           # DRS / active aero
    rear_flap_legal_status: int = 0        # 0=disallowed, 1=detected, 2=allowed (DRS enabled)
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
    Compact scoring and timing update (SIMP Type 2, 168 bytes).
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


@dataclass
class VehicleScoring:
    """
    Individual vehicle scoring & timing entry (VehicleScoringInfoV01).
    Struct size: 584 bytes (#pragma pack(4)).
    """
    id: int = 0                            # Slot ID
    driver_name: str = ""                  # Driver name (up to 32 chars)
    vehicle_name: str = ""                 # Vehicle / livery name (up to 64 chars)
    total_laps: int = 0                    # Completed laps
    sector: int = 0                        # 0=S3, 1=S1, 2=S2
    finish_status: int = 0                 # 0=none, 1=finished, 2=dnf, 3=dq
    lap_dist: float = 0.0                  # Track distance along path (meters)
    path_lateral: float = 0.0              # Lateral distance from path center (+left, -right)
    track_edge: float = 0.0                # Distance to track edge

    best_sector1: float = 0.0              # Personal best S1
    best_sector2: float = 0.0              # Personal best S2 (cumulative S1+S2)
    best_lap_time: float = 0.0             # Personal best lap time
    last_sector1: float = 0.0              # Last lap S1
    last_sector2: float = 0.0              # Last lap S2 (cumulative S1+S2)
    last_lap_time: float = 0.0             # Last lap time
    cur_sector1: float = 0.0               # Current lap S1
    cur_sector2: float = 0.0               # Current lap S2 (cumulative S1+S2)

    num_pitstops: int = 0                  # Pit stop count
    num_penalties: int = 0                 # Outstanding penalties count
    is_player: bool = False                # 1 if local player car
    control: int = 0                       # -1=nobody, 0=player, 1=AI, 2=remote, 3=replay
    in_pits: bool = False                  # Pitting / in pit lane
    place: int = 1                         # Overall position (1-based)
    vehicle_class: str = ""                # Car class (e.g. "Hypercar", "LMP2", "LMGT3")

    time_behind_next: float = 0.0          # Time behind car in next higher place
    laps_behind_next: int = 0              # Laps behind car in next higher place
    time_behind_leader: float = 0.0        # Time behind race leader
    laps_behind_leader: int = 0            # Laps behind race leader
    lap_start_et: float = 0.0              # ET when this lap was started

    pos: TelemVect3 = field(default_factory=TelemVect3)           # World position (meters)
    local_vel: TelemVect3 = field(default_factory=TelemVect3)     # Local velocity (m/s)
    local_accel: TelemVect3 = field(default_factory=TelemVect3)   # Local acceleration (m/s^2)
    ori: Tuple[TelemVect3, TelemVect3, TelemVect3] = (            # 3x3 Orientation Matrix
        TelemVect3(1, 0, 0), TelemVect3(0, 1, 0), TelemVect3(0, 0, 1)
    )
    local_rot: TelemVect3 = field(default_factory=TelemVect3)     # Rotation (rad/s)
    local_rot_accel: TelemVect3 = field(default_factory=TelemVect3) # Rotational acceleration (rad/s^2)

    headlights: int = 0                    # Headlights state
    pit_state: int = 0                     # 0=none, 1=request, 2=entering, 3=stopped, 4=exiting
    server_scored: int = 1
    individual_phase: int = 0
    qualification: int = 0                 # Qualifying position (1-based)
    time_into_lap: float = 0.0             # Estimated time elapsed in current lap
    estimated_lap_time: float = 0.0        # Estimated full lap time

    pit_group: str = ""                    # Pit stall / team group
    flag: int = 0                          # Primary flag (0=green, 6=blue)
    under_yellow: bool = False             # Taken caution flag
    count_lap_flag: int = 2                # 0=invalid, 1=lap count only, 2=valid lap & time
    in_garage_stall: bool = False
    pit_lap_dist: float = 0.0              # Distance of pit stall along lap
    best_lap_sector1: float = 0.0          # S1 from best overall lap
    best_lap_sector2: float = 0.0          # S2 from best overall lap

    # Convenience properties
    @property
    def speed_mps(self) -> float:
        """Speed in m/s."""
        return self.local_vel.magnitude

    @property
    def speed_kmh(self) -> float:
        """Speed in km/h."""
        return self.speed_mps * 3.6

    @property
    def forward_speed_mps(self) -> float:
        """Forward speed in m/s (-local_vel.z in isiMotor coordinates)."""
        return -self.local_vel.z

    @property
    def forward_speed_kmh(self) -> float:
        """Forward speed in km/h."""
        return self.forward_speed_mps * 3.6

    @property
    def cur_sector2_individual(self) -> float:
        """Current standalone Sector 2 time."""
        return max(0.0, self.cur_sector2 - self.cur_sector1) if self.cur_sector2 > 0 and self.cur_sector1 > 0 else 0.0

    @property
    def last_sector2_individual(self) -> float:
        """Last lap standalone Sector 2 time."""
        return max(0.0, self.last_sector2 - self.last_sector1) if self.last_sector2 > 0 and self.last_sector1 > 0 else 0.0

    @property
    def last_sector3_individual(self) -> float:
        """Last lap standalone Sector 3 time."""
        return max(0.0, self.last_lap_time - self.last_sector2) if self.last_lap_time > 0 and self.last_sector2 > 0 else 0.0

    @property
    def best_sector2_individual(self) -> float:
        """Best standalone Sector 2 time."""
        return max(0.0, self.best_sector2 - self.best_sector1) if self.best_sector2 > 0 and self.best_sector1 > 0 else 0.0

    @property
    def finish_status_str(self) -> str:
        """Human-readable finish status."""
        statuses = {0: "Running", 1: "Finished", 2: "DNF", 3: "DQ"}
        return statuses.get(self.finish_status, "Unknown")

    @property
    def pit_state_str(self) -> str:
        """Human-readable pit state."""
        states = {0: "On Track", 1: "Pit Request", 2: "Entering Pits", 3: "In Pit Box", 4: "Exiting Pits"}
        return states.get(self.pit_state, "Unknown")


@dataclass
class FullScoringSession:
    """
    Full multi-car scoring & session timing update (SIMP Type 4).
    Contains session weather overview, track conditions, and all active grid vehicles.
    """
    track_name: str = ""                   # Track name
    session: int = 0                       # 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race
    current_et: float = 0.0                # Current session elapsed time in seconds
    end_et: float = 0.0                    # End session time (seconds)
    max_laps: int = 0                      # Max session laps
    lap_dist: float = 0.0                  # Track total lap distance in meters
    num_vehicles: int = 0                  # Number of active vehicles in grid
    game_phase: int = 5                    # 0=Garage..5=GreenFlag, 6=FCY..8=SessionOver
    yellow_flag_state: int = 0             # -1=Invalid, 0=None, 1=Pending, 2=PitClosed, 3=PitLeadLap, 4=PitOpen, 5=LastLap, 6=Resume
    sector_flags: Tuple[int, int, int] = (0, 0, 0) # Local yellows in S3, S1, S2
    start_light: int = 0
    num_red_lights: int = 0
    in_realtime: bool = True
    player_name: str = ""
    plr_file_name: str = ""
    dark_cloud: float = 0.0
    raining: float = 0.0
    ambient_temp: float = 0.0              # Celsius
    track_temp: float = 0.0                # Celsius
    wind: TelemVect3 = field(default_factory=TelemVect3)
    min_path_wetness: float = 0.0
    max_path_wetness: float = 0.0
    avg_path_wetness: float = 0.0
    vehicles: List[VehicleScoring] = field(default_factory=list)

    @property
    def player_vehicle(self) -> Optional[VehicleScoring]:
        """Finds the local player vehicle in the grid."""
        for v in self.vehicles:
            if v.is_player or v.control == 0:
                return v
        return self.vehicles[0] if self.vehicles else None

    @property
    def leaderboard(self) -> List[VehicleScoring]:
        """Returns active vehicles sorted by overall place (1st to last)."""
        return sorted(self.vehicles, key=lambda v: v.place if v.place > 0 else 999)

    @property
    def is_fcy(self) -> bool:
        """True if session is currently under Full Course Yellow / Safety Car."""
        return self.game_phase == 6 or self.yellow_flag_state > 0

    @property
    def is_race(self) -> bool:
        """True if current session is race."""
        return 10 <= self.session <= 13

    @property
    def game_phase_str(self) -> str:
        """Human-readable session phase name."""
        phases = {
            0: "Garage",
            1: "WarmUp",
            2: "GridWalk",
            3: "Formation",
            4: "Countdown",
            5: "GreenFlag",
            6: "FullCourseYellow",
            7: "SessionStopped",
            8: "SessionOver"
        }
        return phases.get(self.game_phase, f"Phase_{self.game_phase}")


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


@dataclass(frozen=True)
class TrackRulesParticipant:
    """
    Per-vehicle track order and yellow flag rules state (140 bytes).
    """
    id: int = 0                            # Slot ID
    frozen_order: int = -1                 # 0-based place when caution was called
    place: int = 0                         # 1-based place
    yellow_severity: float = 0.0           # Vehicle contribution to yellow flag severity
    current_relative_distance: float = 0.0 # Distance relative to track start/safety car
    relative_laps: int = 0                 # Laps relative to safety car
    column_assignment: int = 5             # 0=left, 1=midleft, 2=middle, 3=midright, 4=right, 5=invalid, 6=freechoice, 7=pending
    position_assignment: int = -1          # 0-based position within column
    pits_open: int = 2                     # 0=false, 1=true, 2=false, 3=true
    up_to_speed: bool = True               # Vehicle can be safely followed
    goal_relative_distance: float = 0.0    # Target distance behind leader/car ahead
    message: str = ""                      # Participant instruction message (e.g. "Follow Car #7")

    @property
    def column_str(self) -> str:
        cols = {
            0: "Left Lane",
            1: "Mid-Left Lane",
            2: "Middle Lane",
            3: "Mid-Right Lane",
            4: "Right Lane",
            5: "Invalid/Pits",
            6: "Free Choice",
            7: "Pending"
        }
        return cols.get(self.column_assignment, f"Column({self.column_assignment})")

    @property
    def pits_open_bool(self) -> bool:
        return self.pits_open in (1, 3)


@dataclass(frozen=True)
class TrackRulesSession:
    """
    Full session track rules, safety car state, and frozen order (Type 5).
    """
    current_et: float = 0.0
    stage: int = 2                         # 0=formation_init, 1=formation_update, 2=normal, 3=caution_init, 4=caution_update
    pole_column: int = 0
    num_actions: int = 0
    num_participants: int = 0
    yellow_flag_detected: bool = False
    yellow_flag_laps_overridden: int = 0
    safety_car_exists: bool = False
    safety_car_active: bool = False
    safety_car_laps: int = 0
    safety_car_threshold: float = 0.0
    safety_car_lap_dist: float = 0.0
    safety_car_lap_dist_at_start: float = 0.0
    pit_lane_start_dist: float = 0.0
    teleport_lap_dist: float = 0.0
    yellow_flag_state: int = 0
    yellow_flag_laps: int = 0
    safety_car_instruction: int = 0        # 0=none, 1=active, 2=head for pits
    safety_car_speed: float = 0.0          # Max speed in m/s
    safety_car_minimum_spacing: float = -1.0
    safety_car_maximum_spacing: float = -1.0
    minimum_column_spacing: float = -1.0
    maximum_column_spacing: float = -1.0
    minimum_speed: float = -1.0
    maximum_speed: float = -1.0
    message: str = ""
    participants: List[TrackRulesParticipant] = field(default_factory=list)

    @property
    def stage_str(self) -> str:
        stages = {
            0: "Formation Init",
            1: "Formation Update",
            2: "Normal",
            3: "Caution Init",
            4: "Caution Update"
        }
        return stages.get(self.stage, f"Stage({self.stage})")

    @property
    def pole_column_str(self) -> str:
        cols = {
            0: "Left", 1: "Mid-Left", 2: "Middle", 3: "Mid-Right", 4: "Right"
        }
        return cols.get(self.pole_column, f"Col({self.pole_column})")

    @property
    def is_safety_car_active(self) -> bool:
        return self.safety_car_active

    @property
    def is_caution_active(self) -> bool:
        return self.stage in (3, 4) or self.yellow_flag_detected or self.yellow_flag_state > 0


@dataclass(frozen=True)
class PitMenu:
    """
    Live in-car pit stop menu state (SIMP Type 6, 76 bytes).
    """
    category_index: int = 0
    category_name: str = ""
    choice_index: int = 0
    choice_string: str = ""
    num_choices: int = 0

    @property
    def is_available(self) -> bool:
        return self.num_choices > 0 or len(self.category_name) > 0


@dataclass(frozen=True)
class WeatherControl:
    """
    Environmental conditions & weather node grid (SIMP Type 7, 108 bytes).
    """
    et: float = 0.0
    raining: Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]] = (
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    )
    cloudiness: float = 0.0                # 0.0 (clear) to 1.0 (dark overcast)
    ambient_temp_k: float = 293.15         # Air temp in Kelvin
    wind_max_speed: float = 0.0            # Wind speed in m/s
    apply_cloudiness_instantly: bool = False

    @property
    def ambient_temp_c(self) -> float:
        """Air temperature in Celsius (°C)."""
        return self.ambient_temp_k - 273.15

    @property
    def origin_raining(self) -> float:
        """Rain intensity at origin node [1][1] (0.0 to 1.0)."""
        return self.raining[1][1]
