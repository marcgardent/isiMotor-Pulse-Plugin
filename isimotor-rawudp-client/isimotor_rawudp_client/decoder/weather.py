"""
Environmental conditions and weather grid decoder.
"""

import struct

from ..constants import WEATHER_SIZE, WEATHER_STRUCT
from ..models import WeatherControl


def decode_weather(data: bytes, offset: int = 0) -> WeatherControl | None:
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
