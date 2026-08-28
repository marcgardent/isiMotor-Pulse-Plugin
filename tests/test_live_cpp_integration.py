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
from isimotor_rawudp_client.decoder import decode_telemetry, decode_compact_scoring, decode_system_event

MOCK_BIN = os.path.join(os.path.dirname(__file__), "cpp_mock", "isi_mock_host")
TEST_PORT = 5066


class TestLiveCppIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(MOCK_BIN):
            subprocess.run(["make", "-C", os.path.join(os.path.dirname(__file__), "cpp_mock")], check=True)
        assert os.path.exists(MOCK_BIN), f"Failed to find or build {MOCK_BIN}"

    def test_live_cpp_mock_streaming(self):
        """
        Tests live UDP stream from native C++ isi_mock_host @ 100Hz.
        Receives and validates 50+ frames over socket.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", TEST_PORT))
        sock.settimeout(2.0)

        # Spawn C++ mock transmitter: 100 Hz for 2 seconds
        proc = subprocess.Popen(
            [MOCK_BIN, "--serve", str(TEST_PORT), "100", "2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        telem_packets = []
        scoring_packets = []
        event_packets = []

        start_time = time.time()
        try:
            while time.time() - start_time < 1.5:
                try:
                    data, addr = sock.recvfrom(65535)
                    if len(data) == 1888:
                        t = decode_telemetry(data)
                        if t:
                            telem_packets.append(t)
                    elif data.startswith(b"SIMP") and len(data) == 168:
                        s = decode_compact_scoring(data)
                        if s:
                            scoring_packets.append(s)
                    elif data.startswith(b"SIMP") and len(data) == 6:
                        ev = decode_system_event(data)
                        if ev:
                            event_packets.append(ev)
                except socket.timeout:
                    break
        finally:
            sock.close()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
            proc.wait(timeout=3)

        # Assertions
        self.assertGreaterEqual(len(event_packets), 1, "Expected at least 1 SystemEvent packet")
        self.assertEqual(event_packets[0].event_id, 1)
        self.assertEqual(event_packets[0].name, "EnterRealtime")

        self.assertGreaterEqual(len(telem_packets), 50, f"Expected 50+ telemetry packets, received {len(telem_packets)}")
        self.assertGreaterEqual(len(scoring_packets), 1, f"Expected scoring packets, received {len(scoring_packets)}")

        # Validate physical dynamics in stream
        first_t = telem_packets[0]
        last_t = telem_packets[-1]

        self.assertGreater(last_t.elapsed_time, first_t.elapsed_time)
        self.assertEqual(first_t.vehicle_name, "Ferrari 499P #51")
        self.assertEqual(first_t.track_name, "Circuit de la Sarthe - Le Mans")
        self.assertGreaterEqual(first_t.engine_rpm, 4000.0)
        self.assertLessEqual(first_t.engine_rpm, 10000.0)

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
            stderr=subprocess.PIPE
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
        self.assertGreaterEqual(received_count, target_hz - 5, f"Expected ~{target_hz} pkts, got {received_count}")
        self.assertLessEqual(received_count, target_hz + 5, f"Expected ~{target_hz} pkts, got {received_count}")


if __name__ == "__main__":
    unittest.main()
