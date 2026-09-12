"""
FlatBuffers encode/decode helpers for the packet types migrated off the
legacy RawUdpHeader + fixed-layout-struct wire format (schemas/*.fbs).

With ZeroMQ/TCP the message boundary already delimits one FlatBuffer, so
there is no header, no chunking, and no framing: `decode_*` functions take
the full raw ZMQ message bytes, and `encode_*` functions return the full
bytes to publish as-is.
"""

import flatbuffers

from isimotor_rawudp_types import (
    FullScoringSession,
    TelemInfo,
    TelemVect3,
    TelemWheel,
    VehicleScoring,
)
from isimotor_rawudp_types.ecu import EcuState
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import CommandPayload as _CommandPayload
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import CompactScoring as _CompactScoringFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import EcuRaw as _EcuRawFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import ExtendedState as _ExtendedStateFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import ForceFeedback as _ForceFeedbackFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import FullScoringSession as _FullScoringSessionFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import Graphics as _GraphicsFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import HWControlCommand as _HWControlCommandFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import InboundCommand as _InboundCommandFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import PhysicsOptions as _PhysicsOptionsFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import SystemEvent as _SystemEventFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import TelemInfo as _TelemInfoFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import TelemWheel as _TelemWheelFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import Vec3 as _Vec3FB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import VehicleScoring as _VehicleScoringFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import WeatherControl as _WeatherControlFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import WeatherControlCommand as _WeatherControlCommandFB
from isimotor_rawudp_types.lmu import (
    LMUCompoundType,
    LMUScoringExtension,
    LMUTelemetryExtension,
    LMUVehicleScoringExtension,
    LMUWheelExtension,
)


def decode_system_event_fbs(data: bytes) -> int | None:
    """Decodes a SystemEvent FlatBuffer (packet type 3), returning the raw event_type byte."""
    if not data:
        return None
    ev = _SystemEventFB.SystemEvent.GetRootAs(data, 0)
    return int(ev.EventType())


def encode_system_event_fbs(event_type: int) -> bytes:
    """Encodes a SystemEvent FlatBuffer (packet type 3)."""
    builder = flatbuffers.Builder(16)
    _SystemEventFB.Start(builder)
    _SystemEventFB.AddEventType(builder, event_type)
    root = _SystemEventFB.End(builder)
    builder.Finish(root)
    return bytes(builder.Output())


def decode_force_feedback_fbs(data: bytes) -> float | None:
    """Decodes a ForceFeedback FlatBuffer (packet type 9), returning the raw force_value."""
    if not data:
        return None
    ffb = _ForceFeedbackFB.ForceFeedback.GetRootAs(data, 0)
    return float(ffb.ForceValue())


def encode_force_feedback_fbs(force_value: float) -> bytes:
    """Encodes a ForceFeedback FlatBuffer (packet type 9)."""
    builder = flatbuffers.Builder(16)
    _ForceFeedbackFB.Start(builder)
    _ForceFeedbackFB.AddForceValue(builder, force_value)
    root = _ForceFeedbackFB.End(builder)
    builder.Finish(root)
    return bytes(builder.Output())


def encode_hw_control_fbs(control_name: str, control_value: float = 1.0, duration_ms: int = 50) -> bytes:
    """Encodes an InboundCommand FlatBuffer wrapping a HWControlCommand payload (packet type 100)."""
    builder = flatbuffers.Builder(96)
    name_offset = builder.CreateString(control_name)
    _HWControlCommandFB.Start(builder)
    _HWControlCommandFB.AddControlName(builder, name_offset)
    _HWControlCommandFB.AddControlValue(builder, control_value)
    _HWControlCommandFB.AddDurationMs(builder, duration_ms)
    hw_offset = _HWControlCommandFB.End(builder)

    _InboundCommandFB.Start(builder)
    _InboundCommandFB.AddPayloadType(builder, _CommandPayload.CommandPayload.HWControlCommand)
    _InboundCommandFB.AddPayload(builder, hw_offset)
    root = _InboundCommandFB.End(builder)
    builder.Finish(root)
    return bytes(builder.Output())


def encode_weather_control_fbs(
    ambient_temp: float = 20.0,
    track_temp: float = 25.0,
    dark_cloud: float = 0.0,
    raining: float = 0.0,
    wind_speed: float = 0.0,
    wind_direction: float = 0.0,
    min_path_wetness: float = 0.0,
    max_path_wetness: float = 0.0,
) -> bytes:
    """Encodes an InboundCommand FlatBuffer wrapping a WeatherControlCommand payload (packet type 101)."""
    builder = flatbuffers.Builder(128)
    _WeatherControlCommandFB.Start(builder)
    _WeatherControlCommandFB.AddAmbientTemp(builder, ambient_temp)
    _WeatherControlCommandFB.AddTrackTemp(builder, track_temp)
    _WeatherControlCommandFB.AddDarkCloud(builder, dark_cloud)
    _WeatherControlCommandFB.AddRaining(builder, raining)
    _WeatherControlCommandFB.AddWindSpeed(builder, wind_speed)
    _WeatherControlCommandFB.AddWindDirection(builder, wind_direction)
    _WeatherControlCommandFB.AddMinPathWetness(builder, min_path_wetness)
    _WeatherControlCommandFB.AddMaxPathWetness(builder, max_path_wetness)
    wc_offset = _WeatherControlCommandFB.End(builder)

    _InboundCommandFB.Start(builder)
    _InboundCommandFB.AddPayloadType(builder, _CommandPayload.CommandPayload.WeatherControlCommand)
    _InboundCommandFB.AddPayload(builder, wc_offset)
    root = _InboundCommandFB.End(builder)
    builder.Finish(root)
    return bytes(builder.Output())


def decode_hw_control_fbs(data: bytes) -> tuple[str, float, int] | None:
    """Decodes an InboundCommand FlatBuffer's HWControlCommand payload, if present."""
    cmd = _InboundCommandFB.InboundCommand.GetRootAs(data, 0)
    if cmd.PayloadType() != _CommandPayload.CommandPayload.HWControlCommand:
        return None
    table = cmd.Payload()
    if table is None:
        return None
    hw = _HWControlCommandFB.HWControlCommand()
    hw.Init(table.Bytes, table.Pos)
    name = hw.ControlName()
    return (name.decode("utf-8") if name else "", hw.ControlValue(), hw.DurationMs())


def decode_weather_control_fbs(data: bytes) -> tuple[float, float, float, float, float, float, float, float] | None:
    """Decodes an InboundCommand FlatBuffer's WeatherControlCommand payload, if present."""
    cmd = _InboundCommandFB.InboundCommand.GetRootAs(data, 0)
    if cmd.PayloadType() != _CommandPayload.CommandPayload.WeatherControlCommand:
        return None
    table = cmd.Payload()
    if table is None:
        return None
    wc = _WeatherControlCommandFB.WeatherControlCommand()
    wc.Init(table.Bytes, table.Pos)
    return (
        wc.AmbientTemp(),
        wc.TrackTemp(),
        wc.DarkCloud(),
        wc.Raining(),
        wc.WindSpeed(),
        wc.WindDirection(),
        wc.MinPathWetness(),
        wc.MaxPathWetness(),
    )


def decode_compact_scoring_fbs(data: bytes) -> dict | None:
    """Decodes a CompactScoring FlatBuffer (packet type 2) into a plain field dict."""
    if not data:
        return None
    cs = _CompactScoringFB.CompactScoring.GetRootAs(data, 0)
    track_name = cs.TrackName()
    return {
        "track_name": track_name.decode("utf-8") if track_name else "",
        "session": cs.Session(),
        "current_et": cs.CurrentEt(),
        "total_lap_dist": cs.TotalLapDist(),
        "max_laps": cs.MaxLaps(),
        "in_realtime": bool(cs.InRealtime()),
        "total_laps": cs.TotalLaps(),
        "sector": cs.Sector(),
        "in_garage_stall": bool(cs.InGarageStall()),
        "count_lap_flag": cs.CountLapFlag(),
        "cur_sector1": cs.CurSector1(),
        "cur_sector2": cs.CurSector2(),
        "last_sector1": cs.LastSector1(),
        "last_sector2": cs.LastSector2(),
        "last_lap_time": cs.LastLapTime(),
        "best_sector1": cs.BestSector1(),
        "best_sector2": cs.BestSector2(),
        "best_lap_time": cs.BestLapTime(),
    }


def encode_compact_scoring_fbs(fields: dict) -> bytes:
    """Encodes a CompactScoring FlatBuffer (packet type 2) from a plain field dict (see decode_compact_scoring_fbs)."""
    builder = flatbuffers.Builder(256)
    track_name_offset = builder.CreateString(fields["track_name"])
    _CompactScoringFB.Start(builder)
    _CompactScoringFB.AddTrackName(builder, track_name_offset)
    _CompactScoringFB.AddSession(builder, fields["session"])
    _CompactScoringFB.AddCurrentEt(builder, fields["current_et"])
    _CompactScoringFB.AddTotalLapDist(builder, fields["total_lap_dist"])
    _CompactScoringFB.AddMaxLaps(builder, fields["max_laps"])
    _CompactScoringFB.AddInRealtime(builder, fields["in_realtime"])
    _CompactScoringFB.AddTotalLaps(builder, fields["total_laps"])
    _CompactScoringFB.AddSector(builder, fields["sector"])
    _CompactScoringFB.AddInGarageStall(builder, fields["in_garage_stall"])
    _CompactScoringFB.AddCountLapFlag(builder, fields["count_lap_flag"])
    _CompactScoringFB.AddCurSector1(builder, fields["cur_sector1"])
    _CompactScoringFB.AddCurSector2(builder, fields["cur_sector2"])
    _CompactScoringFB.AddLastSector1(builder, fields["last_sector1"])
    _CompactScoringFB.AddLastSector2(builder, fields["last_sector2"])
    _CompactScoringFB.AddLastLapTime(builder, fields["last_lap_time"])
    _CompactScoringFB.AddBestSector1(builder, fields["best_sector1"])
    _CompactScoringFB.AddBestSector2(builder, fields["best_sector2"])
    _CompactScoringFB.AddBestLapTime(builder, fields["best_lap_time"])
    root = _CompactScoringFB.End(builder)
    builder.Finish(root)
    return bytes(builder.Output())


def decode_weather_fbs(data: bytes) -> dict | None:
    """Decodes a WeatherControl FlatBuffer (packet type 7) into a plain field dict."""
    if not data:
        return None
    w = _WeatherControlFB.WeatherControl.GetRootAs(data, 0)
    rain_flat = [w.Raining(i) for i in range(w.RainingLength())]
    while len(rain_flat) < 9:
        rain_flat.append(0.0)
    return {
        "et": w.Et(),
        "raining": (
            (rain_flat[0], rain_flat[1], rain_flat[2]),
            (rain_flat[3], rain_flat[4], rain_flat[5]),
            (rain_flat[6], rain_flat[7], rain_flat[8]),
        ),
        "cloudiness": w.Cloudiness(),
        "ambient_temp_k": w.AmbientTempK(),
        "wind_max_speed": w.WindMaxSpeed(),
        "apply_cloudiness_instantly": bool(w.ApplyCloudinessInstantly()),
    }


def encode_weather_fbs(fields: dict) -> bytes:
    """Encodes a WeatherControl FlatBuffer (packet type 7) from a plain field dict (see decode_weather_fbs)."""
    builder = flatbuffers.Builder(160)
    rain_flat = [v for row in fields["raining"] for v in row]
    _WeatherControlFB.StartRainingVector(builder, len(rain_flat))
    for v in reversed(rain_flat):
        builder.PrependFloat64(v)
    raining_offset = builder.EndVector()

    _WeatherControlFB.Start(builder)
    _WeatherControlFB.AddEt(builder, fields["et"])
    _WeatherControlFB.AddRaining(builder, raining_offset)
    _WeatherControlFB.AddCloudiness(builder, fields["cloudiness"])
    _WeatherControlFB.AddAmbientTempK(builder, fields["ambient_temp_k"])
    _WeatherControlFB.AddWindMaxSpeed(builder, fields["wind_max_speed"])
    _WeatherControlFB.AddApplyCloudinessInstantly(builder, fields["apply_cloudiness_instantly"])
    root = _WeatherControlFB.End(builder)
    builder.Finish(root)
    return bytes(builder.Output())


def decode_extended_state_fbs(data: bytes) -> dict | None:
    """Decodes an ExtendedState FlatBuffer (packet type 8) into a plain field dict."""
    if not data:
        return None
    ext = _ExtendedStateFB.ExtendedState.GetRootAs(data, 0)
    phys = ext.Physics()
    physics = {
        "traction_control": phys.TractionControl(),
        "anti_lock_brakes": phys.AntiLockBrakes(),
        "stability_control": phys.StabilityControl(),
        "auto_shift": phys.AutoShift(),
        "auto_clutch": phys.AutoClutch(),
        "invulnerable": phys.Invulnerable(),
        "opposite_lock": phys.OppositeLock(),
        "steering_help": phys.SteeringHelp(),
        "braking_help": phys.BrakingHelp(),
        "spin_recovery": phys.SpinRecovery(),
        "auto_pit": phys.AutoPit(),
        "auto_lift": phys.AutoLift(),
        "auto_blip": phys.AutoBlip(),
        "fuel_mult": phys.FuelMult(),
        "tire_mult": phys.TireMult(),
        "mech_fail": phys.MechFail(),
        "allow_pitcrew_push": phys.AllowPitcrewPush(),
        "repeat_shifts": phys.RepeatShifts(),
        "hold_clutch": phys.HoldClutch(),
        "auto_reverse": phys.AutoReverse(),
        "alternate_neutral": phys.AlternateNeutral(),
        "ai_control": phys.AiControl(),
        "manual_shift_override_time": phys.ManualShiftOverrideTime(),
        "auto_shift_override_time": phys.AutoShiftOverrideTime(),
        "speed_sensitive_steering": phys.SpeedSensitiveSteering(),
        "steer_ratio_speed": phys.SteerRatioSpeed(),
    }
    return {
        "physics": physics,
        "max_impact_magnitude": ext.MaxImpactMagnitude(),
        "accumulated_impact_magnitude": ext.AccumulatedImpactMagnitude(),
        "in_realtime_fc": bool(ext.InRealtimeFc()),
        "session_started": bool(ext.SessionStarted()),
        "session": ext.Session(),
        "current_pit_speed_limit": ext.CurrentPitSpeedLimit(),
    }


def encode_extended_state_fbs(fields: dict) -> bytes:
    """Encodes an ExtendedState FlatBuffer (packet type 8) from a plain field dict (see decode_extended_state_fbs)."""
    builder = flatbuffers.Builder(160)
    p = fields["physics"]
    _PhysicsOptionsFB.Start(builder)
    _PhysicsOptionsFB.AddTractionControl(builder, p["traction_control"])
    _PhysicsOptionsFB.AddAntiLockBrakes(builder, p["anti_lock_brakes"])
    _PhysicsOptionsFB.AddStabilityControl(builder, p["stability_control"])
    _PhysicsOptionsFB.AddAutoShift(builder, p["auto_shift"])
    _PhysicsOptionsFB.AddAutoClutch(builder, p["auto_clutch"])
    _PhysicsOptionsFB.AddInvulnerable(builder, p["invulnerable"])
    _PhysicsOptionsFB.AddOppositeLock(builder, p["opposite_lock"])
    _PhysicsOptionsFB.AddSteeringHelp(builder, p["steering_help"])
    _PhysicsOptionsFB.AddBrakingHelp(builder, p["braking_help"])
    _PhysicsOptionsFB.AddSpinRecovery(builder, p["spin_recovery"])
    _PhysicsOptionsFB.AddAutoPit(builder, p["auto_pit"])
    _PhysicsOptionsFB.AddAutoLift(builder, p["auto_lift"])
    _PhysicsOptionsFB.AddAutoBlip(builder, p["auto_blip"])
    _PhysicsOptionsFB.AddFuelMult(builder, p["fuel_mult"])
    _PhysicsOptionsFB.AddTireMult(builder, p["tire_mult"])
    _PhysicsOptionsFB.AddMechFail(builder, p["mech_fail"])
    _PhysicsOptionsFB.AddAllowPitcrewPush(builder, p["allow_pitcrew_push"])
    _PhysicsOptionsFB.AddRepeatShifts(builder, p["repeat_shifts"])
    _PhysicsOptionsFB.AddHoldClutch(builder, p["hold_clutch"])
    _PhysicsOptionsFB.AddAutoReverse(builder, p["auto_reverse"])
    _PhysicsOptionsFB.AddAlternateNeutral(builder, p["alternate_neutral"])
    _PhysicsOptionsFB.AddAiControl(builder, p["ai_control"])
    _PhysicsOptionsFB.AddManualShiftOverrideTime(builder, p["manual_shift_override_time"])
    _PhysicsOptionsFB.AddAutoShiftOverrideTime(builder, p["auto_shift_override_time"])
    _PhysicsOptionsFB.AddSpeedSensitiveSteering(builder, p["speed_sensitive_steering"])
    _PhysicsOptionsFB.AddSteerRatioSpeed(builder, p["steer_ratio_speed"])
    physics_offset = _PhysicsOptionsFB.End(builder)

    _ExtendedStateFB.Start(builder)
    _ExtendedStateFB.AddPhysics(builder, physics_offset)
    _ExtendedStateFB.AddMaxImpactMagnitude(builder, fields["max_impact_magnitude"])
    _ExtendedStateFB.AddAccumulatedImpactMagnitude(builder, fields["accumulated_impact_magnitude"])
    _ExtendedStateFB.AddInRealtimeFc(builder, fields["in_realtime_fc"])
    _ExtendedStateFB.AddSessionStarted(builder, fields["session_started"])
    _ExtendedStateFB.AddSession(builder, fields["session"])
    _ExtendedStateFB.AddCurrentPitSpeedLimit(builder, fields["current_pit_speed_limit"])
    root = _ExtendedStateFB.End(builder)
    builder.Finish(root)
    return bytes(builder.Output())


def decode_graphics_fbs(data: bytes) -> dict | None:
    """Decodes a Graphics FlatBuffer (packet type 10) into a plain field dict."""
    if not data:
        return None
    gfx = _GraphicsFB.Graphics.GetRootAs(data, 0)
    cam_pos = gfx.CamPos()
    ori0 = gfx.CamOri0()
    ori1 = gfx.CamOri1()
    ori2 = gfx.CamOri2()
    return {
        "cam_pos": (cam_pos.X(), cam_pos.Y(), cam_pos.Z()),
        "cam_ori": (
            (ori0.X(), ori0.Y(), ori0.Z()),
            (ori1.X(), ori1.Y(), ori1.Z()),
            (ori2.X(), ori2.Y(), ori2.Z()),
        ),
        "ambient_rgb": (gfx.AmbientRed(), gfx.AmbientGreen(), gfx.AmbientBlue()),
        "slot_id": gfx.SlotId(),
        "camera_type": gfx.CameraType(),
    }


def encode_graphics_fbs(fields: dict) -> bytes:
    """Encodes a Graphics FlatBuffer (packet type 10) from a plain field dict (see decode_graphics_fbs)."""
    builder = flatbuffers.Builder(160)
    cx, cy, cz = fields["cam_pos"]
    o0, o1, o2 = fields["cam_ori"]
    # Structs must be built before the table that embeds them.
    cam_pos = _Vec3FB.CreateVec3(builder, cx, cy, cz)
    cam_ori0 = _Vec3FB.CreateVec3(builder, *o0)
    cam_ori1 = _Vec3FB.CreateVec3(builder, *o1)
    cam_ori2 = _Vec3FB.CreateVec3(builder, *o2)

    _GraphicsFB.Start(builder)
    _GraphicsFB.AddCamPos(builder, cam_pos)
    _GraphicsFB.AddCamOri0(builder, cam_ori0)
    _GraphicsFB.AddCamOri1(builder, cam_ori1)
    _GraphicsFB.AddCamOri2(builder, cam_ori2)
    ar, ag, ab = fields["ambient_rgb"]
    _GraphicsFB.AddAmbientRed(builder, ar)
    _GraphicsFB.AddAmbientGreen(builder, ag)
    _GraphicsFB.AddAmbientBlue(builder, ab)
    _GraphicsFB.AddSlotId(builder, fields["slot_id"])
    _GraphicsFB.AddCameraType(builder, fields["camera_type"])
    root = _GraphicsFB.End(builder)
    builder.Finish(root)
    return bytes(builder.Output())


def _vec3_fbs(v) -> TelemVect3:  # type: ignore[no-untyped-def]
    return TelemVect3(v.X(), v.Y(), v.Z())


def _decode_ecu_raw_fbs(ecu: _EcuRawFB.EcuRaw | None) -> EcuState:
    """Builds an EcuState from an EcuRaw FlatBuffer table, applying the same
    'unavailable if max==0' convention as the legacy raw-bytes decoder."""
    if ecu is None:
        return EcuState()
    tc_max, tc_cut_max, tc_slip_max = ecu.TcMax(), ecu.TcCutMax(), ecu.TcSlipMax()
    abs_max, motor_map_max, brake_migration_max = ecu.AbsMax(), ecu.MotorMapMax(), ecu.BrakeMigrationMax()
    front_arb_max, rear_arb_max = ecu.FrontArbMax(), ecu.RearArbMax()
    return EcuState(
        tc_active=bool(ecu.TcActive()),
        abs_active=bool(ecu.AbsActive()),
        tc_level=int(ecu.Tc()) if tc_max > 0 else -1,
        tc_max=int(tc_max),
        tc_cut=int(ecu.TcCut()) if tc_cut_max > 0 else -1,
        tc_cut_max=int(tc_cut_max),
        tc_slip=int(ecu.TcSlip()) if tc_slip_max > 0 else -1,
        tc_slip_max=int(tc_slip_max),
        abs_level=int(ecu.AbsLevel()) if abs_max > 0 else -1,
        abs_max=int(abs_max),
        motor_map=int(ecu.MotorMap()) if motor_map_max > 0 else -1,
        motor_map_max=int(motor_map_max),
        brake_migration=int(ecu.BrakeMigration()) if brake_migration_max > 0 else -1,
        brake_migration_max=int(brake_migration_max),
        front_arb=int(ecu.FrontArb()) if front_arb_max > 0 else -1,
        front_arb_max=int(front_arb_max),
        rear_arb=int(ecu.RearArb()) if rear_arb_max > 0 else -1,
        rear_arb_max=int(rear_arb_max),
        wiper_state=int(ecu.WiperState()),
        lift_and_coast=ecu.LiftAndCoast() / 255.0,
    )


def _decode_lmu_telemetry_fbs(lmu) -> LMUTelemetryExtension:  # type: ignore[no-untyped-def]
    if lmu is None:
        return LMUTelemetryExtension()
    model = lmu.VehicleModel()
    return LMUTelemetryExtension(
        ecu=_decode_ecu_raw_fbs(lmu.Ecu()),
        virtual_energy=float(lmu.VirtualEnergy()),
        regen_kw=float(lmu.RegenKw()),
        track_limits_steps=int(lmu.TrackLimitsSteps()),
        vehicle_model=model.decode("utf-8") if model else "",
    )


def _decode_telem_wheel_fbs(w: _TelemWheelFB.TelemWheel) -> TelemWheel:
    terrain = w.TerrainName()
    lmu = w.Lmu()
    lmu_ext = LMUWheelExtension()
    if lmu is not None:
        try:
            compound = LMUCompoundType(lmu.CompoundType())
        except ValueError:
            compound = LMUCompoundType.UNKNOWN
        lmu_ext = LMUWheelExtension(compound_type=compound, brake_wear_meters=float(lmu.BrakeWearMeters()))

    return TelemWheel(
        suspension_deflection=w.SuspensionDeflection(),
        ride_height=w.RideHeight(),
        susp_force=w.SuspForce(),
        brake_temp=w.BrakeTemp(),
        brake_pressure=w.BrakePressure(),
        rotation=w.Rotation(),
        lateral_patch_vel=w.LateralPatchVel(),
        longitudinal_patch_vel=w.LongitudinalPatchVel(),
        lateral_ground_vel=w.LateralGroundVel(),
        longitudinal_ground_vel=w.LongitudinalGroundVel(),
        camber=w.Camber(),
        lateral_force=w.LateralForce(),
        longitudinal_force=w.LongitudinalForce(),
        tire_load=w.TireLoad(),
        grip_fraction=w.GripFraction(),
        pressure=w.Pressure(),
        temperature=(w.Temperature(0), w.Temperature(1), w.Temperature(2)),
        wear=w.Wear(),
        terrain_name=terrain.decode("utf-8") if terrain else "",
        surface_type=w.SurfaceType(),
        flat=bool(w.Flat()),
        detached=bool(w.Detached()),
        static_undeflected_radius=w.StaticUndeflectedRadius(),
        vertical_tire_deflection=w.VerticalTireDeflection(),
        wheel_y_location=w.WheelYLocation(),
        toe=w.Toe(),
        tire_carcass_temperature=w.TireCarcassTemperature(),
        tire_inner_layer_temperature=(
            w.TireInnerLayerTemperature(0),
            w.TireInnerLayerTemperature(1),
            w.TireInnerLayerTemperature(2),
        ),
        lmu=lmu_ext,
    )


def decode_telemetry_fbs(data: bytes) -> TelemInfo | None:
    """Decodes a TelemInfo FlatBuffer (packet type 1)."""
    if not data:
        return None
    t = _TelemInfoFB.TelemInfo.GetRootAs(data, 0)
    veh_name, track_name = t.VehicleName(), t.TrackName()
    front_compound, rear_compound = t.FrontTireCompoundName(), t.RearTireCompoundName()

    return TelemInfo(
        slot_id=t.SlotId(),
        delta_time=t.DeltaTime(),
        elapsed_time=t.ElapsedTime(),
        lap_number=t.LapNumber(),
        lap_start_et=t.LapStartEt(),
        vehicle_name=veh_name.decode("utf-8") if veh_name else "",
        track_name=track_name.decode("utf-8") if track_name else "",
        pos=_vec3_fbs(t.Pos()),
        local_vel=_vec3_fbs(t.LocalVel()),
        local_accel=_vec3_fbs(t.LocalAccel()),
        ori=(_vec3_fbs(t.Ori0()), _vec3_fbs(t.Ori1()), _vec3_fbs(t.Ori2())),
        local_rot=_vec3_fbs(t.LocalRot()),
        local_rot_accel=_vec3_fbs(t.LocalRotAccel()),
        gear=t.Gear(),
        engine_rpm=t.EngineRpm(),
        engine_water_temp=t.EngineWaterTemp(),
        engine_oil_temp=t.EngineOilTemp(),
        clutch_rpm=t.ClutchRpm(),
        unfiltered_throttle=t.UnfilteredThrottle(),
        unfiltered_brake=t.UnfilteredBrake(),
        unfiltered_steering=t.UnfilteredSteering(),
        unfiltered_clutch=t.UnfilteredClutch(),
        filtered_throttle=t.FilteredThrottle(),
        filtered_brake=t.FilteredBrake(),
        filtered_steering=t.FilteredSteering(),
        filtered_clutch=t.FilteredClutch(),
        steering_shaft_torque=t.SteeringShaftTorque(),
        front_3rd_deflection=t.Front3rdDeflection(),
        rear_3rd_deflection=t.Rear3rdDeflection(),
        front_wing_height=t.FrontWingHeight(),
        front_ride_height=t.FrontRideHeight(),
        rear_ride_height=t.RearRideHeight(),
        drag=t.Drag(),
        front_downforce=t.FrontDownforce(),
        rear_downforce=t.RearDownforce(),
        fuel=t.Fuel(),
        engine_max_rpm=t.EngineMaxRpm(),
        scheduled_stops=t.ScheduledStops(),
        overheating=bool(t.Overheating()),
        detached=bool(t.Detached()),
        headlights=bool(t.Headlights()),
        dent_severity=tuple(t.DentSeverity(i) for i in range(t.DentSeverityLength())),
        last_impact_et=t.LastImpactEt(),
        last_impact_magnitude=t.LastImpactMagnitude(),
        last_impact_pos=_vec3_fbs(t.LastImpactPos()),
        engine_torque=t.EngineTorque(),
        current_sector=t.CurrentSector(),
        speed_limiter=t.SpeedLimiter(),
        max_gears=t.MaxGears(),
        front_tire_compound_index=t.FrontTireCompoundIndex(),
        rear_tire_compound_index=t.RearTireCompoundIndex(),
        fuel_capacity=t.FuelCapacity(),
        front_flap_activated=t.FrontFlapActivated(),
        rear_flap_activated=t.RearFlapActivated(),
        rear_flap_legal_status=t.RearFlapLegalStatus(),
        ignition_starter=t.IgnitionStarter(),
        front_tire_compound_name=front_compound.decode("utf-8") if front_compound else "",
        rear_tire_compound_name=rear_compound.decode("utf-8") if rear_compound else "",
        speed_limiter_available=t.SpeedLimiterAvailable(),
        anti_stall_activated=t.AntiStallActivated(),
        visual_steering_wheel_range=t.VisualSteeringWheelRange(),
        rear_brake_bias=t.RearBrakeBias(),
        turbo_boost_pressure=t.TurboBoostPressure(),
        physics_to_graphics_offset=tuple(
            t.PhysicsToGraphicsOffset(i) for i in range(t.PhysicsToGraphicsOffsetLength())
        ),
        physical_steering_wheel_range=t.PhysicalSteeringWheelRange(),
        battery_charge_fraction=t.BatteryChargeFraction(),
        electric_boost_motor_torque=t.ElectricBoostMotorTorque(),
        electric_boost_motor_rpm=t.ElectricBoostMotorRpm(),
        electric_boost_motor_temperature=t.ElectricBoostMotorTemperature(),
        electric_boost_water_temperature=t.ElectricBoostWaterTemperature(),
        electric_boost_motor_state=t.ElectricBoostMotorState(),
        lmu=_decode_lmu_telemetry_fbs(t.Lmu()),
        wheels=(
            _decode_telem_wheel_fbs(t.Wheels(0)),
            _decode_telem_wheel_fbs(t.Wheels(1)),
            _decode_telem_wheel_fbs(t.Wheels(2)),
            _decode_telem_wheel_fbs(t.Wheels(3)),
        ),
    )


def _decode_lmu_vehicle_scoring_fbs(lv) -> LMUVehicleScoringExtension:  # type: ignore[no-untyped-def]
    if lv is None:
        return LMUVehicleScoringExtension()
    return LMUVehicleScoringExtension(fuel_fraction=float(lv.FuelFraction()), track_limits_steps=lv.TrackLimitsSteps())


def _decode_vehicle_scoring_fbs(v: _VehicleScoringFB.VehicleScoring) -> VehicleScoring:
    driver_name, veh_name = v.DriverName(), v.VehicleName()
    veh_class, pit_group = v.VehicleClass(), v.PitGroup()
    return VehicleScoring(
        id=v.Id(),
        driver_name=driver_name.decode("utf-8") if driver_name else "",
        vehicle_name=veh_name.decode("utf-8") if veh_name else "",
        total_laps=v.TotalLaps(),
        sector=v.Sector(),
        finish_status=v.FinishStatus(),
        vehicle_lap_dist=v.VehicleLapDist(),
        path_lateral=v.PathLateral(),
        track_edge=v.TrackEdge(),
        best_sector1=v.BestSector1(),
        best_sector2=v.BestSector2(),
        best_lap_time=v.BestLapTime(),
        last_sector1=v.LastSector1(),
        last_sector2=v.LastSector2(),
        last_lap_time=v.LastLapTime(),
        cur_sector1=v.CurSector1(),
        cur_sector2=v.CurSector2(),
        num_pitstops=v.NumPitstops(),
        num_penalties=v.NumPenalties(),
        is_player=bool(v.IsPlayer()),
        control=v.Control(),
        in_pits=bool(v.InPits()),
        place=v.Place(),
        vehicle_class=veh_class.decode("utf-8") if veh_class else "",
        time_behind_next=v.TimeBehindNext(),
        laps_behind_next=v.LapsBehindNext(),
        time_behind_leader=v.TimeBehindLeader(),
        laps_behind_leader=v.LapsBehindLeader(),
        lap_start_et=v.LapStartEt(),
        pos=_vec3_fbs(v.Pos()),
        local_vel=_vec3_fbs(v.LocalVel()),
        local_accel=_vec3_fbs(v.LocalAccel()),
        ori=(_vec3_fbs(v.Ori0()), _vec3_fbs(v.Ori1()), _vec3_fbs(v.Ori2())),
        local_rot=_vec3_fbs(v.LocalRot()),
        local_rot_accel=_vec3_fbs(v.LocalRotAccel()),
        headlights=v.Headlights(),
        pit_state=v.PitState(),
        server_scored=v.ServerScored(),
        individual_phase=v.IndividualPhase(),
        qualification=v.Qualification(),
        time_into_lap=v.TimeIntoLap(),
        estimated_lap_time=v.EstimatedLapTime(),
        pit_group=pit_group.decode("utf-8") if pit_group else "",
        flag=v.Flag(),
        under_yellow=bool(v.UnderYellow()),
        count_lap_flag=v.CountLapFlag(),
        in_garage_stall=bool(v.InGarageStall()),
        pit_lap_dist=v.PitLapDist(),
        best_lap_sector1=v.BestLapSector1(),
        best_lap_sector2=v.BestLapSector2(),
        lmu=_decode_lmu_vehicle_scoring_fbs(v.Lmu()),
    )


def _decode_lmu_scoring_session_fbs(lmu) -> LMUScoringExtension:  # type: ignore[no-untyped-def]
    if lmu is None:
        return LMUScoringExtension()
    return LMUScoringExtension(
        track_grip_level=lmu.TrackGripLevel(),
        track_limits_steps_per_point=lmu.TrackLimitsStepsPerPoint(),
        track_limits_steps_per_penalty=lmu.TrackLimitsStepsPerPenalty(),
        time_of_day_seconds=float(lmu.TimeOfDaySeconds()),
    )


def decode_full_scoring_fbs(data: bytes) -> FullScoringSession | None:
    """Decodes a FullScoringSession FlatBuffer (packet type 4), including all embedded vehicles."""
    if not data:
        return None
    fs = _FullScoringSessionFB.FullScoringSession.GetRootAs(data, 0)
    track_name, player_name, plr_file_name = fs.TrackName(), fs.PlayerName(), fs.PlrFileName()
    vehicles = [_decode_vehicle_scoring_fbs(fs.Vehicles(i)) for i in range(fs.VehiclesLength())]

    return FullScoringSession(
        track_name=track_name.decode("utf-8") if track_name else "",
        session=fs.Session(),
        current_et=fs.CurrentEt(),
        end_et=fs.EndEt(),
        max_laps=fs.MaxLaps(),
        total_lap_dist=fs.TotalLapDist(),
        num_vehicles=len(vehicles),
        game_phase=fs.GamePhase(),
        yellow_flag_state=fs.YellowFlagState(),
        sector_flags=(fs.SectorFlag0(), fs.SectorFlag1(), fs.SectorFlag2()),
        start_light=fs.StartLight(),
        num_red_lights=fs.NumRedLights(),
        in_realtime=bool(fs.InRealtime()),
        player_name=player_name.decode("utf-8") if player_name else "",
        plr_file_name=plr_file_name.decode("utf-8") if plr_file_name else "",
        dark_cloud=fs.DarkCloud(),
        raining=fs.Raining(),
        ambient_temp=fs.AmbientTemp(),
        track_temp=fs.TrackTemp(),
        wind=_vec3_fbs(fs.Wind()),
        min_path_wetness=fs.MinPathWetness(),
        max_path_wetness=fs.MaxPathWetness(),
        avg_path_wetness=fs.AvgPathWetness(),
        lmu=_decode_lmu_scoring_session_fbs(fs.Lmu()),
        vehicles=vehicles,
    )
