"""
Track rules, yellow flag procedures, and safety car decoders.
"""

import struct
from typing import Optional, List
from ..constants import (
    TRACK_RULES_PARTICIPANT_SIZE,
    TRACK_RULES_PARTICIPANT_STRUCT,
    TRACK_RULES_SESSION_SIZE,
    TRACK_RULES_SESSION_STRUCT,
)
from ..models import TrackRulesParticipant, TrackRulesSession
from .base import _decode_string


def decode_track_rules_participant(
    data: bytes, offset: int = 0
) -> TrackRulesParticipant:
    """Decodes a 140-byte TrackRulesParticipant struct at specified offset."""
    (
        slot_id,
        frozen_order,
        place,
        yellow_severity,
        current_rel_dist,
        rel_laps,
        col_assign,
        pos_assign,
        pits_open,
        up_to_speed,
        goal_rel_dist,
        raw_msg,
    ) = struct.unpack_from(TRACK_RULES_PARTICIPANT_STRUCT, data, offset)

    return TrackRulesParticipant(
        id=slot_id,
        frozen_order=frozen_order,
        place=place,
        yellow_severity=yellow_severity,
        current_relative_distance=current_rel_dist,
        relative_laps=rel_laps,
        column_assignment=col_assign,
        position_assignment=pos_assign,
        pits_open=pits_open,
        up_to_speed=up_to_speed,
        goal_relative_distance=goal_rel_dist,
        message=_decode_string(raw_msg),
    )


def decode_track_rules(data: bytes, offset: int = 0) -> Optional[TrackRulesSession]:
    """
    Decodes full TrackRulesSession packet (Type 5).
    Header: 192 bytes, followed by N * 140 bytes of participant records.
    """
    if len(data) - offset < TRACK_RULES_SESSION_SIZE:
        return None

    (
        current_et,
        stage,
        pole_col,
        num_actions,
        num_participants,
        yellow_detected,
        yellow_overridden,
        sc_exists,
        sc_active,
        sc_laps,
        sc_threshold,
        sc_lap_dist,
        sc_lap_dist_start,
        pit_lane_start_dist,
        teleport_lap_dist,
        yellow_flag_state,
        yellow_flag_laps,
        sc_instruction,
        sc_speed,
        sc_min_spacing,
        sc_max_spacing,
        min_col_spacing,
        max_col_spacing,
        min_speed,
        max_speed,
        raw_msg,
    ) = struct.unpack_from(TRACK_RULES_SESSION_STRUCT, data, offset)

    participants: List[TrackRulesParticipant] = []
    part_offset = offset + TRACK_RULES_SESSION_SIZE
    valid_count = max(0, min(num_participants, 128))

    for _ in range(valid_count):
        if part_offset + TRACK_RULES_PARTICIPANT_SIZE <= len(data):
            participants.append(decode_track_rules_participant(data, part_offset))
            part_offset += TRACK_RULES_PARTICIPANT_SIZE
        else:
            break

    return TrackRulesSession(
        current_et=current_et,
        stage=stage,
        pole_column=pole_col,
        num_actions=num_actions,
        num_participants=num_participants,
        yellow_flag_detected=yellow_detected,
        yellow_flag_laps_overridden=yellow_overridden,
        safety_car_exists=sc_exists,
        safety_car_active=sc_active,
        safety_car_laps=sc_laps,
        safety_car_threshold=sc_threshold,
        safety_car_lap_dist=sc_lap_dist,
        safety_car_lap_dist_at_start=sc_lap_dist_start,
        pit_lane_start_dist=pit_lane_start_dist,
        teleport_lap_dist=teleport_lap_dist,
        yellow_flag_state=yellow_flag_state,
        yellow_flag_laps=yellow_flag_laps,
        safety_car_instruction=sc_instruction,
        safety_car_speed=sc_speed,
        safety_car_minimum_spacing=sc_min_spacing,
        safety_car_maximum_spacing=sc_max_spacing,
        minimum_column_spacing=min_col_spacing,
        maximum_column_spacing=max_col_spacing,
        minimum_speed=min_speed,
        maximum_speed=max_speed,
        message=_decode_string(raw_msg),
        participants=participants,
    )
