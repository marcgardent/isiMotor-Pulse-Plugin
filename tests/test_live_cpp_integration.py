"""
Test Suite: Live End-to-End C++ Mock Host Integration
Spawns the compiled C++ isi_mock_host binary as a subprocess and tests real-time
UDP packet reception and decoding over 127.0.0.1.
"""

import os
import subprocess
import time
import socket
import unittest
from isimotor_rawudp_client.client import IsiMotorClient
from isimotor_rawudp_client.decoder import (
    decode_telemetry,
    decode_compact_scoring,
    decode_system_event,
)

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
        event_list = []

        client.on_telemetry = lambda t: telem_list.append(t)
        client.on_scoring = lambda s: compact_scoring_list.append(s)
        client.on_full_scoring = lambda fs: full_scoring_list.append(fs)
        client.on_track_rules = lambda tr: track_rules_list.append(tr)
        client.on_pit_menu = lambda pm: pit_menu_list.append(pm)
        client.on_weather = lambda w: weather_list.append(w)
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

        self.assertGreaterEqual(
            len(telem_list), 50, f"Expected 50+ telemetry packets, received {len(telem_list)}"
        )
        self.assertGreaterEqual(
            len(compact_scoring_list), 1, f"Expected compact scoring packets, received {len(compact_scoring_list)}"
        )
        self.assertGreaterEqual(
            len(full_scoring_list), 1, f"Expected full scoring packets, received {len(full_scoring_list)}"
        )
        self.assertGreaterEqual(
            len(track_rules_list), 1, f"Expected track rules packets, received {len(track_rules_list)}"
        )
        self.assertGreaterEqual(
            len(pit_menu_list), 10, f"Expected pit menu packets, received {len(pit_menu_list)}"
        )
        self.assertGreaterEqual(
            len(weather_list), 1, f"Expected weather packets, received {len(weather_list)}"
        )

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
                    if len(data) == 1888:
                        received_count += 1
                except socket.timeout:
                    break
        finally:
            sock.close()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            proc.wait(timeout=2)

        # Expected ~30 packets for 1.0s stream at 30Hz (allow +/- 5 frames tolerance)
        self.assertGreaterEqual(
            received_count, target_hz - 5, f"Expected ~{target_hz} pkts, got {received_count}"
        )
        self.assertLessEqual(
            received_count, target_hz + 5, f"Expected ~{target_hz} pkts, got {received_count}"
        )


if __name__ == "__main__":
    unittest.main()
