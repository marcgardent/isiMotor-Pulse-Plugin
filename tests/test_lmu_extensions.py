"""
Unit Tests for Le Mans Ultimate (LMU) Extended Telemetry & Scoring Data.
Tests strict OOP separation, SOLID principles, and binary decoders for all LMU extension zones.

End-to-end LMU-within-TelemInfo/FullScoringSession integration is covered by
tests/test_golden_truth.py's telemetry/full_scoring tests, which decode real
FlatBuffers produced by the C++ mock host (Types 1 and 4 are FlatBuffers now,
not raw memcpy'd structs, so synthetic byte buffers can no longer stand in
for them here).
"""

import struct
import unittest

from isimotor_rawudp_client import (
    LMUCompoundType,
    LMUScoringExtension,
    LMUTelemetryExtension,
    LMUVehicleScoringExtension,
    LMUWheelExtension,
)
from isimotor_rawudp_client._internal.decoder import (
    decode_lmu_scoring_extension,
    decode_lmu_telemetry_extension,
    decode_lmu_vehicle_scoring_extension,
    decode_lmu_wheel_extension,
)


class TestLMUExtensions(unittest.TestCase):
    def test_lmu_models_oop_defaults(self):
        """Validates default states and domain helpers of LMU models."""
        telem_ext = LMUTelemetryExtension()
        self.assertFalse(telem_ext.has_hypercar_energy)
        self.assertEqual(telem_ext.virtual_energy, 0.0)
        self.assertEqual(telem_ext.regen_kw, 0.0)
        self.assertEqual(telem_ext.vehicle_model, "")

        wheel_ext = LMUWheelExtension()
        self.assertEqual(wheel_ext.compound_type, LMUCompoundType.UNKNOWN)
        self.assertEqual(wheel_ext.brake_wear_meters, 0.0)

        scoring_ext = LMUScoringExtension()
        self.assertEqual(scoring_ext.track_grip_level, 0)
        self.assertEqual(scoring_ext.grip_fraction, 0.0)
        self.assertEqual(scoring_ext.time_of_day_str, "00:00:00")

        veh_scoring_ext = LMUVehicleScoringExtension()
        self.assertEqual(veh_scoring_ext.fuel_fraction, 0.0)
        self.assertEqual(veh_scoring_ext.track_limits_steps, 0)

    def test_decode_lmu_telemetry_extension(self):
        """Validates unpacking of Hypercar energy, live regen, model, and ECU aids."""
        # 111 bytes buffer:
        # [0..19]: 20B ECU (TC=2, TCMax=8, ABS=3, ABSMax=10, TCActive=1, ABSActive=0)
        # [20]: 1B track_limits_steps (2)
        # [21..23]: 3B padding
        # [24..31]: 1d virtual_energy (0.85)
        # [32..39]: 1d regen (150.0 kW)
        # [40..71]: 32s vehicle_model ("Ferrari 499P")
        # [72..110]: 39B reserved
        raw_ext = bytearray(111)

        # ECU
        ecu_bytes = struct.pack("<20B", 2, 8, 1, 5, 2, 5, 3, 10, 1, 0, 1, 4, 2, 5, 1, 5, 2, 5, 1, 200)
        raw_ext[0:20] = ecu_bytes

        # Rest of LMU telemetry
        struct.pack_into("<B3x2d32s", raw_ext, 20, 2, 0.85, 150.0, b"Ferrari 499P")

        ext = decode_lmu_telemetry_extension(bytes(raw_ext), offset=0)

        self.assertTrue(ext.ecu.tc_active)
        self.assertFalse(ext.ecu.abs_active)
        self.assertEqual(ext.ecu.tc_level, 2)
        self.assertEqual(ext.ecu.abs_level, 3)
        self.assertTrue(ext.has_hypercar_energy)
        self.assertAlmostEqual(ext.virtual_energy, 0.85)
        self.assertAlmostEqual(ext.regen_kw, 150.0)
        self.assertEqual(ext.track_limits_steps, 2)
        self.assertEqual(ext.vehicle_model, "Ferrari 499P")

    def test_decode_lmu_wheel_extension(self):
        """Validates unpacking of wheel compound enum and brake wear."""
        # 24 bytes buffer:
        # [0]: 1B compound (3 = HARD)
        # [1..3]: 3B padding
        # [4..11]: 1d brake_wear (0.028 meters)
        # [12..23]: 12B reserved
        raw_wheel_ext = bytearray(24)
        struct.pack_into("<B3xd", raw_wheel_ext, 0, 3, 0.028)

        w_ext = decode_lmu_wheel_extension(bytes(raw_wheel_ext), offset=0)

        self.assertEqual(w_ext.compound_type, LMUCompoundType.HARD)
        self.assertEqual(str(w_ext.compound_type), "Hard")
        self.assertAlmostEqual(w_ext.brake_wear_meters, 0.028)

    def test_decode_lmu_scoring_session_extension(self):
        """Validates unpacking of session grip, solar time of day, and track limits rules."""
        raw_scoring_ext = bytearray(200)
        # grip=3 (Optimum / 0.75), steps_per_point=3, steps_per_penalty=9, time_of_day=50400.0 (14:00:00)
        struct.pack_into("<3B1xf", raw_scoring_ext, 0, 3, 3, 9, 50400.0)

        s_ext = decode_lmu_scoring_extension(bytes(raw_scoring_ext), offset=0)

        self.assertEqual(s_ext.track_grip_level, 3)
        self.assertAlmostEqual(s_ext.grip_fraction, 0.75)
        self.assertEqual(s_ext.track_limits_steps_per_point, 3)
        self.assertEqual(s_ext.track_limits_steps_per_penalty, 9)
        self.assertEqual(s_ext.time_of_day_str, "14:00:00")

    def test_decode_lmu_vehicle_scoring_extension(self):
        """Validates unpacking of opponent fuel fraction and cuts count."""
        raw_veh_ext = bytearray(48)
        # fuel=191 (~75%), cuts=3
        struct.pack_into("<2B", raw_veh_ext, 0, 191, 3)

        v_ext = decode_lmu_vehicle_scoring_extension(bytes(raw_veh_ext), offset=0)

        self.assertAlmostEqual(v_ext.fuel_fraction, 191 / 255.0, places=3)
        self.assertEqual(v_ext.track_limits_steps, 3)


if __name__ == "__main__":
    unittest.main()
