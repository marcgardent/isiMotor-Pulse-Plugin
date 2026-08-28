"""
isiMotor-RawUDP Python Client Package
High-performance, zero-overhead telemetry & scoring reader for Le Mans Ultimate and rFactor 2.
"""

from .models import (
    RawUdpHeader,
    TelemInfo,
    TelemWheel,
    TelemVect3,
    CompactScoring,
    FullScoringSession,
    VehicleScoring,
    TrackRulesParticipant,
    TrackRulesSession,
    PitMenu,
    WeatherControl,
    SystemEvent,
)
from .decoder import (
    decode_header,
    decode_packet,
    decode_telemetry,
    decode_compact_scoring,
    decode_full_scoring,
    decode_vehicle_scoring,
    decode_track_rules_participant,
    decode_track_rules,
    decode_pit_menu,
    decode_weather,
    decode_system_event,
)
from .client import IsiMotorClient

__version__ = "1.2.0"
__all__ = [
    "IsiMotorClient",
    "RawUdpHeader",
    "TelemInfo",
    "TelemWheel",
    "TelemVect3",
    "CompactScoring",
    "FullScoringSession",
    "VehicleScoring",
    "TrackRulesParticipant",
    "TrackRulesSession",
    "PitMenu",
    "WeatherControl",
    "SystemEvent",
    "decode_header",
    "decode_packet",
    "decode_telemetry",
    "decode_compact_scoring",
    "decode_full_scoring",
    "decode_vehicle_scoring",
    "decode_track_rules_participant",
    "decode_track_rules",
    "decode_pit_menu",
    "decode_weather",
    "decode_system_event",
]
