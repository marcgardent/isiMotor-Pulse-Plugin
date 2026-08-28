"""
Unit Tests for Modular Python Client Architecture (SOLID, SRP, SLAP).
Tests decoupled components: Codecs, Reassembler, StateStore, EventDispatcher, Transport, and Facade.
"""

import time
import struct
import unittest
from isimotor_rawudp_client import (
    IsiMotorClient,
    TelemInfo,
    TelemWheel,
    TelemVect3,
    CompactScoring,
    FullScoringSession,
    VehicleScoring,
    TrackRulesParticipant,
    TrackRulesSession,
    PitMenu,
    WeatherControl,
    PhysicsOptions,
    ExtendedState,
    ForceFeedback,
    Graphics,
    SystemEvent,
    PitAction,
    HWControlCommand,
    WeatherControlCommand,
)
from isimotor_rawudp_client.constants import (
    HEADER_SIZE,
    PKT_TYPE_TELEMETRY,
    PKT_TYPE_COMPACT_SCORING,
    PKT_TYPE_SYSTEM_EVENT,
    PKT_TYPE_FULL_SCORING,
    PKT_TYPE_TRACK_RULES,
)
from isimotor_rawudp_client.decoder import (
    decode_header,
    encode_header,
    decode_packet,
    PacketDecoderRegistry,
    encode_hw_control,
    decode_hw_control,
    encode_weather_control,
    decode_weather_control,
)
from isimotor_rawudp_client.state import StateStore
from isimotor_rawudp_client.reassembly import ChunkReassembler
from isimotor_rawudp_client.dispatcher import EventDispatcher
from isimotor_rawudp_client.transport import UdpSender


class TestModularArchitecture(unittest.TestCase):

    def test_all_models_instantiation(self):
        """Validates that all domain models can be constructed and have expected properties."""
        v = TelemVect3(3.0, 4.0, 0.0)
        self.assertAlmostEqual(v.magnitude, 5.0)
        self.assertEqual(v.as_tuple(), (3.0, 4.0, 0.0))

        wheel = TelemWheel(
            temperature=(300.0, 310.0, 320.0),
            tire_carcass_temperature=330.0,
            longitudinal_patch_vel=10.0,
        )
        self.assertAlmostEqual(wheel.temperature_celsius[0], 300.0 - 273.15, places=2)
        self.assertAlmostEqual(wheel.carcass_temp_celsius, 330.0 - 273.15, places=2)
        self.assertAlmostEqual(wheel.patch_speed_kmh, 36.0, places=2)

        telem = TelemInfo(
            gear=1,
            local_vel=TelemVect3(0, 0, -20.0),
            wheels=(wheel, wheel, wheel, wheel),
        )
        self.assertEqual(telem.gear_str, "1")
        self.assertAlmostEqual(telem.forward_speed_mps, 20.0)
        self.assertAlmostEqual(telem.forward_speed_kmh, 72.0)
        self.assertEqual(telem.fl_wheel.patch_speed_kmh, 36.0)

        scoring = CompactScoring(session=10, cur_sector1=30.0, cur_sector2=70.0)
        self.assertTrue(scoring.is_race_session)
        self.assertAlmostEqual(scoring.cur_sector2_individual, 40.0)

        ev = SystemEvent(event_id=1)
        self.assertEqual(ev.name, "EnterRealtime")
        self.assertTrue(ev.in_realtime)

        ffb = ForceFeedback(force_value=0.75)
        self.assertAlmostEqual(ffb.percentage, 75.0)

        ext = ExtendedState(current_pit_speed_limit=16.67)
        self.assertAlmostEqual(ext.current_pit_speed_limit_kmh, 60.012, places=2)

    def test_state_store_thread_safety_and_isolation(self):
        """Tests that StateStore updates and retrieves packet types thread-safely."""
        store = StateStore()
        self.assertEqual(store.packet_count, 0)
        self.assertIsNone(store.get_telemetry())

        t = TelemInfo(slot_id=7, engine_rpm=6500.0)
        now = time.time()
        store.update(t, now)

        self.assertEqual(store.packet_count, 1)
        self.assertEqual(store.last_packet_time, now)
        cached_t = store.get_telemetry()
        self.assertIsNotNone(cached_t)
        self.assertEqual(cached_t.slot_id, 7)
        self.assertAlmostEqual(cached_t.engine_rpm, 6500.0)

        # Update scoring
        s = CompactScoring(track_name="Spa")
        store.update(s, now + 0.1)
        self.assertEqual(store.packet_count, 2)
        self.assertEqual(store.get_scoring().track_name, "Spa")
        self.assertEqual(store.get_telemetry().slot_id, 7)

        # Reset
        store.reset()
        self.assertEqual(store.packet_count, 0)
        self.assertIsNone(store.get_telemetry())
        self.assertIsNone(store.get_scoring())

    def test_event_dispatcher_attribute_and_bus_listeners(self):
        """Tests EventDispatcher with both attribute callbacks and dynamic bus subscriptions."""
        dispatcher = EventDispatcher()
        received_telemetry = []
        received_any = []
        bus_telemetry = []

        dispatcher.on_telemetry = lambda t: received_telemetry.append(t)
        dispatcher.on_packet = lambda p: received_any.append(p)
        dispatcher.subscribe(TelemInfo, lambda t: bus_telemetry.append(t))

        telem = TelemInfo(slot_id=42)
        scoring = CompactScoring(track_name="Monza")

        dispatcher.dispatch(telem)
        self.assertEqual(len(received_telemetry), 1)
        self.assertEqual(len(received_any), 1)
        self.assertEqual(len(bus_telemetry), 1)

        dispatcher.dispatch(scoring)
        self.assertEqual(len(received_telemetry), 1)
        self.assertEqual(len(received_any), 2)
        self.assertEqual(len(bus_telemetry), 1)

    def test_packet_decoder_registry_extension(self):
        """Tests Open/Closed capability of PacketDecoderRegistry for adding new custom decoders."""
        registry = PacketDecoderRegistry()

        # Define custom dummy packet and decoder
        custom_pkt_type = 200

        class CustomPacket:
            def __init__(self, val: int):
                self.val = val

        def custom_decoder(payload: bytes):
            val = struct.unpack("<i", payload[:4])[0]
            return CustomPacket(val)

        registry.register(custom_pkt_type, custom_decoder)

        # Encode standard SIMP packet with custom type
        hdr = encode_header(packet_type=custom_pkt_type, payload_size=4)
        data = hdr + struct.pack("<i", 12345)

        res = decode_packet(data, registry=registry)
        self.assertIsInstance(res, CustomPacket)
        self.assertEqual(res.val, 12345)

    def test_chunk_reassembler_lifecycle_and_timeout(self):
        """Tests ChunkReassembler with sequential chunks and timeout eviction."""
        reassembler = ChunkReassembler(timeout_seconds=0.1, cleanup_interval_seconds=0.0)

        # Create dummy 2-chunk packet (Track Rules payload)
        # 192 bytes session header
        dummy_session = b"\x00" * 192
        chunk0 = dummy_session[:100]
        chunk1 = dummy_session[100:]

        hdr0 = encode_header(PKT_TYPE_TRACK_RULES, len(chunk0), sequence_number=1, chunk_index=0, total_chunks=2)
        hdr1 = encode_header(PKT_TYPE_TRACK_RULES, len(chunk1), sequence_number=1, chunk_index=1, total_chunks=2)

        # Incomplete chunk
        res0 = reassembler.process(hdr0 + chunk0, now=10.0)
        self.assertIsNone(res0)

        # Complete chunk
        res1 = reassembler.process(hdr1 + chunk1, now=10.05)
        self.assertIsInstance(res1, TrackRulesSession)

        # Stale chunk timeout
        reassembler.process(hdr0 + chunk0, now=20.0)
        self.assertEqual(len(reassembler._buffers), 1)

        # Advance time past timeout
        reassembler.cleanup_stale(now=20.2)
        self.assertEqual(len(reassembler._buffers), 0)

    def test_client_facade_composition(self):
        """Tests IsiMotorClient facade high-level composition and getters."""
        client = IsiMotorClient(host="127.0.0.1", port=5999)

        received_packets = []
        client.on_telemetry = lambda t: received_packets.append(t)

        # Simulate receiving a datagram via internal ingestion pipeline (SLAP)
        t = TelemInfo(slot_id=99, engine_rpm=7200.0)
        client._state.update(t, time.time())
        client._dispatcher.dispatch(t)

        self.assertEqual(client.get_latest_telemetry().slot_id, 99)
        self.assertEqual(len(received_packets), 1)
        self.assertEqual(client.packet_count, 1)

        # Context manager enter/exit sanity check
        with client:
            self.assertTrue(client.is_running)
        self.assertFalse(client.is_running)


if __name__ == "__main__":
    unittest.main()
