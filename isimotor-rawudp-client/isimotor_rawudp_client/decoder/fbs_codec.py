"""
FlatBuffers encode/decode helpers for the packet types migrated off the
legacy RawUdpHeader + fixed-layout-struct wire format (schemas/*.fbs).

With ZeroMQ/TCP the message boundary already delimits one FlatBuffer, so
there is no header, no chunking, and no framing: `decode_*` functions take
the full raw ZMQ message bytes, and `encode_*` functions return the full
bytes to publish as-is.
"""

import flatbuffers

from isimotor_rawudp_types.fbs_generated.isimotor.fbs import CommandPayload as _CommandPayload
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import CompactScoring as _CompactScoringFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import ExtendedState as _ExtendedStateFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import ForceFeedback as _ForceFeedbackFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import Graphics as _GraphicsFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import HWControlCommand as _HWControlCommandFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import InboundCommand as _InboundCommandFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import PhysicsOptions as _PhysicsOptionsFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import SystemEvent as _SystemEventFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import Vec3 as _Vec3FB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import WeatherControl as _WeatherControlFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import WeatherControlCommand as _WeatherControlCommandFB


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
