"""
High-performance binary decoder for isiMotor / LMU / rFactor 2 raw UDP packets.
"""

import struct
from typing import Optional, Union, List, Tuple
from .models import (
    TelemVect3,
    TelemWheel,
    WheelInfo,
    TelemInfo,
    CompactScoring,
    VehicleScoring,
    FullScoringSession,
    TrackRulesParticipant,
    TrackRulesSession,
    PitMenu,
    WeatherControl,
    PhysicsOptions,
    ExtendedState,
    ForceFeedback,
    Graphics,
    SystemEvent,
    RawUdpHeader,
    PitAction,
    HWControlCommand,
    WeatherControlCommand,
)

# ── Packet Size & Struct Constants ─────────────────────────────────────────────
HEADER_SIZE = 24
HEADER_STRUCT = "<4sBBHIdBBH"
SYSTEM_EVENT_SIZE = 6
SYSTEM_EVENT_STRUCT = "<4sBB"

TELEMINFO_SIZE = 1888
COMPACT_SCORING_SIZE = 168
FULL_SCORING_SESSION_SIZE = 284
VEHICLE_SCORING_SIZE = 584

TRACK_RULES_PARTICIPANT_SIZE = 140
TRACK_RULES_PARTICIPANT_STRUCT = "<ihhfdiiiB?2xd96s"

TRACK_RULES_SESSION_SIZE = 192
TRACK_RULES_SESSION_STRUCT = "<diiii?B??ifdfffb1xh4xifffffff96s"

PIT_MENU_SIZE = 76
PIT_MENU_STRUCT = "<i32si32si"

WEATHER_SIZE = 108
WEATHER_STRUCT = "<d9dddd?3x"

EXTENDED_STATE_SIZE = 68
EXTENDED_STATE_STRUCT = "<22B2x4f2d2B2xif"

FORCE_FEEDBACK_SIZE = 8
FORCE_FEEDBACK_STRUCT = "<d"

GRAPHICS_SIZE = 128
GRAPHICS_STRUCT = "<3d9d3dii"

HW_CONTROL_COMMAND_SIZE = 44
HW_CONTROL_COMMAND_STRUCT = "<32sdH2x"

WEATHER_CONTROL_COMMAND_SIZE = 64
WEATHER_CONTROL_COMMAND_STRUCT = "<8d"


def _decode_string(raw_bytes: bytes) -> str:
    """Decodes null-terminated C string."""
    return raw_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")


def decode_header(data: bytes) -> Optional[RawUdpHeader]:
    """Decodes 24-byte standardized SIMP protocol header."""
    if len(data) < HEADER_SIZE or not data.startswith(b"SIMP"):
        return None

    magic, ver, pkt_type, payload_sz, seq, session_et, chunk_idx, total_chunks, sub_id = (
        struct.unpack_from(HEADER_STRUCT, data, 0)
    )
    return RawUdpHeader(
        magic=magic,
        protocol_version=ver,
        packet_type=pkt_type,
        payload_size=payload_sz,
        sequence_number=seq,
        session_et=session_et,
        chunk_index=chunk_idx,
        total_chunks=total_chunks,
        sub_type_or_id=sub_id,
    )


def decode_wheel(data: bytes, offset: int) -> TelemWheel:
    """Decodes a 260-byte TelemWheelV01 struct at specified offset."""
    deflation = struct.unpack_from("<d", data, offset + 0)[0]
    ride_height = struct.unpack_from("<d", data, offset + 8)[0]
    susp_force = struct.unpack_from("<d", data, offset + 16)[0]
    brake_temp = struct.unpack_from("<d", data, offset + 24)[0]
    brake_pressure = struct.unpack_from("<d", data, offset + 32)[0]

    rotation = struct.unpack_from("<d", data, offset + 40)[0]
    lat_patch_vel = struct.unpack_from("<d", data, offset + 48)[0]
    long_patch_vel = struct.unpack_from("<d", data, offset + 56)[0]
    lat_ground_vel = struct.unpack_from("<d", data, offset + 64)[0]
    long_ground_vel = struct.unpack_from("<d", data, offset + 72)[0]
    camber = struct.unpack_from("<d", data, offset + 80)[0]
    lat_force = struct.unpack_from("<d", data, offset + 88)[0]
    long_force = struct.unpack_from("<d", data, offset + 96)[0]
    tire_load = struct.unpack_from("<d", data, offset + 104)[0]

    grip_fract = struct.unpack_from("<d", data, offset + 112)[0]
    pressure = struct.unpack_from("<d", data, offset + 120)[0]
    t0, t1, t2 = struct.unpack_from("<ddd", data, offset + 128)
    wear = struct.unpack_from("<d", data, offset + 152)[0]
    terrain_name = _decode_string(data[offset + 160 : offset + 176])
    surface_type = data[offset + 176]
    flat = bool(data[offset + 177])
    detached = bool(data[offset + 178])
    static_radius = data[offset + 179]

    vert_deflection = struct.unpack_from("<d", data, offset + 180)[0]
    wheel_y = struct.unpack_from("<d", data, offset + 188)[0]
    toe = struct.unpack_from("<d", data, offset + 196)[0]

    carcass_temp = struct.unpack_from("<d", data, offset + 204)[0]
    it0, it1, it2 = struct.unpack_from("<ddd", data, offset + 212)

    return TelemWheel(
        suspension_deflection=deflation,
        ride_height=ride_height,
        susp_force=susp_force,
        brake_temp=brake_temp,
        brake_pressure=brake_pressure,
        rotation=rotation,
        lateral_patch_vel=lat_patch_vel,
        longitudinal_patch_vel=long_patch_vel,
        lateral_ground_vel=lat_ground_vel,
        longitudinal_ground_vel=long_ground_vel,
        camber=camber,
        lateral_force=lat_force,
        longitudinal_force=long_force,
        tire_load=tire_load,
        grip_fraction=grip_fract,
        pressure=pressure,
        temperature=(t0, t1, t2),
        wear=wear,
        terrain_name=terrain_name,
        surface_type=surface_type,
        flat=flat,
        detached=detached,
        static_undeflected_radius=static_radius,
        vertical_tire_deflection=vert_deflection,
        wheel_y_location=wheel_y,
        toe=toe,
        tire_carcass_temperature=carcass_temp,
        tire_inner_layer_temperature=(it0, it1, it2),
    )


def decode_telemetry(data: bytes, offset: int = 0) -> Optional[TelemInfo]:
    """Decodes a 1888-byte native TelemInfoV01 memory dump."""
    if len(data) - offset < TELEMINFO_SIZE:
        return None

    slot_id = struct.unpack_from("<i", data, offset + 0)[0]
    dt = struct.unpack_from("<d", data, offset + 4)[0]
    elapsed = struct.unpack_from("<d", data, offset + 12)[0]
    lap_num = struct.unpack_from("<i", data, offset + 20)[0]
    lap_start_et = struct.unpack_from("<d", data, offset + 24)[0]
    veh_name = _decode_string(data[offset + 32 : offset + 96])
    track_name = _decode_string(data[offset + 96 : offset + 160])

    px, py, pz = struct.unpack_from("<ddd", data, offset + 160)
    pos = TelemVect3(px, py, pz)

    vx, vy, vz = struct.unpack_from("<ddd", data, offset + 184)
    local_vel = TelemVect3(vx, vy, vz)

    ax, ay, az = struct.unpack_from("<ddd", data, offset + 208)
    local_accel = TelemVect3(ax, ay, az)

    # Orientation matrix 3x3
    r0 = TelemVect3(*struct.unpack_from("<ddd", data, offset + 232))
    r1 = TelemVect3(*struct.unpack_from("<ddd", data, offset + 256))
    r2 = TelemVect3(*struct.unpack_from("<ddd", data, offset + 280))
    ori = (r0, r1, r2)

    rx, ry, rz = struct.unpack_from("<ddd", data, offset + 304)
    local_rot = TelemVect3(rx, ry, rz)

    rax, ray, raz = struct.unpack_from("<ddd", data, offset + 328)
    local_rot_accel = TelemVect3(rax, ray, raz)

    gear = struct.unpack_from("<i", data, offset + 352)[0]
    engine_rpm = struct.unpack_from("<d", data, offset + 356)[0]
    water_temp = struct.unpack_from("<d", data, offset + 364)[0]
    oil_temp = struct.unpack_from("<d", data, offset + 372)[0]
    clutch_rpm = struct.unpack_from("<d", data, offset + 380)[0]

    unf_throttle = struct.unpack_from("<d", data, offset + 388)[0]
    unf_brake = struct.unpack_from("<d", data, offset + 396)[0]
    unf_steer = struct.unpack_from("<d", data, offset + 404)[0]
    unf_clutch = struct.unpack_from("<d", data, offset + 412)[0]

    fil_throttle = struct.unpack_from("<d", data, offset + 420)[0]
    fil_brake = struct.unpack_from("<d", data, offset + 428)[0]
    fil_steer = struct.unpack_from("<d", data, offset + 436)[0]
    fil_clutch = struct.unpack_from("<d", data, offset + 444)[0]

    steering_shaft_torque = struct.unpack_from("<d", data, offset + 452)[0]
    front_3rd_defl = struct.unpack_from("<d", data, offset + 460)[0]
    rear_3rd_defl = struct.unpack_from("<d", data, offset + 468)[0]

    front_wing_h = struct.unpack_from("<d", data, offset + 476)[0]
    front_ride_h = struct.unpack_from("<d", data, offset + 484)[0]
    rear_ride_h = struct.unpack_from("<d", data, offset + 492)[0]
    drag = struct.unpack_from("<d", data, offset + 500)[0]
    front_downforce = struct.unpack_from("<d", data, offset + 508)[0]
    rear_downforce = struct.unpack_from("<d", data, offset + 516)[0]

    fuel = struct.unpack_from("<d", data, offset + 524)[0]
    max_rpm = struct.unpack_from("<d", data, offset + 532)[0]
    scheduled_stops = data[offset + 540]
    overheating = bool(data[offset + 541])
    detached = bool(data[offset + 542])
    headlights = bool(data[offset + 543])
    dent_severity = tuple(data[offset + 544 : offset + 552])

    last_impact_et = struct.unpack_from("<d", data, offset + 552)[0]
    last_impact_magnitude = struct.unpack_from("<d", data, offset + 560)[0]
    ix, iy, iz = struct.unpack_from("<ddd", data, offset + 568)
    last_impact_pos = TelemVect3(ix, iy, iz)

    engine_torque = struct.unpack_from("<d", data, offset + 592)[0]
    current_sector = struct.unpack_from("<i", data, offset + 600)[0]
    speed_limiter = data[offset + 604]
    max_gears = data[offset + 605]
    front_tire_compound_idx = data[offset + 606]
    rear_tire_compound_idx = data[offset + 607]
    fuel_capacity = struct.unpack_from("<d", data, offset + 608)[0]
    front_flap_act = data[offset + 616]
    rear_flap_act = data[offset + 617]
    rear_flap_status = data[offset + 618]
    ignition_starter = data[offset + 619]
    front_compound_name = _decode_string(data[offset + 620 : offset + 638])
    rear_compound_name = _decode_string(data[offset + 638 : offset + 656])

    speed_limiter_avail = data[offset + 656]
    anti_stall_act = data[offset + 657]
    visual_steer_range = struct.unpack_from("<f", data, offset + 660)[0]
    rear_brake_bias = struct.unpack_from("<d", data, offset + 664)[0]
    turbo_boost = struct.unpack_from("<d", data, offset + 672)[0]
    p2g_offset = struct.unpack_from("<fff", data, offset + 680)
    physical_steer_range = struct.unpack_from("<f", data, offset + 692)[0]
    battery_charge = struct.unpack_from("<d", data, offset + 696)[0]

    eb_torque = struct.unpack_from("<d", data, offset + 704)[0]
    eb_rpm = struct.unpack_from("<d", data, offset + 712)[0]
    eb_temp = struct.unpack_from("<d", data, offset + 720)[0]
    eb_water_temp = struct.unpack_from("<d", data, offset + 728)[0]
    eb_state = data[offset + 736]

    # Wheels (FL: 848, FR: 1108, RL: 1368, RR: 1628)
    w_fl = decode_wheel(data, offset + 848)
    w_fr = decode_wheel(data, offset + 1108)
    w_rl = decode_wheel(data, offset + 1368)
    w_rr = decode_wheel(data, offset + 1628)

    return TelemInfo(
        slot_id=slot_id,
        delta_time=dt,
        elapsed_time=elapsed,
        lap_number=lap_num,
        lap_start_et=lap_start_et,
        vehicle_name=veh_name,
        track_name=track_name,
        pos=pos,
        local_vel=local_vel,
        local_accel=local_accel,
        ori=ori,
        local_rot=local_rot,
        local_rot_accel=local_rot_accel,
        gear=gear,
        engine_rpm=engine_rpm,
        engine_water_temp=water_temp,
        engine_oil_temp=oil_temp,
        clutch_rpm=clutch_rpm,
        unfiltered_throttle=unf_throttle,
        unfiltered_brake=unf_brake,
        unfiltered_steering=unf_steer,
        unfiltered_clutch=unf_clutch,
        filtered_throttle=fil_throttle,
        filtered_brake=fil_brake,
        filtered_steering=fil_steer,
        filtered_clutch=fil_clutch,
        steering_shaft_torque=steering_shaft_torque,
        front_3rd_deflection=front_3rd_defl,
        rear_3rd_deflection=rear_3rd_defl,
        front_wing_height=front_wing_h,
        front_ride_height=front_ride_h,
        rear_ride_height=rear_ride_h,
        drag=drag,
        front_downforce=front_downforce,
        rear_downforce=rear_downforce,
        fuel=fuel,
        engine_max_rpm=max_rpm,
        scheduled_stops=scheduled_stops,
        overheating=overheating,
        detached=detached,
        headlights=headlights,
        dent_severity=dent_severity,
        last_impact_et=last_impact_et,
        last_impact_magnitude=last_impact_magnitude,
        last_impact_pos=last_impact_pos,
        engine_torque=engine_torque,
        current_sector=current_sector,
        speed_limiter=speed_limiter,
        max_gears=max_gears,
        front_tire_compound_index=front_tire_compound_idx,
        rear_tire_compound_index=rear_tire_compound_idx,
        fuel_capacity=fuel_capacity,
        front_flap_activated=front_flap_act,
        rear_flap_activated=rear_flap_act,
        rear_flap_legal_status=rear_flap_status,
        ignition_starter=ignition_starter,
        front_tire_compound_name=front_compound_name,
        rear_tire_compound_name=rear_compound_name,
        speed_limiter_available=speed_limiter_avail,
        anti_stall_activated=anti_stall_act,
        visual_steering_wheel_range=visual_steer_range,
        rear_brake_bias=rear_brake_bias,
        turbo_boost_pressure=turbo_boost,
        physics_to_graphics_offset=p2g_offset,
        physical_steering_wheel_range=physical_steer_range,
        battery_charge_fraction=battery_charge,
        electric_boost_motor_torque=eb_torque,
        electric_boost_motor_rpm=eb_rpm,
        electric_boost_motor_temperature=eb_temp,
        electric_boost_water_temperature=eb_water_temp,
        electric_boost_motor_state=eb_state,
        wheels=(w_fl, w_fr, w_rl, w_rr),
    )


def decode_compact_scoring(data: bytes, offset: int = 0) -> Optional[CompactScoring]:
    """Decodes a 168-byte SIMP Type 2 compact scoring packet."""
    if len(data) - offset < COMPACT_SCORING_SIZE:
        return None

    # Check magic if starting at 0
    if offset == 0 and data.startswith(b"SIMP") and len(data) >= 5 and data[4] == 2:
        # Legacy SIMP Type 2 layout
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


def decode_full_scoring(data: bytes, offset: int = 0) -> Optional[FullScoringSession]:
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

    vehicles: List[VehicleScoring] = []
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


def decode_pit_menu(data: bytes, offset: int = 0) -> Optional[PitMenu]:
    """Decodes a 76-byte PitMenu packet (Type 6)."""
    if len(data) - offset < PIT_MENU_SIZE:
        return None

    cat_idx, raw_cat_name, choice_idx, raw_choice_str, num_choices = (
        struct.unpack_from(PIT_MENU_STRUCT, data, offset)
    )
    return PitMenu(
        category_index=cat_idx,
        category_name=_decode_string(raw_cat_name),
        choice_index=choice_idx,
        choice_string=_decode_string(raw_choice_str),
        num_choices=num_choices,
    )


def decode_weather(data: bytes, offset: int = 0) -> Optional[WeatherControl]:
    """Decodes a 108-byte WeatherControl packet (Type 7)."""
    if len(data) - offset < WEATHER_SIZE:
        return None

    unpacked = struct.unpack_from(WEATHER_STRUCT, data, offset)
    et = unpacked[0]
    rain_flat = unpacked[1:10]
    cloudiness = unpacked[10]
    ambient_temp_k = unpacked[11]
    wind_max_speed = unpacked[12]
    instant_cloud = unpacked[13]

    raining = (
        (rain_flat[0], rain_flat[1], rain_flat[2]),
        (rain_flat[3], rain_flat[4], rain_flat[5]),
        (rain_flat[6], rain_flat[7], rain_flat[8]),
    )

    return WeatherControl(
        et=et,
        raining=raining,
        cloudiness=cloudiness,
        ambient_temp_k=ambient_temp_k,
        wind_max_speed=wind_max_speed,
        apply_cloudiness_instantly=instant_cloud,
    )


def decode_extended_state(data: bytes, offset: int = 0) -> Optional[ExtendedState]:
    """Decodes a 68-byte ExtendedState packet (Type 8)."""
    if len(data) - offset < EXTENDED_STATE_SIZE:
        return None

    unpacked = struct.unpack_from(EXTENDED_STATE_STRUCT, data, offset)
    physics = PhysicsOptions(
        traction_control=unpacked[0],
        anti_lock_brakes=unpacked[1],
        stability_control=unpacked[2],
        auto_shift=unpacked[3],
        auto_clutch=unpacked[4],
        invulnerable=unpacked[5],
        opposite_lock=unpacked[6],
        steering_help=unpacked[7],
        braking_help=unpacked[8],
        spin_recovery=unpacked[9],
        auto_pit=unpacked[10],
        auto_lift=unpacked[11],
        auto_blip=unpacked[12],
        fuel_mult=unpacked[13],
        tire_mult=unpacked[14],
        mech_fail=unpacked[15],
        allow_pitcrew_push=unpacked[16],
        repeat_shifts=unpacked[17],
        hold_clutch=unpacked[18],
        auto_reverse=unpacked[19],
        alternate_neutral=unpacked[20],
        ai_control=unpacked[21],
        manual_shift_override_time=unpacked[22],
        auto_shift_override_time=unpacked[23],
        speed_sensitive_steering=unpacked[24],
        steer_ratio_speed=unpacked[25],
    )

    max_impact = unpacked[26]
    acc_impact = unpacked[27]
    in_rt = bool(unpacked[28])
    session_started = bool(unpacked[29])
    session = unpacked[30]
    pit_speed = unpacked[31]

    return ExtendedState(
        physics=physics,
        max_impact_magnitude=max_impact,
        accumulated_impact_magnitude=acc_impact,
        in_realtime_fc=in_rt,
        session_started=session_started,
        session=session,
        current_pit_speed_limit=pit_speed,
    )


def decode_force_feedback(data: bytes, offset: int = 0) -> Optional[ForceFeedback]:
    """Decodes an 8-byte ForceFeedback packet (Type 9)."""
    if len(data) - offset < FORCE_FEEDBACK_SIZE:
        return None

    force_val = struct.unpack_from(FORCE_FEEDBACK_STRUCT, data, offset)[0]
    return ForceFeedback(force_value=force_val)


def decode_graphics(data: bytes, offset: int = 0) -> Optional[Graphics]:
    """Decodes a 128-byte Graphics packet (Type 10)."""
    if len(data) - offset < GRAPHICS_SIZE:
        return None

    unpacked = struct.unpack_from(GRAPHICS_STRUCT, data, offset)
    cam_pos = TelemVect3(unpacked[0], unpacked[1], unpacked[2])
    cam_ori = (
        TelemVect3(unpacked[3], unpacked[4], unpacked[5]),
        TelemVect3(unpacked[6], unpacked[7], unpacked[8]),
        TelemVect3(unpacked[9], unpacked[10], unpacked[11]),
    )
    ambient_rgb = (unpacked[12], unpacked[13], unpacked[14])
    slot_id = unpacked[15]
    camera_type = unpacked[16]

    return Graphics(
        cam_pos=cam_pos,
        cam_ori=cam_ori,
        ambient_rgb=ambient_rgb,
        slot_id=slot_id,
        camera_type=camera_type,
    )


def decode_system_event(data: bytes, offset: int = 0) -> Optional[SystemEvent]:
    """Decodes a 6-byte SIMP Type 3 system event packet."""
    if len(data) - offset < 2:
        return None
    event_id = data[offset + 5] if (offset == 0 and data.startswith(b"SIMP")) else data[offset]
    return SystemEvent(event_id=event_id)


def encode_header(
    packet_type: int,
    payload_size: int,
    sequence_number: int = 0,
    session_et: float = 0.0,
    chunk_index: int = 0,
    total_chunks: int = 1,
    sub_type_or_id: int = 0,
) -> bytes:
    """Encodes a standard 24-byte SIMP protocol header."""
    return struct.pack(
        HEADER_STRUCT,
        b"SIMP",
        1,  # protocol_version
        packet_type,
        payload_size,
        sequence_number,
        session_et,
        chunk_index,
        total_chunks,
        sub_type_or_id,
    )


def encode_hw_control(
    control_name: str,
    control_value: float = 1.0,
    duration_ms: int = 50,
    with_header: bool = False,
    sequence_number: int = 0,
) -> bytes:
    """
    Encodes a 44-byte HWControlCommandPacket, optionally prepended with the 24-byte SIMP header (Type 100).
    """
    raw_name = control_name.encode("utf-8")[:32].ljust(32, b"\x00")
    payload = struct.pack(HW_CONTROL_COMMAND_STRUCT, raw_name, float(control_value), int(duration_ms))
    if with_header:
        hdr = encode_header(100, len(payload), sequence_number=sequence_number)
        return hdr + payload
    return payload


def decode_hw_control(data: bytes, offset: int = 0) -> Optional[HWControlCommand]:
    """Decodes a 44-byte HWControlCommand packet (Type 100)."""
    if len(data) - offset < HW_CONTROL_COMMAND_SIZE:
        return None
    raw_name, val, dur = struct.unpack_from(HW_CONTROL_COMMAND_STRUCT, data, offset)
    return HWControlCommand(
        control_name=_decode_string(raw_name),
        control_value=val,
        duration_ms=dur,
    )


def encode_weather_control(
    ambient_temp: float = 20.0,
    track_temp: float = 25.0,
    dark_cloud: float = 0.0,
    raining: float = 0.0,
    wind_speed: float = 0.0,
    wind_direction: float = 0.0,
    min_path_wetness: float = 0.0,
    max_path_wetness: float = 0.0,
    with_header: bool = False,
    sequence_number: int = 0,
) -> bytes:
    """
    Encodes a 64-byte WeatherControlCommandPacket, optionally prepended with the 24-byte SIMP header (Type 101).
    """
    payload = struct.pack(
        WEATHER_CONTROL_COMMAND_STRUCT,
        float(ambient_temp),
        float(track_temp),
        float(dark_cloud),
        float(raining),
        float(wind_speed),
        float(wind_direction),
        float(min_path_wetness),
        float(max_path_wetness),
    )
    if with_header:
        hdr = encode_header(101, len(payload), sequence_number=sequence_number)
        return hdr + payload
    return payload


def decode_weather_control(data: bytes, offset: int = 0) -> Optional[WeatherControlCommand]:
    """Decodes a 64-byte WeatherControlCommand packet (Type 101)."""
    if len(data) - offset < WEATHER_CONTROL_COMMAND_SIZE:
        return None
    unpacked = struct.unpack_from(WEATHER_CONTROL_COMMAND_STRUCT, data, offset)
    return WeatherControlCommand(
        ambient_temp=unpacked[0],
        track_temp=unpacked[1],
        dark_cloud=unpacked[2],
        raining=unpacked[3],
        wind_speed=unpacked[4],
        wind_direction=unpacked[5],
        min_path_wetness=unpacked[6],
        max_path_wetness=unpacked[7],
    )


def decode_packet(
    data: bytes,
) -> Optional[
    Union[
        TelemInfo,
        CompactScoring,
        FullScoringSession,
        TrackRulesSession,
        PitMenu,
        WeatherControl,
        ExtendedState,
        ForceFeedback,
        Graphics,
        SystemEvent,
        HWControlCommand,
        WeatherControlCommand,
    ]
]:
    """
    Main decoder entrypoint. Identifies and parses any supported isiMotor UDP packet.
    Supports both legacy raw/SIMP packets and new standardized 24-byte header packets.
    """
    if not data:
        return None

    # 1. Check for standardized 24-byte RawUdpHeader (protocolVersion == 1)
    if data.startswith(b"SIMP") and len(data) >= HEADER_SIZE:
        proto_ver = data[4]
        if proto_ver == 1:
            hdr = decode_header(data)
            if hdr:
                payload = data[HEADER_SIZE : HEADER_SIZE + hdr.payload_size]
                if hdr.packet_type == 1:
                    return decode_telemetry(payload)
                elif hdr.packet_type == 2:
                    return decode_compact_scoring(payload)
                elif hdr.packet_type == 3:
                    return decode_system_event(payload)
                elif hdr.packet_type == 4:
                    if hdr.total_chunks == 1:
                        return decode_full_scoring(payload)
                    return None
                elif hdr.packet_type == 5:
                    if hdr.total_chunks == 1:
                        return decode_track_rules(payload)
                    return None
                elif hdr.packet_type == 6:
                    return decode_pit_menu(payload)
                elif hdr.packet_type == 7:
                    return decode_weather(payload)
                elif hdr.packet_type == 8:
                    return decode_extended_state(payload)
                elif hdr.packet_type == 9:
                    return decode_force_feedback(payload)
                elif hdr.packet_type == 10:
                    return decode_graphics(payload)
                elif hdr.packet_type == 100:
                    return decode_hw_control(payload)
                elif hdr.packet_type == 101:
                    return decode_weather_control(payload)

    # 2. Legacy SIMP Packet Types (CompactScoring=2, SystemEvent=3)
    if data.startswith(b"SIMP") and len(data) >= 5:
        pkt_type = data[4]
        if pkt_type == 2:
            return decode_compact_scoring(data)
        elif pkt_type == 3:
            return decode_system_event(data)

    # 3. Legacy Raw Telemetry (1888 bytes without SIMP header)
    if len(data) >= TELEMINFO_SIZE:
        return decode_telemetry(data)

    return None
