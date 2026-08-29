"""
Test Suite: Live End-to-End C++ Mock Host Integration
Spawns the compiled C++ isi_mock_host binary as a subprocess and tests real-time
UDP packet reception and decoding over 127.0.0.1.
"""

import os
import socket
import subprocess
import time
import unittest

from isimotor_rawudp_client.client import IsiMotorClient
from isimotor_rawudp_client.decoder.header import decode_header
from isimotor_rawudp_client.models import PitAction

MOCK_BIN = os.path.join(os.path.dirname(__file__), "cpp_mock", "isi_mock_host")
TEST_PORT = 5066


class TestLiveCppIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(MOCK_BIN):
            subprocess.run(
                ["make", "-C", os.path.join(os.path.dirname(__file__), "cpp_mock")],
                check=True,
            )
        assert os.path.exists(MOCK_BIN), f"Failed to find or build {MOCK_BIN}"

    def test_live_cpp_mock_streaming(self):
        """
        Tests live UDP stream from native C++ isi_mock_host @ 100Hz using IsiMotorClient.
        Receives and validates telemetry, compact scoring, full scoring grid, and system events.
        """
        client = IsiMotorClient(host="127.0.0.1", port=TEST_PORT)

        telem_list = []
        compact_scoring_list = []
        full_scoring_list = []
        track_rules_list = []
        pit_menu_list = []
        weather_list = []
        ext_state_list = []
        ffb_list = []
        gfx_list = []
        event_list = []

        client.on_telemetry = lambda t: telem_list.append(t)
        client.on_scoring = lambda s: compact_scoring_list.append(s)
        client.on_full_scoring = lambda fs: full_scoring_list.append(fs)
        client.on_track_rules = lambda tr: track_rules_list.append(tr)
        client.on_pit_menu = lambda pm: pit_menu_list.append(pm)
        client.on_weather = lambda w: weather_list.append(w)
        client.on_extended_state = lambda ext: ext_state_list.append(ext)
        client.on_force_feedback = lambda ffb: ffb_list.append(ffb)
        client.on_graphics = lambda gfx: gfx_list.append(gfx)
        client.on_system_event = lambda ev: event_list.append(ev)

        client.start()

        # Spawn C++ mock transmitter: 100 Hz for 2 seconds
        proc = subprocess.Popen(
            [MOCK_BIN, "--serve", str(TEST_PORT), "100", "2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        time.sleep(1.8)
        client.stop()

        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
        proc.wait(timeout=3)

        # Assertions
        self.assertGreaterEqual(len(event_list), 1, "Expected SystemEvent packet")
        self.assertEqual(event_list[0].event_id, 1)

        self.assertGreaterEqual(len(telem_list), 50, f"Expected 50+ telemetry packets, received {len(telem_list)}")
        self.assertGreaterEqual(
            len(compact_scoring_list), 1, f"Expected compact scoring packets, received {len(compact_scoring_list)}"
        )
        self.assertGreaterEqual(
            len(full_scoring_list), 1, f"Expected full scoring packets, received {len(full_scoring_list)}"
        )
        self.assertGreaterEqual(
            len(track_rules_list), 1, f"Expected track rules packets, received {len(track_rules_list)}"
        )
        self.assertGreaterEqual(len(pit_menu_list), 10, f"Expected pit menu packets, received {len(pit_menu_list)}")
        self.assertGreaterEqual(len(weather_list), 1, f"Expected weather packets, received {len(weather_list)}")
        self.assertGreaterEqual(
            len(ext_state_list), 1, f"Expected extended state packets, received {len(ext_state_list)}"
        )
        self.assertGreaterEqual(len(ffb_list), 50, f"Expected 50+ FFB packets, received {len(ffb_list)}")
        self.assertGreaterEqual(len(gfx_list), 10, f"Expected 10+ graphics packets, received {len(gfx_list)}")

        # Validate multi-car full scoring
        latest_fs = full_scoring_list[-1]
        self.assertEqual(latest_fs.track_name, "Circuit de la Sarthe - Le Mans")
        self.assertEqual(latest_fs.num_vehicles, 3)
        self.assertEqual(len(latest_fs.vehicles), 3)

        leaderboard = latest_fs.leaderboard
        self.assertEqual(leaderboard[0].place, 1)
        self.assertEqual(leaderboard[0].driver_name, "Marc Gardent")
        self.assertEqual(leaderboard[1].place, 2)
        self.assertEqual(leaderboard[1].driver_name, "Kamui Kobayashi")
        self.assertEqual(leaderboard[2].place, 3)
        self.assertEqual(leaderboard[2].driver_name, "Kevin Estre")

        # Validate Track Rules
        latest_tr = track_rules_list[-1]
        self.assertTrue(latest_tr.is_safety_car_active)
        self.assertTrue(latest_tr.is_caution_active)
        self.assertEqual(latest_tr.stage_str, "Caution Update")
        self.assertEqual(len(latest_tr.participants), 3)
        self.assertEqual(latest_tr.participants[0].message, "Follow Safety Car")

        # Validate Pit Menu
        latest_pm = pit_menu_list[-1]
        self.assertEqual(latest_pm.category_name, "Tires")
        self.assertEqual(latest_pm.choice_string, "Soft Slick")
        self.assertEqual(latest_pm.num_choices, 4)

        # Validate Weather
        latest_w = weather_list[-1]
        self.assertAlmostEqual(latest_w.ambient_temp_c, 24.5, places=1)
        self.assertAlmostEqual(latest_w.origin_raining, 0.05, places=2)

        # Validate Extended State (FR-05)
        latest_ext = ext_state_list[-1]
        self.assertEqual(latest_ext.physics.traction_control_str, "Medium")
        self.assertEqual(latest_ext.physics.anti_lock_brakes_str, "Low")
        self.assertTrue(latest_ext.physics.auto_clutch)
        self.assertTrue(latest_ext.physics.auto_blip)
        self.assertAlmostEqual(latest_ext.current_pit_speed_limit_kmh, 60.0, places=1)
        self.assertGreater(latest_ext.accumulated_impact_magnitude, 3000.0)

        # Validate Force Feedback (FR-06)
        latest_ffb = ffb_list[-1]
        self.assertGreaterEqual(latest_ffb.percentage, 0.0)
        self.assertLessEqual(latest_ffb.percentage, 100.0)

        # Validate Graphics (FR-06)
        latest_gfx = gfx_list[-1]
        self.assertEqual(latest_gfx.slot_id, 42)
        self.assertEqual(latest_gfx.camera_type_str, "Cockpit")
        self.assertTrue(latest_gfx.is_cockpit_view)

        # Validate physical dynamics in stream
        first_t = telem_list[0]
        last_t = telem_list[-1]
        self.assertGreater(last_t.elapsed_time, first_t.elapsed_time)
        self.assertEqual(first_t.vehicle_name, "Ferrari 499P #51")

    def test_live_frequency_rate_throttling(self):
        """
        Tests that rate-limiting accurately constrains packet stream frequency (e.g. 30Hz).
        """
        target_hz = 30
        duration = 1.0
        port = 5077

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        sock.settimeout(1.5)

        proc = subprocess.Popen(
            [MOCK_BIN, "--serve", str(port), str(target_hz), str(duration)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        received_count = 0
        start_time = time.time()
        try:
            while time.time() - start_time < duration + 0.5:
                try:
                    data, _ = sock.recvfrom(65535)
                    hdr = decode_header(data)
                    if hdr and hdr.packet_type == 1 and hdr.chunk_index == 0:
                        received_count += 1
                except TimeoutError:
                    break
        finally:
            sock.close()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            proc.wait(timeout=2)

        # Expected ~30 packets for 1.0s stream at 30Hz (allow +/- 5 frames tolerance)
        self.assertGreaterEqual(received_count, target_hz - 5, f"Expected ~{target_hz} pkts, got {received_count}")
        self.assertLessEqual(received_count, target_hz + 5, f"Expected ~{target_hz} pkts, got {received_count}")

    def test_live_bidirectional_control(self):
        """
        Tests live bi-directional UDP communication (FR-07):
        - Sending Pit Menu actions (PitMenuDown)
        - Sending Hardware controls (TCIncrease)
        - Injecting dynamic weather overrides (ambient_temp, raining)
        """
        port = 5090
        inbound_port = 5091

        client = IsiMotorClient(host="127.0.0.1", port=port, inbound_host="127.0.0.1", inbound_port=inbound_port)
        weather_updates = []
        pit_menu_updates = []

        client.on_weather = lambda w: weather_updates.append(w)
        client.on_pit_menu = lambda p: pit_menu_updates.append(p)
        client.start()

        proc = subprocess.Popen(
            [MOCK_BIN, "--serve", str(port), "100", "2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # Wait for mock server to be listening
            time.sleep(0.3)

            # 1. Send PitMenuDown action
            res_pit = client.send_pit_action(PitAction.MENU_DOWN)
            self.assertTrue(res_pit, "send_pit_action returned False")

            # 2. Send HW control
            res_hw = client.send_hw_control("TCIncrease", control_value=1.0, duration_ms=50)
            self.assertTrue(res_hw, "send_hw_control returned False")

            # 3. Send dynamic weather override
            res_weather = client.send_weather_override(ambient_temp=36.5, raining=0.80)
            self.assertTrue(res_weather, "send_weather_override returned False")

            time.sleep(1.0)
        finally:
            client.stop()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            proc.wait(timeout=2)

        # Validate that the weather override was received by the mock host and reflected in the live stream
        self.assertTrue(
            any(abs(w.ambient_temp_c - 36.5) < 0.5 for w in weather_updates),
            f"Expected weather override (36.5°C) in stream: {[w.ambient_temp_c for w in weather_updates]}",
        )


if __name__ == "__main__":
    unittest.main()
