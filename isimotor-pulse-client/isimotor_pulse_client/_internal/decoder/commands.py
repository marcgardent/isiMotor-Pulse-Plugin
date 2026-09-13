"""
Inbound hardware control and weather override encoders and decoders.

Wire format: a single FlatBuffers InboundCommand message (schemas/
inbound_command.fbs) with a CommandPayload union distinguishing HWControl
from WeatherControl - both kinds share the same grouped inbound ZeroMQ port,
so the union (rather than a header byte) is what tells them apart. No
chunking/framing: the ZMQ message boundary IS the FlatBuffer.
"""

from isimotor_pulse_types import HWControlCommand, WeatherControlCommand

from .fbs_codec import (
    decode_hw_control_fbs,
    decode_weather_control_fbs,
    encode_hw_control_fbs,
    encode_weather_control_fbs,
)


def encode_hw_control(control_name: str, control_value: float = 1.0, duration_ms: int = 50) -> bytes:
    """Encodes an InboundCommand FlatBuffer wrapping a HWControl payload (packet type 100)."""
    return encode_hw_control_fbs(control_name, control_value, duration_ms)


def decode_hw_control(data: bytes, offset: int = 0) -> HWControlCommand | None:
    """Decodes an InboundCommand FlatBuffer's HWControl payload (packet type 100)."""
    decoded = decode_hw_control_fbs(data[offset:] if offset else data)
    if decoded is None:
        return None
    control_name, control_value, duration_ms = decoded
    return HWControlCommand(control_name=control_name, control_value=control_value, duration_ms=duration_ms)


def encode_weather_control(
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
    return encode_weather_control_fbs(
        ambient_temp=ambient_temp,
        track_temp=track_temp,
        dark_cloud=dark_cloud,
        raining=raining,
        wind_speed=wind_speed,
        wind_direction=wind_direction,
        min_path_wetness=min_path_wetness,
        max_path_wetness=max_path_wetness,
    )


def decode_weather_control(data: bytes, offset: int = 0) -> WeatherControlCommand | None:
    """Decodes an InboundCommand FlatBuffer's WeatherControl payload (packet type 101)."""
    decoded = decode_weather_control_fbs(data[offset:] if offset else data)
    if decoded is None:
        return None
    ambient_temp, track_temp, dark_cloud, raining, wind_speed, wind_direction, min_path_wetness, max_path_wetness = (
        decoded
    )
    return WeatherControlCommand(
        ambient_temp=ambient_temp,
        track_temp=track_temp,
        dark_cloud=dark_cloud,
        raining=raining,
        wind_speed=wind_speed,
        wind_direction=wind_direction,
        min_path_wetness=min_path_wetness,
        max_path_wetness=max_path_wetness,
    )
