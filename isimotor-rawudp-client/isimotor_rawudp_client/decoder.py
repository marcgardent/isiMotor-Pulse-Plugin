"""
High-performance binary decoder for isiMotor / LMU / rFactor 2 raw UDP packets.
"""

import struct
from typing import Optional, Union, Tuple
from .models import TelemInfo, TelemWheel, TelemVect3, CompactScoring, SystemEvent

TELEMINFO_SIZE = 1904
COMPACT_SCORING_SIZE = 176
SYSTEM_EVENT_SIZE = 6

def _decode_string(raw_bytes: bytes) -> str:
    """Decodes null-terminated C string."""
    return raw_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")

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

def decode_telemetry(data: bytes) -> Optional[TelemInfo]:
    """Decodes a 1904-byte native TelemInfoV01 memory dump."""
    if len(data) < TELEMINFO_SIZE:
        return None

    slot_id = struct.unpack_from("<i", data, 0)[0]
    dt = struct.unpack_from("<d", data, 8)[0]
    elapsed = struct.unpack_from("<d", data, 16)[0]
    lap_num = struct.unpack_from("<i", data, 24)[0]
    lap_start_et = struct.unpack_from("<d", data, 32)[0]
    veh_name = _decode_string(data[40:104])
    track_name = _decode_string(data[104:168])

    px, py, pz = struct.unpack_from("<ddd", data, 168)
    pos = TelemVect3(px, py, pz)

    vx, vy, vz = struct.unpack_from("<ddd", data, 192)
    local_vel = TelemVect3(vx, vy, vz)

    ax, ay, az = struct.unpack_from("<ddd", data, 216)
    local_accel = TelemVect3(ax, ay, az)

    # Orientation matrix 3x3
    r0 = TelemVect3(*struct.unpack_from("<ddd", data, 240))
    r1 = TelemVect3(*struct.unpack_from("<ddd", data, 264))
    r2 = TelemVect3(*struct.unpack_from("<ddd", data, 288))
    ori = (r0, r1, r2)

    rx, ry, rz = struct.unpack_from("<ddd", data, 312)
    local_rot = TelemVect3(rx, ry, rz)

    rax, ray, raz = struct.unpack_from("<ddd", data, 336)
    local_rot_accel = TelemVect3(rax, ray, raz)

    gear = struct.unpack_from("<i", data, 360)[0]
    engine_rpm = struct.unpack_from("<d", data, 368)[0]
    water_temp = struct.unpack_from("<d", data, 376)[0]
    oil_temp = struct.unpack_from("<d", data, 384)[0]
    clutch_rpm = struct.unpack_from("<d", data, 392)[0]

    unf_throttle = struct.unpack_from("<d", data, 400)[0]
    unf_brake = struct.unpack_from("<d", data, 408)[0]
    unf_steer = struct.unpack_from("<d", data, 416)[0]
    unf_clutch = struct.unpack_from("<d", data, 424)[0]

    fil_throttle = struct.unpack_from("<d", data, 432)[0]
    fil_brake = struct.unpack_from("<d", data, 440)[0]
    fil_steer = struct.unpack_from("<d", data, 448)[0]
    fil_clutch = struct.unpack_from("<d", data, 456)[0]

    steering_shaft_torque = struct.unpack_from("<d", data, 464)[0]
    front_3rd_defl = struct.unpack_from("<d", data, 472)[0]
    rear_3rd_defl = struct.unpack_from("<d", data, 480)[0]

    front_wing_h = struct.unpack_from("<d", data, 488)[0]
    front_ride_h = struct.unpack_from("<d", data, 496)[0]
    rear_ride_h = struct.unpack_from("<d", data, 504)[0]
    drag = struct.unpack_from("<d", data, 512)[0]
    front_downforce = struct.unpack_from("<d", data, 520)[0]
    rear_downforce = struct.unpack_from("<d", data, 528)[0]

    fuel = struct.unpack_from("<d", data, 536)[0]
    max_rpm = struct.unpack_from("<d", data, 544)[0]
    scheduled_stops = data[552]
    overheating = bool(data[553])
    detached = bool(data[554])
    headlights = bool(data[555])
    dent_severity = tuple(data[556:564])

    last_impact_et = struct.unpack_from("<d", data, 568)[0]
    last_impact_magnitude = struct.unpack_from("<d", data, 576)[0]
    ix, iy, iz = struct.unpack_from("<ddd", data, 584)
    last_impact_pos = TelemVect3(ix, iy, iz)

    engine_torque = struct.unpack_from("<d", data, 608)[0]
    current_sector = struct.unpack_from("<i", data, 616)[0]
    speed_limiter = data[620]
    max_gears = data[621]
    front_tire_compound_idx = data[622]
    rear_tire_compound_idx = data[623]
    fuel_capacity = struct.unpack_from("<d", data, 624)[0]
    front_flap_act = data[632]
    rear_flap_act = data[633]
    rear_flap_status = data[634]
    ignition_starter = data[635]
    front_compound_name = _decode_string(data[636:654])
    rear_compound_name = _decode_string(data[654:672])

    speed_limiter_avail = data[672]
    anti_stall_act = data[673]
    visual_steer_range = struct.unpack_from("<f", data, 676)[0]
    rear_brake_bias = struct.unpack_from("<d", data, 680)[0]
    turbo_boost = struct.unpack_from("<d", data, 688)[0]
    p2g_offset = struct.unpack_from("<fff", data, 696)
    physical_steer_range = struct.unpack_from("<f", data, 708)[0]
    battery_charge = struct.unpack_from("<d", data, 712)[0]

    eb_torque = struct.unpack_from("<d", data, 720)[0]
    eb_rpm = struct.unpack_from("<d", data, 728)[0]
    eb_temp = struct.unpack_from("<d", data, 736)[0]
    eb_water_temp = struct.unpack_from("<d", data, 744)[0]
    eb_state = data[752]

    # Wheels (FL: 864, FR: 1124, RL: 1384, RR: 1644)
    w_fl = decode_wheel(data, 864)
    w_fr = decode_wheel(data, 1124)
    w_rl = decode_wheel(data, 1384)
    w_rr = decode_wheel(data, 1644)

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

def decode_compact_scoring(data: bytes) -> Optional[CompactScoring]:
    """Decodes a 176-byte SIMP Type 2 compact scoring packet."""
    if len(data) < COMPACT_SCORING_SIZE or not data.startswith(b"SIMP") or data[4] != 2:
        return None

    track = _decode_string(data[5:69])
    session = struct.unpack_from("<i", data, 72)[0]
    current_et = struct.unpack_from("<d", data, 80)[0]
    lap_dist = struct.unpack_from("<d", data, 88)[0]
    max_laps = struct.unpack_from("<i", data, 96)[0]
    in_rt = bool(data[104])
    total_laps = struct.unpack_from("<h", data, 106)[0]
    sector = struct.unpack_from("<b", data, 108)[0]
    in_garage = bool(data[109])
    count_lap_flag = data[110]

    cur_s1 = struct.unpack_from("<d", data, 112)[0]
    cur_s2 = struct.unpack_from("<d", data, 120)[0]
    last_s1 = struct.unpack_from("<d", data, 128)[0]
    last_s2 = struct.unpack_from("<d", data, 136)[0]
    last_lap = struct.unpack_from("<d", data, 144)[0]
    best_s1 = struct.unpack_from("<d", data, 152)[0]
    best_s2 = struct.unpack_from("<d", data, 160)[0]
    best_lap = struct.unpack_from("<d", data, 168)[0]

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

def decode_system_event(data: bytes) -> Optional[SystemEvent]:
    """Decodes a 6-byte SIMP Type 3 system event packet."""
    if len(data) < SYSTEM_EVENT_SIZE or not data.startswith(b"SIMP") or data[4] != 3:
        return None
    return SystemEvent(event_id=data[5])

def decode_packet(data: bytes) -> Optional[Union[TelemInfo, CompactScoring, SystemEvent]]:
    """
    Main decoder entrypoint. Identifies and parses any supported isiMotor UDP packet.
    """
    if not data:
        return None

    if len(data) >= TELEMINFO_SIZE:
        return decode_telemetry(data)

    if data.startswith(b"SIMP") and len(data) >= 5:
        pkt_type = data[4]
        if pkt_type == 2:
            return decode_compact_scoring(data)
        elif pkt_type == 3:
            return decode_system_event(data)

    return None
