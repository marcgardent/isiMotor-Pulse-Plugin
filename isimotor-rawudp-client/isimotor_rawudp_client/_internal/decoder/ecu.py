"""
Electronic Control Unit (ECU) and onboard driver aids binary decoder.
"""

import struct

from isimotor_rawudp_types.ecu import EcuState

# 20 consecutive unsigned 8-bit integers (20 bytes)
_ECU_FORMAT = struct.Struct("<20B")


def decode_ecu_state(data: bytes, offset: int = 737) -> EcuState:
    """
    Decodes the 111-byte expansion block at offset 737 (mExpansion / LMUExtendedTelemetry).
    Extracts LMU native electronic aids (TC, ABS, Engine Maps, ARBs, Wipers, Lift&Coast).
    """
    if len(data) - offset < 20:
        return EcuState()

    (
        tc,
        tc_max,
        tc_cut,
        tc_cut_max,
        tc_slip,
        tc_slip_max,
        abs_lvl,
        abs_max,
        tc_act,
        abs_act,
        m_map,
        m_map_max,
        mig,
        mig_max,
        f_arb,
        f_arb_max,
        r_arb,
        r_arb_max,
        wiper,
        lnc,
    ) = _ECU_FORMAT.unpack_from(data, offset)

    return EcuState(
        tc_active=bool(tc_act),
        abs_active=bool(abs_act),
        tc_level=int(tc) if tc_max > 0 else -1,
        tc_max=int(tc_max),
        tc_cut=int(tc_cut) if tc_cut_max > 0 else -1,
        tc_cut_max=int(tc_cut_max),
        tc_slip=int(tc_slip) if tc_slip_max > 0 else -1,
        tc_slip_max=int(tc_slip_max),
        abs_level=int(abs_lvl) if abs_max > 0 else -1,
        abs_max=int(abs_max),
        motor_map=int(m_map) if m_map_max > 0 else -1,
        motor_map_max=int(m_map_max),
        brake_migration=int(mig) if mig_max > 0 else -1,
        brake_migration_max=int(mig_max),
        front_arb=int(f_arb) if f_arb_max > 0 else -1,
        front_arb_max=int(f_arb_max),
        rear_arb=int(r_arb) if r_arb_max > 0 else -1,
        rear_arb_max=int(r_arb_max),
        wiper_state=int(wiper),
        lift_and_coast=lnc / 255.0,
    )
