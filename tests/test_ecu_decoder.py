"""
Unit Tests for LMU Electronic Aids & ECU Telemetry Decoder (SOLID, SRP, SLAP).
Tests EcuState dataclass, binary decoding from mExpansion (offset 737), and integration in TelemInfo.
"""

import struct
import unittest

from isimotor_rawudp_client import (
    EcuState,
    decode_ecu_state,
    decode_telemetry,
)
from isimotor_rawudp_client.constants import TELEMINFO_SIZE


class TestEcuDecoder(unittest.TestCase):
    def test_ecu_state_defaults(self):
        """Validates default values and helper properties of EcuState."""
        ecu = EcuState()
        self.assertFalse(ecu.tc_active)
        self.assertFalse(ecu.abs_active)
        self.assertEqual(ecu.tc_level, -1)
        self.assertEqual(ecu.tc_max, 0)
        self.assertFalse(ecu.has_tc)
        self.assertFalse(ecu.has_abs)
        self.assertFalse(ecu.has_motor_map)
        self.assertFalse(ecu.has_brake_migration)
        self.assertEqual(ecu.lift_and_coast, 0.0)

    def test_decode_ecu_state_active_aids(self):
        """Validates unpacking of active TC, ABS, levels, and ECU maps."""
        # 20 bytes representing LMUExtendedTelemetry:
        # mTC=3, mTCMax=8, mTCCut=2, mTCCutMax=5, mTCSlip=4, mTCSlipMax=6,
        # mABS=5, mABSMax=10, mTCActive=1, mABSActive=1,
        # mMotorMap=2, mMotorMapMax=4, mMigration=3, mMigrationMax=5,
        # mFrontAntiSway=2, mFrontAntiSwayMax=5, mRearAntiSway=1, mRearAntiSwayMax=5,
        # mWiperState=2, mLiftAndCoastProgress=128
        raw_ecu = struct.pack(
            "<20B",
            3, 8, 2, 5, 4, 6,
            5, 10, 1, 1,
            2, 4, 3, 5,
            2, 5, 1, 5,
            2, 128
        )

        ecu = decode_ecu_state(raw_ecu, offset=0)

        self.assertTrue(ecu.tc_active)
        self.assertTrue(ecu.abs_active)
        self.assertEqual(ecu.tc_level, 3)
        self.assertEqual(ecu.tc_max, 8)
        self.assertTrue(ecu.has_tc)
        self.assertEqual(ecu.tc_cut, 2)
        self.assertEqual(ecu.tc_cut_max, 5)
        self.assertEqual(ecu.tc_slip, 4)
        self.assertEqual(ecu.tc_slip_max, 6)
        self.assertEqual(ecu.abs_level, 5)
        self.assertEqual(ecu.abs_max, 10)
        self.assertTrue(ecu.has_abs)
        self.assertEqual(ecu.motor_map, 2)
        self.assertEqual(ecu.motor_map_max, 4)
        self.assertTrue(ecu.has_motor_map)
        self.assertEqual(ecu.brake_migration, 3)
        self.assertEqual(ecu.brake_migration_max, 5)
        self.assertTrue(ecu.has_brake_migration)
        self.assertEqual(ecu.front_arb, 2)
        self.assertEqual(ecu.front_arb_max, 5)
        self.assertEqual(ecu.rear_arb, 1)
        self.assertEqual(ecu.rear_arb_max, 5)
        self.assertEqual(ecu.wiper_state, 2)
        self.assertAlmostEqual(ecu.lift_and_coast, 128 / 255.0, places=4)

    def test_decode_ecu_state_zero_or_rf2_defaults(self):
        """Validates that all zeros (e.g. standard rF2 packet) produce disabled/clean ECU state."""
        raw_zeros = bytes(20)
        ecu = decode_ecu_state(raw_zeros, offset=0)

        self.assertFalse(ecu.tc_active)
        self.assertFalse(ecu.abs_active)
        self.assertEqual(ecu.tc_level, -1)
        self.assertEqual(ecu.abs_level, -1)
        self.assertEqual(ecu.motor_map, -1)
        self.assertFalse(ecu.has_tc)
        self.assertFalse(ecu.has_abs)

    def test_full_telemetry_packet_ecu_integration(self):
        """Validates that decode_telemetry correctly unpacks ECU state at offset 737."""
        buffer = bytearray(TELEMINFO_SIZE)

        # Populate slot ID at offset 0
        struct.pack_into("<i", buffer, 0, 42)

        # Populate ECU fields at offset 737:
        # TC=4, TCMax=10, ABS=2, ABSMax=8, TCActive=1, ABSActive=0
        ecu_bytes = struct.pack(
            "<20B",
            4, 10, 0, 0, 0, 0,
            2, 8, 1, 0,
            1, 3, 0, 0,
            0, 0, 0, 0,
            1, 255
        )
        buffer[737 : 737 + len(ecu_bytes)] = ecu_bytes

        telem = decode_telemetry(bytes(buffer))
        self.assertIsNotNone(telem)
        self.assertEqual(telem.slot_id, 42)
        self.assertTrue(telem.ecu.tc_active)
        self.assertFalse(telem.ecu.abs_active)
        self.assertEqual(telem.ecu.tc_level, 4)
        self.assertEqual(telem.ecu.tc_max, 10)
        self.assertEqual(telem.ecu.abs_level, 2)
        self.assertEqual(telem.ecu.abs_max, 8)
        self.assertEqual(telem.ecu.motor_map, 1)
        self.assertEqual(telem.ecu.wiper_state, 1)
        self.assertAlmostEqual(telem.ecu.lift_and_coast, 1.0, places=4)


if __name__ == "__main__":
    unittest.main()
