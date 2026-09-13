"""
isiMotor-RawUDP Python Client Package
High-performance, zero-overhead telemetry & scoring reader for Le Mans Ultimate and rFactor 2.

Installation, Steam detection & JSON configuration helpers live in the
`isimotor_rawudp_client.install` subpackage (see its `__all__`), and are not
re-exported here to keep the top-level namespace focused on the telemetry API.
"""

from isimotor_rawudp_types import (
    CompactScoring,
    EcuState,
    ExtendedState,
    ForceFeedback,
    FullScoringSession,
    Graphics,
    HWControlCommand,
    LMUCompoundType,
    LMUScoringExtension,
    LMUTelemetryExtension,
    LMUVehicleScoringExtension,
    LMUWheelExtension,
    PhysicsOptions,
    SystemEvent,
    TelemInfo,
    TelemVect3,
    TelemWheel,
    VehicleScoring,
    WeatherControl,
    WeatherControlCommand,
)

from .client import IsiMotorClient
from .decoder import (
    decode_compact_scoring,
    decode_ecu_state,
    decode_extended_state,
    decode_force_feedback,
    decode_full_scoring,
    decode_graphics,
    decode_hw_control,
    decode_lmu_scoring_extension,
    decode_lmu_telemetry_extension,
    decode_lmu_vehicle_scoring_extension,
    decode_lmu_wheel_extension,
    decode_system_event,
    decode_telemetry,
    decode_weather,
    decode_weather_control,
    encode_hw_control,
    encode_weather_control,
)
from .flatbuffer_single_packet_client import FlatBufferSinglePacketClient
from .flatbuffer_single_packet_client_factory import FlatBufferSinglePacketClientFactory
from .raw_single_packet_client import RawSinglePacketClient
from .raw_single_packet_client_factory import RawSinglePacketClientFactory
from .single_packet_client import SinglePacketClient
from .single_packet_client_factory import SinglePacketClientFactory

__version__ = "0.6.2"
__all__ = [
    "CompactScoring",
    "EcuState",
    "ExtendedState",
    "FlatBufferSinglePacketClient",
    "FlatBufferSinglePacketClientFactory",
    "ForceFeedback",
    "FullScoringSession",
    "Graphics",
    "HWControlCommand",
    "IsiMotorClient",
    "LMUCompoundType",
    "LMUScoringExtension",
    "LMUTelemetryExtension",
    "LMUVehicleScoringExtension",
    "LMUWheelExtension",
    "PhysicsOptions",
    "RawSinglePacketClient",
    "RawSinglePacketClientFactory",
    "SinglePacketClient",
    "SinglePacketClientFactory",
    "SystemEvent",
    "TelemInfo",
    "TelemVect3",
    "TelemWheel",
    "VehicleScoring",
    "WeatherControl",
    "WeatherControlCommand",
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
