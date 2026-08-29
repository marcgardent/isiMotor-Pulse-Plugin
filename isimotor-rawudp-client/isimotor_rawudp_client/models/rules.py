"""
Track rules, yellow flag procedures, and safety car data models.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TrackRulesParticipant:
    """
    Per-vehicle track order and yellow flag rules state (140 bytes).
    """

    id: int = 0  # Slot ID
    frozen_order: int = -1  # 0-based place when caution was called
    place: int = 0  # 1-based place
    yellow_severity: float = 0.0  # Vehicle contribution to yellow flag severity
    current_relative_distance: float = 0.0  # Distance relative to track start/safety car
    relative_laps: int = 0  # Laps relative to safety car
    column_assignment: int = 5  # 0=left, 1=midleft, 2=middle, 3=midright, 4=right, 5=invalid, 6=freechoice, 7=pending
    position_assignment: int = -1  # 0-based position within column
    pits_open: int = 2  # 0=false, 1=true, 2=false, 3=true
    up_to_speed: bool = True  # Vehicle can be safely followed
    goal_relative_distance: float = 0.0  # Target distance behind leader/car ahead
    message: str = ""  # Participant instruction message (e.g. "Follow Car #7")

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
            7: "Pending",
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
    stage: int = 2  # 0=formation_init, 1=formation_update, 2=normal, 3=caution_init, 4=caution_update
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
    safety_car_instruction: int = 0  # 0=none, 1=active, 2=head for pits
    safety_car_speed: float = 0.0  # Max speed in m/s
    safety_car_minimum_spacing: float = -1.0
    safety_car_maximum_spacing: float = -1.0
    minimum_column_spacing: float = -1.0
    maximum_column_spacing: float = -1.0
    minimum_speed: float = -1.0
    maximum_speed: float = -1.0
    message: str = ""
    participants: list[TrackRulesParticipant] = field(default_factory=list)

    @property
    def stage_str(self) -> str:
        stages = {
            0: "Formation Init",
            1: "Formation Update",
            2: "Normal",
            3: "Caution Init",
            4: "Caution Update",
        }
        return stages.get(self.stage, f"Stage({self.stage})")

    @property
    def pole_column_str(self) -> str:
        cols = {0: "Left", 1: "Mid-Left", 2: "Middle", 3: "Mid-Right", 4: "Right"}
        return cols.get(self.pole_column, f"Col({self.pole_column})")

    @property
    def is_safety_car_active(self) -> bool:
        return self.safety_car_active

    @property
    def is_caution_active(self) -> bool:
        return self.stage in (3, 4) or self.yellow_flag_detected or self.yellow_flag_state > 0
