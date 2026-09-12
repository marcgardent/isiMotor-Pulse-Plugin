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
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import ForceFeedback as _ForceFeedbackFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import HWControl as _HWControlFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import InboundCommand as _InboundCommandFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import SystemEvent as _SystemEventFB
from isimotor_rawudp_types.fbs_generated.isimotor.fbs import WeatherControl as _WeatherControlFB


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
    """Encodes an InboundCommand FlatBuffer wrapping a HWControl payload (packet type 100)."""
    builder = flatbuffers.Builder(96)
    name_offset = builder.CreateString(control_name)
    _HWControlFB.Start(builder)
    _HWControlFB.AddControlName(builder, name_offset)
    _HWControlFB.AddControlValue(builder, control_value)
    _HWControlFB.AddDurationMs(builder, duration_ms)
    hw_offset = _HWControlFB.End(builder)

    _InboundCommandFB.Start(builder)
    _InboundCommandFB.AddPayloadType(builder, _CommandPayload.CommandPayload.HWControl)
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
    """Encodes an InboundCommand FlatBuffer wrapping a WeatherControl payload (packet type 101)."""
    builder = flatbuffers.Builder(128)
    _WeatherControlFB.Start(builder)
    _WeatherControlFB.AddAmbientTemp(builder, ambient_temp)
    _WeatherControlFB.AddTrackTemp(builder, track_temp)
    _WeatherControlFB.AddDarkCloud(builder, dark_cloud)
    _WeatherControlFB.AddRaining(builder, raining)
    _WeatherControlFB.AddWindSpeed(builder, wind_speed)
    _WeatherControlFB.AddWindDirection(builder, wind_direction)
    _WeatherControlFB.AddMinPathWetness(builder, min_path_wetness)
    _WeatherControlFB.AddMaxPathWetness(builder, max_path_wetness)
    wc_offset = _WeatherControlFB.End(builder)

    _InboundCommandFB.Start(builder)
    _InboundCommandFB.AddPayloadType(builder, _CommandPayload.CommandPayload.WeatherControl)
    _InboundCommandFB.AddPayload(builder, wc_offset)
    root = _InboundCommandFB.End(builder)
    builder.Finish(root)
    return bytes(builder.Output())


def decode_hw_control_fbs(data: bytes) -> tuple[str, float, int] | None:
    """Decodes an InboundCommand FlatBuffer's HWControl payload, if present."""
    cmd = _InboundCommandFB.InboundCommand.GetRootAs(data, 0)
    if cmd.PayloadType() != _CommandPayload.CommandPayload.HWControl:
        return None
    table = cmd.Payload()
    if table is None:
        return None
    hw = _HWControlFB.HWControl()
    hw.Init(table.Bytes, table.Pos)
    name = hw.ControlName()
    return (name.decode("utf-8") if name else "", hw.ControlValue(), hw.DurationMs())


def decode_weather_control_fbs(data: bytes) -> tuple[float, float, float, float, float, float, float, float] | None:
    """Decodes an InboundCommand FlatBuffer's WeatherControl payload, if present."""
    cmd = _InboundCommandFB.InboundCommand.GetRootAs(data, 0)
    if cmd.PayloadType() != _CommandPayload.CommandPayload.WeatherControl:
        return None
    table = cmd.Payload()
    if table is None:
        return None
    wc = _WeatherControlFB.WeatherControl()
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
