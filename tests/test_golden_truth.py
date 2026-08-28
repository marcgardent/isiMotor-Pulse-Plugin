"""
Test Suite: Golden Dataset Byte-for-Byte Cross Validation
Validates Python decoder against ground-truth datasets dumped by native C++ isi_mock_host.
"""

import json
import os
import struct
import unittest
from isimotor_rawudp_client.models import RawUdpHeader
from isimotor_rawudp_client.decoder import (
    decode_header,
    decode_telemetry,
    decode_compact_scoring,
    decode_full_scoring,
    decode_system_event,
    decode_packet,
    HEADER_SIZE,
)
from isimotor_rawudp_client.client import IsiMotorClient

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

    def test_full_scoring_golden_decoding(self):
        bin_path = os.path.join(GOLDEN_DIR, "full_scoring_golden.bin")
        json_path = os.path.join(GOLDEN_DIR, "full_scoring_golden.json")

        self.assertTrue(os.path.exists(bin_path), f"Golden bin missing at {bin_path}")
        self.assertTrue(os.path.exists(json_path), f"Golden json missing at {json_path}")

        with open(bin_path, "rb") as f:
            data = f.read()
        with open(json_path, "r", encoding="utf-8") as f:
            truth = json.load(f)

        expected_size = 284 + 3 * 584
        self.assertEqual(len(data), expected_size, f"Expected {expected_size} bytes, got {len(data)}")

        fs = decode_full_scoring(data)
        self.assertIsNotNone(fs, "Full scoring decode returned None")

        self.assertEqual(fs.track_name, truth["track_name"])
        self.assertEqual(fs.session, truth["session"])
        self.assertAlmostEqual(fs.current_et, truth["current_et"], places=3)
        self.assertAlmostEqual(fs.end_et, truth["end_et"], places=1)
        self.assertEqual(fs.max_laps, truth["max_laps"])
        self.assertAlmostEqual(fs.lap_dist, truth["lap_dist"], places=1)
        self.assertEqual(fs.num_vehicles, 3)
        self.assertAlmostEqual(fs.ambient_temp, truth["ambient_temp"], places=1)
        self.assertAlmostEqual(fs.track_temp, truth["track_temp"], places=1)

        # Validate Grid Vehicles
        self.assertEqual(len(fs.vehicles), 3)

        # Car 1 (Player)
        v0 = fs.vehicles[0]
        self.assertEqual(v0.id, 51)
        self.assertEqual(v0.driver_name, "Marc Gardent")
        self.assertEqual(v0.vehicle_name, "Ferrari 499P #51")
        self.assertEqual(v0.vehicle_class, "Hypercar")
        self.assertEqual(v0.place, 1)
        self.assertTrue(v0.is_player)
        self.assertFalse(v0.in_pits)
        self.assertAlmostEqual(v0.best_lap_time, 204.850, places=3)

        # Car 2
        v1 = fs.vehicles[1]
        self.assertEqual(v1.id, 7)
        self.assertEqual(v1.driver_name, "Kamui Kobayashi")
        self.assertEqual(v1.place, 2)
        self.assertFalse(v1.is_player)
        self.assertAlmostEqual(v1.time_behind_leader, 1.450, places=3)

        # Car 3 (In Pits)
        v2 = fs.vehicles[2]
        self.assertEqual(v2.id, 6)
        self.assertEqual(v2.driver_name, "Kevin Estre")
        self.assertEqual(v2.place, 3)
        self.assertTrue(v2.in_pits)
        self.assertEqual(v2.pit_state, 3)
        self.assertEqual(v2.num_pitstops, 2)

        # Validate Leaderboard helper
        leaderboard = fs.leaderboard
        self.assertEqual([c.place for c in leaderboard], [1, 2, 3])
        self.assertEqual(fs.player_vehicle.id, 51)

    def test_header_decoding(self):
        # Pack sample 24-byte header
        hdr_bytes = struct.pack("<4sBBHIdBBH", b"SIMP", 1, 4, 1200, 105, 1250.5, 0, 2, 3)
        self.assertEqual(len(hdr_bytes), HEADER_SIZE)

        hdr = decode_header(hdr_bytes)
        self.assertIsNotNone(hdr)
        self.assertEqual(hdr.magic, b"SIMP")
        self.assertEqual(hdr.protocol_version, 1)
        self.assertEqual(hdr.packet_type, 4)
        self.assertEqual(hdr.payload_size, 1200)
        self.assertEqual(hdr.sequence_number, 105)
        self.assertAlmostEqual(hdr.session_et, 1250.5, places=1)
        self.assertEqual(hdr.chunk_index, 0)
        self.assertEqual(hdr.total_chunks, 2)
        self.assertEqual(hdr.sub_type_or_id, 3)

    def test_chunk_slicing_and_reassembly(self):
        bin_path = os.path.join(GOLDEN_DIR, "full_scoring_golden.bin")
        with open(bin_path, "rb") as f:
            full_data = f.read()

        client = IsiMotorClient()
        chunk_size = 1200
        total_chunks = (len(full_data) + chunk_size - 1) // chunk_size

        chunk0_payload = full_data[0:chunk_size]
        hdr0 = struct.pack("<4sBBHIdBBH", b"SIMP", 1, 4, len(chunk0_payload), 42, 100.0, 0, total_chunks, 3)
        pkt0 = hdr0 + chunk0_payload

        chunk1_payload = full_data[chunk_size:]
        hdr1 = struct.pack("<4sBBHIdBBH", b"SIMP", 1, 4, len(chunk1_payload), 42, 100.0, 1, total_chunks, 3)
        pkt1 = hdr1 + chunk1_payload

        # Process chunk 0 (incomplete)
        res0 = client._process_chunk(pkt0, 1000.0)
        self.assertIsNone(res0, "Expected None while chunks are incomplete")

        # Process chunk 1 (complete)
        res1 = client._process_chunk(pkt1, 1000.0)
        self.assertIsNotNone(res1, "Expected FullScoringSession upon assembling all chunks")
        self.assertEqual(res1.num_vehicles, 3)
        self.assertEqual(res1.track_name, "Circuit de la Sarthe - Le Mans")
        self.assertEqual(len(res1.vehicles), 3)

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
