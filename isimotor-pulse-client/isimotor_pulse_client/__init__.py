"""
isiMotor-Pulse Python Client Package
High-performance, zero-overhead telemetry & scoring reader for Le Mans Ultimate and rFactor 2.

Installation, Steam detection & JSON configuration helpers live in the
`isimotor_pulse_client.install` subpackage (see its `__all__`), and are not
re-exported here to keep the top-level namespace focused on the telemetry API.

The `decode_*`/`encode_*` codec functions are intentionally NOT re-exported
here: the public client types (`IsiMotorClient`, `DomainSinglePacketClient`,
`DtoSinglePacketClient`) already decode for you, and `RawSinglePacketClient`
hands out undecoded bytes precisely for callers who want to plug in their own
codec. A caller who really wants this package's own codecs reaches into
`isimotor_pulse_client._internal.decoder` explicitly - no compatibility
guarantee is made for anything imported from there.
"""

from isimotor_pulse_types import (
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

from ._internal.domain_single_packet_client import DomainSinglePacketClient
from ._internal.dto_single_packet_client import DtoSinglePacketClient
from ._internal.raw_single_packet_client import RawSinglePacketClient
from .client import IsiMotorClient
from .domain_single_packet_client_factory import DomainSinglePacketClientFactory
from .dto_single_packet_client_factory import DtoSinglePacketClientFactory
from .raw_single_packet_client_factory import RawSinglePacketClientFactory

__version__ = "1.0.3"
__all__ = [
    "CompactScoring",
    "DomainSinglePacketClient",
    "DomainSinglePacketClientFactory",
    "DtoSinglePacketClient",
    "DtoSinglePacketClientFactory",
    "EcuState",
    "ExtendedState",
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
    "SystemEvent",
    "TelemInfo",
    "TelemVect3",
    "TelemWheel",
    "VehicleScoring",
    "WeatherControl",
    "WeatherControlCommand",
]
