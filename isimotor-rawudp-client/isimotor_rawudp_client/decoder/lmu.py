"""
Le Mans Ultimate (LMU) and modern WEC simulation binary decoders.
Decodes extended telemetry and scoring structures embedded within expansion zones.
"""

import struct

from ..models.lmu import (
    LMUCompoundType,
    LMUScoringExtension,
    LMUTelemetryExtension,
    LMUVehicleScoringExtension,
    LMUWheelExtension,
)
from .base import _decode_string
from .ecu import decode_ecu_state

# Telemetry extension format after the 20 ECU bytes:
# offset 20: 1B track_limits_steps, 3x padding, 2d (virtual_energy, regen), 32s vehicle_model
_LMU_TELEM_REST_FORMAT = struct.Struct("<B3x2d32s")

# Wheel extension: offset 0: 1B compound_type, 3x pad, 1d brake_wear
_LMU_WHEEL_FORMAT = struct.Struct("<B3xd")

# Scoring session extension: offset 0: 3B (grip, steps_per_pt, steps_per_penalty), 1x pad, 1f (time_of_day)
_LMU_SCORING_FORMAT = struct.Struct("<3B1xf")

# Vehicle scoring extension: offset 0: 2B (fuel_fraction, track_limits_steps)
_LMU_VEH_SCORING_FORMAT = struct.Struct("<2B")


def decode_lmu_telemetry_extension(data: bytes, offset: int = 737) -> LMUTelemetryExtension:
    """
    Decodes the 111-byte LMU telemetry extension from TelemInfoV01::mExpansion.
    """
    if len(data) - offset < 20:
        return LMUTelemetryExtension()

    ecu = decode_ecu_state(data, offset)

    # Decode additional LMU telemetry if sufficient buffer length
    if len(data) - offset >= 72:
        steps, v_energy, regen, model_raw = _LMU_TELEM_REST_FORMAT.unpack_from(data, offset + 20)
        return LMUTelemetryExtension(
            ecu=ecu,
            virtual_energy=float(v_energy),
            regen_kw=float(regen),
            track_limits_steps=int(steps),
            vehicle_model=_decode_string(model_raw),
        )

    return LMUTelemetryExtension(ecu=ecu)


def decode_lmu_wheel_extension(data: bytes, offset: int) -> LMUWheelExtension:
    """
    Decodes the 24-byte LMU wheel extension from TelemWheelV01::mExpansion.
    """
    if len(data) - offset < 12:
        return LMUWheelExtension()

    compound_val, brake_wear = _LMU_WHEEL_FORMAT.unpack_from(data, offset)
    try:
        compound = LMUCompoundType(compound_val)
    except ValueError:
        compound = LMUCompoundType.UNKNOWN

    return LMUWheelExtension(
        compound_type=compound,
        brake_wear_meters=float(brake_wear),
    )


def decode_lmu_scoring_extension(data: bytes, offset: int = 284) -> LMUScoringExtension:
    """
    Decodes the 200-byte LMU session scoring extension from ScoringInfoV01::mExpansion.
    """
    if len(data) - offset < 8:
        return LMUScoringExtension()

    grip, steps_pt, steps_pen, tod = _LMU_SCORING_FORMAT.unpack_from(data, offset)
    return LMUScoringExtension(
        track_grip_level=int(grip),
        track_limits_steps_per_point=int(steps_pt),
        track_limits_steps_per_penalty=int(steps_pen),
        time_of_day_seconds=float(tod),
    )


def decode_lmu_vehicle_scoring_extension(data: bytes, offset: int = 536) -> LMUVehicleScoringExtension:
    """
    Decodes the 48-byte LMU vehicle scoring extension from VehicleScoringInfoV01::mExpansion.
    """
    if len(data) - offset < 2:
        return LMUVehicleScoringExtension()

    fuel_byte, cut_steps = _LMU_VEH_SCORING_FORMAT.unpack_from(data, offset)
    return LMUVehicleScoringExtension(
        fuel_fraction=fuel_byte / 255.0,
        track_limits_steps=int(cut_steps),
    )
