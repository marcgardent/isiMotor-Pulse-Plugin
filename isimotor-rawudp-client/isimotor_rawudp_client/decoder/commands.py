"""
Inbound hardware control and weather override encoders and decoders.
"""

import struct

from ..constants import (
    HW_CONTROL_COMMAND_SIZE,
    HW_CONTROL_COMMAND_STRUCT,
    WEATHER_CONTROL_COMMAND_SIZE,
    WEATHER_CONTROL_COMMAND_STRUCT,
)
from ..models import HWControlCommand, WeatherControlCommand
from .base import _decode_string
from .header import encode_header


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


def decode_hw_control(data: bytes, offset: int = 0) -> HWControlCommand | None:
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


def decode_weather_control(data: bytes, offset: int = 0) -> WeatherControlCommand | None:
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
