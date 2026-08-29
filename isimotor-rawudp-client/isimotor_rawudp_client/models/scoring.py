"""
Scoring, leaderboard, timing and session data models.
"""

from dataclasses import dataclass, field

from .common import TelemVect3


@dataclass
class CompactScoring:
    """
    Compact scoring and timing update (SIMP Type 2, 168 bytes).
    Updated at 1-5 Hz.
    """

    track_name: str = ""  # Track name string
    session: int = 0  # 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race
    current_et: float = 0.0  # Current session elapsed time in seconds
    lap_dist: float = 0.0  # Track total lap distance in meters
    max_laps: int = 0  # Session maximum laps
    in_realtime: bool = True  # True if currently in active driving mode
    total_laps: int = 0  # Player completed laps
    sector: int = 1  # Current sector: 0=sector3, 1=sector1, 2=sector2
    in_garage_stall: bool = False  # True if inside pit garage
    count_lap_flag: int = 2  # 0=invalid lap, 1=lap count only, 2=valid lap and time

    cur_sector1: float = 0.0  # Current sector 1 time (seconds)
    cur_sector2: float = 0.0  # Current sector 2 cumulative time (S1 + S2)
    last_sector1: float = 0.0  # Last lap sector 1 time
    last_sector2: float = 0.0  # Last lap sector 2 cumulative time
    last_lap_time: float = 0.0  # Last lap total time
    best_sector1: float = 0.0  # Personal best sector 1 time
    best_sector2: float = 0.0  # Personal best sector 2 cumulative time
    best_lap_time: float = 0.0  # Personal best lap time

    @property
    def cur_sector2_individual(self) -> float:
        """Current Sector 2 standalone duration (S2_cum - S1)."""
        return max(0.0, self.cur_sector2 - self.cur_sector1) if self.cur_sector2 > 0 and self.cur_sector1 > 0 else 0.0

    @property
    def last_sector2_individual(self) -> float:
        """Last lap Sector 2 standalone duration."""
        return (
            max(0.0, self.last_sector2 - self.last_sector1) if self.last_sector2 > 0 and self.last_sector1 > 0 else 0.0
        )

    @property
    def last_sector3_individual(self) -> float:
        """Last lap Sector 3 standalone duration (LastLap - S2_cum)."""
        return (
            max(0.0, self.last_lap_time - self.last_sector2)
            if self.last_lap_time > 0 and self.last_sector2 > 0
            else 0.0
        )

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

    id: int = 0  # Slot ID
    driver_name: str = ""  # Driver name (up to 32 chars)
    vehicle_name: str = ""  # Vehicle / livery name (up to 64 chars)
    total_laps: int = 0  # Completed laps
    sector: int = 0  # 0=S3, 1=S1, 2=S2
    finish_status: int = 0  # 0=none, 1=finished, 2=dnf, 3=dq
    lap_dist: float = 0.0  # Track distance along path (meters)
    path_lateral: float = 0.0  # Lateral distance from path center (+left, -right)
    track_edge: float = 0.0  # Distance to track edge

    best_sector1: float = 0.0  # Personal best S1
    best_sector2: float = 0.0  # Personal best S2 (cumulative S1+S2)
    best_lap_time: float = 0.0  # Personal best lap time
    last_sector1: float = 0.0  # Last lap S1
    last_sector2: float = 0.0  # Last lap S2 (cumulative S1+S2)
    last_lap_time: float = 0.0  # Last lap time
    cur_sector1: float = 0.0  # Current lap S1
    cur_sector2: float = 0.0  # Current lap S2 (cumulative S1+S2)

    num_pitstops: int = 0  # Pit stop count
    num_penalties: int = 0  # Outstanding penalties count
    is_player: bool = False  # 1 if local player car
    control: int = 0  # -1=nobody, 0=player, 1=AI, 2=remote, 3=replay
    in_pits: bool = False  # Pitting / in pit lane
    place: int = 1  # Overall position (1-based)
    vehicle_class: str = ""  # Car class (e.g. "Hypercar", "LMP2", "LMGT3")

    time_behind_next: float = 0.0  # Time behind car in next higher place
    laps_behind_next: int = 0  # Laps behind car in next higher place
    time_behind_leader: float = 0.0  # Time behind race leader
    laps_behind_leader: int = 0  # Laps behind race leader
    lap_start_et: float = 0.0  # ET when this lap was started

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

    headlights: int = 0  # Headlights state
    pit_state: int = 0  # 0=none, 1=request, 2=entering, 3=stopped, 4=exiting
    server_scored: int = 1
    individual_phase: int = 0
    qualification: int = 0  # Qualifying position (1-based)
    time_into_lap: float = 0.0  # Estimated time elapsed in current lap
    estimated_lap_time: float = 0.0  # Estimated full lap time

    pit_group: str = ""  # Pit stall / team group
    flag: int = 0  # Primary flag (0=green, 6=blue)
    under_yellow: bool = False  # Taken caution flag
    count_lap_flag: int = 2  # 0=invalid, 1=lap count only, 2=valid lap & time
    in_garage_stall: bool = False
    pit_lap_dist: float = 0.0  # Distance of pit stall along lap
    best_lap_sector1: float = 0.0  # S1 from best overall lap
    best_lap_sector2: float = 0.0  # S2 from best overall lap

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
        return (
            max(0.0, self.last_sector2 - self.last_sector1) if self.last_sector2 > 0 and self.last_sector1 > 0 else 0.0
        )

    @property
    def last_sector3_individual(self) -> float:
        """Last lap standalone Sector 3 time."""
        return (
            max(0.0, self.last_lap_time - self.last_sector2)
            if self.last_lap_time > 0 and self.last_sector2 > 0
            else 0.0
        )

    @property
    def best_sector2_individual(self) -> float:
        """Best standalone Sector 2 time."""
        return (
            max(0.0, self.best_sector2 - self.best_sector1) if self.best_sector2 > 0 and self.best_sector1 > 0 else 0.0
        )

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

    track_name: str = ""  # Track name
    session: int = 0  # 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race
    current_et: float = 0.0  # Current session elapsed time in seconds
    end_et: float = 0.0  # End session time (seconds)
    max_laps: int = 0  # Max session laps
    lap_dist: float = 0.0  # Track total lap distance in meters
    num_vehicles: int = 0  # Number of active vehicles in grid
    game_phase: int = 5  # 0=Garage..5=GreenFlag, 6=FCY..8=SessionOver
    yellow_flag_state: int = (
        0  # -1=Invalid, 0=None, 1=Pending, 2=PitClosed, 3=PitLeadLap, 4=PitOpen, 5=LastLap, 6=Resume
    )
    sector_flags: tuple[int, int, int] = (0, 0, 0)  # Local yellows in S3, S1, S2
    start_light: int = 0
    num_red_lights: int = 0
    in_realtime: bool = True
    player_name: str = ""
    plr_file_name: str = ""
    dark_cloud: float = 0.0
    raining: float = 0.0
    ambient_temp: float = 0.0  # Celsius
    track_temp: float = 0.0  # Celsius
    wind: TelemVect3 = field(default_factory=TelemVect3)
    min_path_wetness: float = 0.0
    max_path_wetness: float = 0.0
    avg_path_wetness: float = 0.0
    vehicles: list[VehicleScoring] = field(default_factory=list)

    @property
    def player_vehicle(self) -> VehicleScoring | None:
        """Finds the local player vehicle in the grid."""
        for v in self.vehicles:
            if v.is_player or v.control == 0:
                return v
        return self.vehicles[0] if self.vehicles else None

    @property
    def leaderboard(self) -> list[VehicleScoring]:
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
            8: "SessionOver",
        }
        return phases.get(self.game_phase, f"Phase_{self.game_phase}")
