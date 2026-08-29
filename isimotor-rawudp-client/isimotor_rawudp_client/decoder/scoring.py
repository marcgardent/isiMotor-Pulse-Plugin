"""
Scoring, timing, and multi-vehicle leaderboard decoders.
"""

import struct

from ..constants import (
    COMPACT_SCORING_SIZE,
    FULL_SCORING_SESSION_SIZE,
    VEHICLE_SCORING_SIZE,
)
from ..models import CompactScoring, FullScoringSession, TelemVect3, VehicleScoring
from .base import _decode_string


def decode_compact_scoring(data: bytes, offset: int = 0) -> CompactScoring | None:
    """Decodes a 168-byte SIMP Type 2 compact scoring packet."""
    if len(data) - offset < COMPACT_SCORING_SIZE:
        return None

    # Check magic if starting at 0
    if offset == 0 and data.startswith(b"SIMP") and len(data) >= 5 and data[4] == 2:
        # SIMP Type 2 compact scoring layout
        track = _decode_string(data[5:69])
        session = struct.unpack_from("<i", data, 72)[0]
        current_et = struct.unpack_from("<d", data, 76)[0]
        lap_dist = struct.unpack_from("<d", data, 84)[0]
        max_laps = struct.unpack_from("<i", data, 92)[0]
        in_rt = bool(data[96])
        total_laps = struct.unpack_from("<h", data, 98)[0]
        sector = struct.unpack_from("<b", data, 100)[0]
        in_garage = bool(data[101])
        count_lap_flag = data[102]

        cur_s1 = struct.unpack_from("<d", data, 104)[0]
        cur_s2 = struct.unpack_from("<d", data, 112)[0]
        last_s1 = struct.unpack_from("<d", data, 120)[0]
        last_s2 = struct.unpack_from("<d", data, 128)[0]
        last_lap = struct.unpack_from("<d", data, 136)[0]
        best_s1 = struct.unpack_from("<d", data, 144)[0]
        best_s2 = struct.unpack_from("<d", data, 152)[0]
        best_lap = struct.unpack_from("<d", data, 160)[0]
    else:
        # Standard payload unpacking
        track = _decode_string(data[offset + 5 : offset + 69])
        session = struct.unpack_from("<i", data, offset + 72)[0]
        current_et = struct.unpack_from("<d", data, offset + 76)[0]
        lap_dist = struct.unpack_from("<d", data, offset + 84)[0]
        max_laps = struct.unpack_from("<i", data, offset + 92)[0]
        in_rt = bool(data[offset + 96])
        total_laps = struct.unpack_from("<h", data, offset + 98)[0]
        sector = struct.unpack_from("<b", data, offset + 100)[0]
        in_garage = bool(data[offset + 101])
        count_lap_flag = data[offset + 102]

        cur_s1 = struct.unpack_from("<d", data, offset + 104)[0]
        cur_s2 = struct.unpack_from("<d", data, offset + 112)[0]
        last_s1 = struct.unpack_from("<d", data, offset + 120)[0]
        last_s2 = struct.unpack_from("<d", data, offset + 128)[0]
        last_lap = struct.unpack_from("<d", data, offset + 136)[0]
        best_s1 = struct.unpack_from("<d", data, offset + 144)[0]
        best_s2 = struct.unpack_from("<d", data, offset + 152)[0]
        best_lap = struct.unpack_from("<d", data, offset + 160)[0]

    return CompactScoring(
        track_name=track,
        session=session,
        current_et=current_et,
        lap_dist=lap_dist,
        max_laps=max_laps,
        in_realtime=in_rt,
        total_laps=total_laps,
        sector=sector,
        in_garage_stall=in_garage,
        count_lap_flag=count_lap_flag,
        cur_sector1=cur_s1,
        cur_sector2=cur_s2,
        last_sector1=last_s1,
        last_sector2=last_s2,
        last_lap_time=last_lap,
        best_sector1=best_s1,
        best_sector2=best_s2,
        best_lap_time=best_lap,
    )


def decode_vehicle_scoring(data: bytes, offset: int = 0) -> VehicleScoring:
    """Decodes a 584-byte VehicleScoringInfoV01 record."""
    v_id = struct.unpack_from("<i", data, offset + 0)[0]
    driver_name = _decode_string(data[offset + 4 : offset + 36])
    veh_name = _decode_string(data[offset + 36 : offset + 100])
    total_laps = struct.unpack_from("<h", data, offset + 100)[0]
    sector = struct.unpack_from("<b", data, offset + 102)[0]
    finish_status = struct.unpack_from("<b", data, offset + 103)[0]
    lap_dist = struct.unpack_from("<d", data, offset + 104)[0]
    path_lateral = struct.unpack_from("<d", data, offset + 112)[0]
    track_edge = struct.unpack_from("<d", data, offset + 120)[0]

    best_s1 = struct.unpack_from("<d", data, offset + 128)[0]
    best_s2 = struct.unpack_from("<d", data, offset + 136)[0]
    best_lap = struct.unpack_from("<d", data, offset + 144)[0]
    last_s1 = struct.unpack_from("<d", data, offset + 152)[0]
    last_s2 = struct.unpack_from("<d", data, offset + 160)[0]
    last_lap = struct.unpack_from("<d", data, offset + 168)[0]
    cur_s1 = struct.unpack_from("<d", data, offset + 176)[0]
    cur_s2 = struct.unpack_from("<d", data, offset + 184)[0]

    num_pitstops = struct.unpack_from("<h", data, offset + 192)[0]
    num_penalties = struct.unpack_from("<h", data, offset + 194)[0]
    is_player = bool(data[offset + 196])
    control = struct.unpack_from("<b", data, offset + 197)[0]
    in_pits = bool(data[offset + 198])
    place = data[offset + 199]
    veh_class = _decode_string(data[offset + 200 : offset + 232])

    time_behind_next = struct.unpack_from("<d", data, offset + 232)[0]
    laps_behind_next = struct.unpack_from("<i", data, offset + 240)[0]
    time_behind_leader = struct.unpack_from("<d", data, offset + 244)[0]
    laps_behind_leader = struct.unpack_from("<i", data, offset + 252)[0]
    lap_start_et = struct.unpack_from("<d", data, offset + 256)[0]

    pos = TelemVect3(*struct.unpack_from("<ddd", data, offset + 264))
    local_vel = TelemVect3(*struct.unpack_from("<ddd", data, offset + 288))
    local_accel = TelemVect3(*struct.unpack_from("<ddd", data, offset + 312))

    r0 = TelemVect3(*struct.unpack_from("<ddd", data, offset + 336))
    r1 = TelemVect3(*struct.unpack_from("<ddd", data, offset + 360))
    r2 = TelemVect3(*struct.unpack_from("<ddd", data, offset + 384))
    ori = (r0, r1, r2)

    local_rot = TelemVect3(*struct.unpack_from("<ddd", data, offset + 408))
    local_rot_accel = TelemVect3(*struct.unpack_from("<ddd", data, offset + 432))

    headlights = data[offset + 456]
    pit_state = data[offset + 457]
    server_scored = data[offset + 458]
    individual_phase = data[offset + 459]
    qualification = struct.unpack_from("<i", data, offset + 460)[0]
    time_into_lap = struct.unpack_from("<d", data, offset + 464)[0]
    estimated_lap_time = struct.unpack_from("<d", data, offset + 472)[0]

    pit_group = _decode_string(data[offset + 480 : offset + 504])
    flag = data[offset + 504]
    under_yellow = bool(data[offset + 505])
    count_lap_flag = data[offset + 506]
    in_garage = bool(data[offset + 507])
    pit_lap_dist = struct.unpack_from("<f", data, offset + 524)[0]
    best_lap_s1 = struct.unpack_from("<f", data, offset + 528)[0]
    best_lap_s2 = struct.unpack_from("<f", data, offset + 532)[0]

    return VehicleScoring(
        id=v_id,
        driver_name=driver_name,
        vehicle_name=veh_name,
        total_laps=total_laps,
        sector=sector,
        finish_status=finish_status,
        lap_dist=lap_dist,
        path_lateral=path_lateral,
        track_edge=track_edge,
        best_sector1=best_s1,
        best_sector2=best_s2,
        best_lap_time=best_lap,
        last_sector1=last_s1,
        last_sector2=last_s2,
        last_lap_time=last_lap,
        cur_sector1=cur_s1,
        cur_sector2=cur_s2,
        num_pitstops=num_pitstops,
        num_penalties=num_penalties,
        is_player=is_player,
        control=control,
        in_pits=in_pits,
        place=place,
        vehicle_class=veh_class,
        time_behind_next=time_behind_next,
        laps_behind_next=laps_behind_next,
        time_behind_leader=time_behind_leader,
        laps_behind_leader=laps_behind_leader,
        lap_start_et=lap_start_et,
        pos=pos,
        local_vel=local_vel,
        local_accel=local_accel,
        ori=ori,
        local_rot=local_rot,
        local_rot_accel=local_rot_accel,
        headlights=headlights,
        pit_state=pit_state,
        server_scored=server_scored,
        individual_phase=individual_phase,
        qualification=qualification,
        time_into_lap=time_into_lap,
        estimated_lap_time=estimated_lap_time,
        pit_group=pit_group,
        flag=flag,
        under_yellow=under_yellow,
        count_lap_flag=count_lap_flag,
        in_garage_stall=in_garage,
        pit_lap_dist=pit_lap_dist,
        best_lap_sector1=best_lap_s1,
        best_lap_sector2=best_lap_s2,
    )


def decode_full_scoring(data: bytes, offset: int = 0) -> FullScoringSession | None:
    """Decodes a FullScoringSession packet along with all embedded vehicle records."""
    if len(data) - offset < FULL_SCORING_SESSION_SIZE:
        return None

    track_name = _decode_string(data[offset + 0 : offset + 64])
    session = struct.unpack_from("<i", data, offset + 64)[0]
    current_et = struct.unpack_from("<d", data, offset + 68)[0]
    end_et = struct.unpack_from("<d", data, offset + 76)[0]
    max_laps = struct.unpack_from("<i", data, offset + 84)[0]
    lap_dist = struct.unpack_from("<d", data, offset + 88)[0]
    num_vehicles = struct.unpack_from("<i", data, offset + 96)[0]
    game_phase = data[offset + 100]
    yellow_flag_state = struct.unpack_from("<b", data, offset + 101)[0]
    sector_flags = struct.unpack_from("<bbb", data, offset + 102)
    start_light = data[offset + 105]
    num_red_lights = data[offset + 106]
    in_realtime = bool(data[offset + 107])
    player_name = _decode_string(data[offset + 108 : offset + 140])
    plr_file_name = _decode_string(data[offset + 140 : offset + 204])

    dark_cloud = struct.unpack_from("<d", data, offset + 204)[0]
    raining = struct.unpack_from("<d", data, offset + 212)[0]
    ambient_temp = struct.unpack_from("<d", data, offset + 220)[0]
    track_temp = struct.unpack_from("<d", data, offset + 228)[0]
    wind = TelemVect3(*struct.unpack_from("<ddd", data, offset + 236))
    min_path_wetness = struct.unpack_from("<d", data, offset + 260)[0]
    max_path_wetness = struct.unpack_from("<d", data, offset + 268)[0]
    avg_path_wetness = struct.unpack_from("<d", data, offset + 276)[0]

    vehicles: list[VehicleScoring] = []
    v_base = offset + FULL_SCORING_SESSION_SIZE
    for i in range(num_vehicles):
        v_offset = v_base + (i * VEHICLE_SCORING_SIZE)
        if len(data) - v_offset < VEHICLE_SCORING_SIZE:
            break
        vehicles.append(decode_vehicle_scoring(data, v_offset))

    return FullScoringSession(
        track_name=track_name,
        session=session,
        current_et=current_et,
        end_et=end_et,
        max_laps=max_laps,
        lap_dist=lap_dist,
        num_vehicles=len(vehicles),
        game_phase=game_phase,
        yellow_flag_state=yellow_flag_state,
        sector_flags=sector_flags,
        start_light=start_light,
        num_red_lights=num_red_lights,
        in_realtime=in_realtime,
        player_name=player_name,
        plr_file_name=plr_file_name,
        dark_cloud=dark_cloud,
        raining=raining,
        ambient_temp=ambient_temp,
        track_temp=track_temp,
        wind=wind,
        min_path_wetness=min_path_wetness,
        max_path_wetness=max_path_wetness,
        avg_path_wetness=avg_path_wetness,
        vehicles=vehicles,
    )
