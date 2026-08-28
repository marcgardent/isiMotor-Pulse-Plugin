"""
isiMotor-RawUDP Python Client Package
High-performance, zero-overhead telemetry reader for Le Mans Ultimate and rFactor 2.
"""

from .models import (
    TelemInfo,
    TelemWheel,
    TelemVect3,
    CompactScoring,
    SystemEvent,
)
from .decoder import (
    decode_packet,
    decode_telemetry,
    decode_compact_scoring,
    decode_system_event,
)
from .client import IsiMotorClient

__version__ = "1.0.0"
__all__ = [
    "IsiMotorClient",
    "TelemInfo",
    "TelemWheel",
    "TelemVect3",
    "CompactScoring",
    "SystemEvent",
    "decode_packet",
    "decode_telemetry",
    "decode_compact_scoring",
    "decode_system_event",
]
