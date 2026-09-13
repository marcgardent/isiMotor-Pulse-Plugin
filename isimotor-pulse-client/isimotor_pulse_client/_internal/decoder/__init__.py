"""
High-performance binary decoders and encoders for isiMotor / LMU / rFactor 2 raw UDP packets.
"""

from ..constants import (
    COMPACT_SCORING_SIZE,
    EXTENDED_STATE_SIZE,
    EXTENDED_STATE_STRUCT,
    FORCE_FEEDBACK_SIZE,
    FORCE_FEEDBACK_STRUCT,
    FULL_SCORING_SESSION_SIZE,
    GRAPHICS_SIZE,
    GRAPHICS_STRUCT,
    HW_CONTROL_COMMAND_SIZE,
    HW_CONTROL_COMMAND_STRUCT,
    PKT_TYPE_COMPACT_SCORING,
    PKT_TYPE_EXTENDED_STATE,
    PKT_TYPE_FORCE_FEEDBACK,
    PKT_TYPE_FULL_SCORING,
    PKT_TYPE_GRAPHICS,
    PKT_TYPE_HW_CONTROL,
    PKT_TYPE_SYSTEM_EVENT,
    PKT_TYPE_TELEMETRY,
    PKT_TYPE_WEATHER,
    PKT_TYPE_WEATHER_CONTROL,
    SYSTEM_EVENT_SIZE,
    SYSTEM_EVENT_STRUCT,
    TELEMINFO_SIZE,
    VEHICLE_SCORING_SIZE,
    WEATHER_CONTROL_COMMAND_SIZE,
    WEATHER_CONTROL_COMMAND_STRUCT,
    WEATHER_SIZE,
    WEATHER_STRUCT,
)
from .base import _decode_string
from .commands import (
    decode_hw_control,
    decode_weather_control,
    encode_hw_control,
    encode_weather_control,
)
from .ecu import decode_ecu_state
from .events import decode_system_event
from .feedback import decode_force_feedback
from .graphics import decode_graphics
from .lmu import (
    decode_lmu_scoring_extension,
    decode_lmu_telemetry_extension,
    decode_lmu_vehicle_scoring_extension,
    decode_lmu_wheel_extension,
)
from .packet_decoder import AnyPacket
from .physics import decode_extended_state
from .scoring import (
    decode_compact_scoring,
    decode_full_scoring,
)
from .telemetry import decode_telemetry
from .weather import decode_weather

__all__ = [
    "COMPACT_SCORING_SIZE",
    "EXTENDED_STATE_SIZE",
    "EXTENDED_STATE_STRUCT",
    "FORCE_FEEDBACK_SIZE",
    "FORCE_FEEDBACK_STRUCT",
    "FULL_SCORING_SESSION_SIZE",
    "GRAPHICS_SIZE",
    "GRAPHICS_STRUCT",
    "HW_CONTROL_COMMAND_SIZE",
    "HW_CONTROL_COMMAND_STRUCT",
    "PKT_TYPE_COMPACT_SCORING",
    "PKT_TYPE_EXTENDED_STATE",
    "PKT_TYPE_FORCE_FEEDBACK",
    "PKT_TYPE_FULL_SCORING",
    "PKT_TYPE_GRAPHICS",
    "PKT_TYPE_HW_CONTROL",
    "PKT_TYPE_SYSTEM_EVENT",
    "PKT_TYPE_TELEMETRY",
    "PKT_TYPE_WEATHER",
    "PKT_TYPE_WEATHER_CONTROL",
    "SYSTEM_EVENT_SIZE",
    "SYSTEM_EVENT_STRUCT",
    "TELEMINFO_SIZE",
    "VEHICLE_SCORING_SIZE",
    "WEATHER_CONTROL_COMMAND_SIZE",
    "WEATHER_CONTROL_COMMAND_STRUCT",
    "WEATHER_SIZE",
    "WEATHER_STRUCT",
    "AnyPacket",
    "_decode_string",
    "decode_compact_scoring",
    "decode_ecu_state",
    "decode_extended_state",
    "decode_force_feedback",
    "decode_full_scoring",
    "decode_graphics",
    "decode_hw_control",
    "decode_lmu_scoring_extension",
    "decode_lmu_telemetry_extension",
    "decode_lmu_vehicle_scoring_extension",
    "decode_lmu_wheel_extension",
    "decode_system_event",
    "decode_telemetry",
    "decode_weather",
    "decode_weather_control",
    "encode_hw_control",
    "encode_weather_control",
]
