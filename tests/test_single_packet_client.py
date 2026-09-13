"""
Unit tests for the single-packet-type client family (Raw / Domain / Dto).

Mirrors the style of test_client_modular.py: no ZeroMQ mocking, the internal
ingestion pipeline is exercised directly (bypassing the network thread) to
keep tests fast and deterministic.
"""

import time
import unittest

from isimotor_pulse_client import (
    DomainSinglePacketClient,
    DomainSinglePacketClientFactory,
    DtoSinglePacketClient,
    DtoSinglePacketClientFactory,
    RawSinglePacketClient,
    RawSinglePacketClientFactory,
    TelemInfo,
)
from isimotor_pulse_client._internal.constants import PKT_TYPE_COMPACT_SCORING, PKT_TYPE_TELEMETRY
from isimotor_pulse_client._internal.decoder import decode_telemetry


class TestRawSinglePacketClient(unittest.TestCase):
    def test_connects_exactly_one_socket_for_its_packet_type(self):
        """RawSinglePacketClient must open one SUB socket, for its pinned packet_type only."""
        client = RawSinglePacketClient(packet_type=PKT_TYPE_TELEMETRY, base_port=5999)
        self.assertEqual(client._receiver.packet_types, (PKT_TYPE_TELEMETRY,))

    def test_ingestion_pipeline_updates_state_and_invokes_callback(self):
        """Simulates a received datagram via the internal pipeline (no real network)."""
        client = RawSinglePacketClient(packet_type=PKT_TYPE_TELEMETRY, base_port=5999)
        received = []
        client.on_packet = lambda data: received.append(data)

        self.assertIsNone(client.get_latest())
        self.assertEqual(client.packet_count, 0)

        now = time.time()
        client._on_datagram_received(PKT_TYPE_TELEMETRY, b"\x01\x02\x03", now)

        self.assertEqual(client.get_latest(), b"\x01\x02\x03")
        self.assertEqual(client.packet_count, 1)
        self.assertEqual(client.last_packet_time, now)
        self.assertEqual(received, [b"\x01\x02\x03"])

    def test_context_manager_lifecycle(self):
        """Real network open/close sanity check, like test_client_facade_composition."""
        with RawSinglePacketClient(packet_type=PKT_TYPE_TELEMETRY, base_port=5999) as client:
            self.assertTrue(client.is_running)
        self.assertFalse(client.is_running)

    def test_factory_pins_expected_packet_type(self):
        client = RawSinglePacketClientFactory.telemetry(base_port=5999)
        self.assertEqual(client.packet_type, PKT_TYPE_TELEMETRY)
        scoring_client = RawSinglePacketClientFactory.scoring(base_port=5999)
        self.assertEqual(scoring_client.packet_type, PKT_TYPE_COMPACT_SCORING)


class TestDomainSinglePacketClient(unittest.TestCase):
    def test_decodes_via_injected_decoder_and_dispatches(self):
        """A fake decoder stands in for decode_telemetry to avoid building real FlatBuffer bytes."""
        decoded = TelemInfo(slot_id=42)
        client = DomainSinglePacketClient(packet_type=PKT_TYPE_TELEMETRY, decoder=lambda data: decoded, base_port=5999)
        received = []
        client.on_packet = lambda t: received.append(t)

        client._on_raw_packet(b"irrelevant-bytes")

        self.assertIs(client.get_latest(), decoded)
        self.assertEqual(client.packet_count, 1)
        self.assertEqual(received, [decoded])

    def test_decoder_returning_none_is_ignored(self):
        """A malformed/undecodable message must not update state or fire the callback."""
        client = DomainSinglePacketClient(packet_type=PKT_TYPE_TELEMETRY, decoder=lambda data: None, base_port=5999)
        received = []
        client.on_packet = lambda t: received.append(t)

        client._on_raw_packet(b"garbage")

        self.assertIsNone(client.get_latest())
        self.assertEqual(client.packet_count, 0)
        self.assertEqual(received, [])

    def test_factory_builds_telemetry_client_with_real_decoder(self):
        client = DomainSinglePacketClientFactory.telemetry(base_port=5999)
        self.assertEqual(client._raw.packet_type, PKT_TYPE_TELEMETRY)
        self.assertIs(client._decoder, decode_telemetry)

    def test_context_manager_lifecycle(self):
        with DomainSinglePacketClientFactory.telemetry(base_port=5999) as client:
            self.assertTrue(client.is_running)
        self.assertFalse(client.is_running)


class TestDtoSinglePacketClient(unittest.TestCase):
    def test_parses_via_injected_root_parser_and_dispatches(self):
        """A fake root_parser stands in for the real FlatBuffer GetRootAs accessor."""
        parsed_root = object()
        client = DtoSinglePacketClient(
            packet_type=PKT_TYPE_TELEMETRY, root_parser=lambda data: parsed_root, base_port=5999
        )
        received = []
        client.on_packet = lambda root: received.append(root)

        client._on_raw_packet(b"irrelevant-bytes")

        self.assertIs(client.get_latest(), parsed_root)
        self.assertEqual(client.packet_count, 1)
        self.assertEqual(received, [parsed_root])

    def test_empty_payload_is_ignored(self):
        client = DtoSinglePacketClient(
            packet_type=PKT_TYPE_TELEMETRY, root_parser=lambda data: object(), base_port=5999
        )
        client._on_raw_packet(b"")
        self.assertIsNone(client.get_latest())
        self.assertEqual(client.packet_count, 0)

    def test_factory_builds_telemetry_client(self):
        client = DtoSinglePacketClientFactory.telemetry(base_port=5999)
        self.assertEqual(client._raw.packet_type, PKT_TYPE_TELEMETRY)

    def test_context_manager_lifecycle(self):
        with DtoSinglePacketClientFactory.telemetry(base_port=5999) as client:
            self.assertTrue(client.is_running)
        self.assertFalse(client.is_running)


if __name__ == "__main__":
    unittest.main()
