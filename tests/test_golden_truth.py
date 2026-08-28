"""
Test Suite: Golden Dataset Byte-for-Byte Cross Validation
Validates Python decoder against ground-truth datasets dumped by native C++ isi_mock_host.
"""

import json
import os
import unittest
from isimotor_rawudp_client.decoder import decode_telemetry, decode_compact_scoring, decode_system_event

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


class TestGoldenTruth(unittest.TestCase):

    def test_telemetry_golden_decoding(self):
        bin_path = os.path.join(GOLDEN_DIR, "telemetry_golden.bin")
        json_path = os.path.join(GOLDEN_DIR, "telemetry_golden.json")

        self.assertTrue(os.path.exists(bin_path), f"Golden bin missing at {bin_path}")
        self.assertTrue(os.path.exists(json_path), f"Golden json missing at {json_path}")

        with open(bin_path, "rb") as f:
            data = f.read()
        with open(json_path, "r", encoding="utf-8") as f:
            truth = json.load(f)

        self.assertEqual(len(data), 1888, f"Expected 1888 bytes, got {len(data)}")
        t = decode_telemetry(data)
        self.assertIsNotNone(t, "Telemetry decode returned None")

        # Validate Core Identification & Session
        self.assertEqual(t.slot_id, truth["slot_id"])
        self.assertAlmostEqual(t.delta_time, truth["delta_time"], places=4)
        self.assertAlmostEqual(t.elapsed_time, truth["elapsed_time"], places=3)
        self.assertEqual(t.lap_number, truth["lap_number"])
        self.assertAlmostEqual(t.lap_start_et, truth["lap_start_et"], places=3)
        self.assertEqual(t.vehicle_name, truth["vehicle_name"])
        self.assertEqual(t.track_name, truth["track_name"])

        # Validate Kinematics (Positions & Velocities)
        self.assertAlmostEqual(t.pos.x, truth["pos"][0], places=2)
        self.assertAlmostEqual(t.pos.y, truth["pos"][1], places=2)
        self.assertAlmostEqual(t.pos.z, truth["pos"][2], places=2)

        self.assertAlmostEqual(t.local_vel.x, truth["local_vel"][0], places=2)
        self.assertAlmostEqual(t.local_vel.y, truth["local_vel"][1], places=2)
        self.assertAlmostEqual(t.local_vel.z, truth["local_vel"][2], places=2)

        self.assertAlmostEqual(t.local_accel.x, truth["local_accel"][0], places=2)
        self.assertAlmostEqual(t.local_accel.y, truth["local_accel"][1], places=2)
        self.assertAlmostEqual(t.local_accel.z, truth["local_accel"][2], places=2)

        # Validate Powertrain & Inputs
        self.assertEqual(t.gear, truth["gear"])
        self.assertAlmostEqual(t.engine_rpm, truth["engine_rpm"], places=1)
        self.assertAlmostEqual(t.engine_water_temp, truth["engine_water_temp"], places=1)
        self.assertAlmostEqual(t.engine_oil_temp, truth["engine_oil_temp"], places=1)
        self.assertAlmostEqual(t.unfiltered_throttle, truth["unfiltered_throttle"], places=3)
        self.assertAlmostEqual(t.unfiltered_brake, truth["unfiltered_brake"], places=3)
        self.assertAlmostEqual(t.unfiltered_steering, truth["unfiltered_steering"], places=3)

        # Validate Fuel & Hybrid
        self.assertAlmostEqual(t.fuel, truth["fuel"], places=2)
        self.assertAlmostEqual(t.fuel_capacity, truth["fuel_capacity"], places=2)
        self.assertAlmostEqual(t.battery_charge_fraction, truth["battery_charge_fraction"], places=3)
        self.assertAlmostEqual(t.electric_boost_motor_torque, truth["electric_boost_motor_torque"], places=1)
        self.assertAlmostEqual(t.electric_boost_motor_rpm, truth["electric_boost_motor_rpm"], places=1)

        # Validate 4 Wheels
        self.assertEqual(len(t.wheels), 4)
        for idx, w in enumerate(t.wheels):
            wt = truth["wheels"][idx]
            self.assertAlmostEqual(w.suspension_deflection, wt["suspension_deflection"], places=3)
            self.assertAlmostEqual(w.ride_height, wt["ride_height"], places=3)
            self.assertAlmostEqual(w.susp_force, wt["susp_force"], places=1)
            self.assertAlmostEqual(w.brake_temp, wt["brake_temp"], places=1)
            self.assertAlmostEqual(w.pressure, wt["pressure"], places=1)
            self.assertAlmostEqual(w.wear, wt["wear"], places=3)
            self.assertEqual(w.terrain_name, wt["terrain_name"])
            self.assertAlmostEqual(w.temperature_celsius[0], wt["temp_celsius"][0], places=1)
            self.assertAlmostEqual(w.temperature_celsius[1], wt["temp_celsius"][1], places=1)
            self.assertAlmostEqual(w.temperature_celsius[2], wt["temp_celsius"][2], places=1)

    def test_scoring_golden_decoding(self):
        bin_path = os.path.join(GOLDEN_DIR, "scoring_golden.bin")
        json_path = os.path.join(GOLDEN_DIR, "scoring_golden.json")

        with open(bin_path, "rb") as f:
            data = f.read()
        with open(json_path, "r", encoding="utf-8") as f:
            truth = json.load(f)

        self.assertEqual(len(data), 168, f"Expected 168 bytes, got {len(data)}")
        s = decode_compact_scoring(data)
        self.assertIsNotNone(s)

        self.assertEqual(s.track_name, truth["track_name"])
        self.assertEqual(s.session, truth["session"])
        self.assertAlmostEqual(s.current_et, truth["current_et"], places=3)
        self.assertAlmostEqual(s.lap_dist, truth["lap_dist"], places=1)
        self.assertEqual(s.max_laps, truth["max_laps"])
        self.assertEqual(s.in_realtime, truth["in_realtime"])
        self.assertEqual(s.total_laps, truth["total_laps"])
        self.assertEqual(s.sector, truth["sector"])
        self.assertAlmostEqual(s.last_lap_time, truth["last_lap_time"], places=3)
        self.assertAlmostEqual(s.best_lap_time, truth["best_lap_time"], places=3)

    def test_event_golden_decoding(self):
        bin_path = os.path.join(GOLDEN_DIR, "event_golden.bin")
        with open(bin_path, "rb") as f:
            data = f.read()

        self.assertEqual(len(data), 6)
        ev = decode_system_event(data)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.event_id, 1)
        self.assertEqual(ev.name, "EnterRealtime")


if __name__ == "__main__":
    unittest.main()
