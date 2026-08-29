"""
Extended game state, physics options, and damage decoder.
"""

import struct

from ..constants import EXTENDED_STATE_SIZE, EXTENDED_STATE_STRUCT
from ..models import ExtendedState, PhysicsOptions


def decode_extended_state(data: bytes, offset: int = 0) -> ExtendedState | None:
    """Decodes a 68-byte ExtendedState packet (Type 8)."""
    if len(data) - offset < EXTENDED_STATE_SIZE:
        return None

    unpacked = struct.unpack_from(EXTENDED_STATE_STRUCT, data, offset)
    physics = PhysicsOptions(
        traction_control=unpacked[0],
        anti_lock_brakes=unpacked[1],
        stability_control=unpacked[2],
        auto_shift=unpacked[3],
        auto_clutch=unpacked[4],
        invulnerable=unpacked[5],
        opposite_lock=unpacked[6],
        steering_help=unpacked[7],
        braking_help=unpacked[8],
        spin_recovery=unpacked[9],
        auto_pit=unpacked[10],
        auto_lift=unpacked[11],
        auto_blip=unpacked[12],
        fuel_mult=unpacked[13],
        tire_mult=unpacked[14],
        mech_fail=unpacked[15],
        allow_pitcrew_push=unpacked[16],
        repeat_shifts=unpacked[17],
        hold_clutch=unpacked[18],
        auto_reverse=unpacked[19],
        alternate_neutral=unpacked[20],
        ai_control=unpacked[21],
        manual_shift_override_time=unpacked[22],
        auto_shift_override_time=unpacked[23],
        speed_sensitive_steering=unpacked[24],
        steer_ratio_speed=unpacked[25],
    )

    max_impact = unpacked[26]
    acc_impact = unpacked[27]
    in_rt = bool(unpacked[28])
    session_started = bool(unpacked[29])
    session = unpacked[30]
    pit_speed = unpacked[31]

    return ExtendedState(
        physics=physics,
        max_impact_magnitude=max_impact,
        accumulated_impact_magnitude=acc_impact,
        in_realtime_fc=in_rt,
        session_started=session_started,
        session=session,
        current_pit_speed_limit=pit_speed,
    )
