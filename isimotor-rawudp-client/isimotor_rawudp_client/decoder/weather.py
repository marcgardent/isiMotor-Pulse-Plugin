"""
Environmental conditions and weather grid decoder.

Wire format: FlatBuffers (schemas/weather.fbs), one message per packet type 7
(its own ZeroMQ port), no header/framing.
"""

from isimotor_rawudp_types import WeatherControl

from .fbs_codec import decode_weather_fbs, encode_weather_fbs


def decode_weather(data: bytes, offset: int = 0) -> WeatherControl | None:
    """Decodes a WeatherControl FlatBuffer payload (packet type 7)."""
    fields = decode_weather_fbs(data[offset:] if offset else data)
    if fields is None:
        return None
    return WeatherControl(**fields)


def encode_weather(weather: WeatherControl) -> bytes:
    """Encodes a WeatherControl FlatBuffer payload (packet type 7)."""
    return encode_weather_fbs(
        {
            "et": weather.et,
            "raining": weather.raining,
            "cloudiness": weather.cloudiness,
            "ambient_temp_k": weather.ambient_temp_k,
            "wind_max_speed": weather.wind_max_speed,
            "apply_cloudiness_instantly": weather.apply_cloudiness_instantly,
        }
    )
