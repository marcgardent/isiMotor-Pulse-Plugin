"""
Unit Tests for Modular Python Client Architecture (SOLID, SRP, SLAP).
Tests decoupled components: Codecs, StateStore, EventDispatcher, Transport, and Facade.
"""

import time
import unittest

from isimotor_pulse_client import (
    CompactScoring,
    ExtendedState,
    ForceFeedback,
    IsiMotorClient,
    PhysicsOptions,
    SystemEvent,
    TelemInfo,
    TelemVect3,
    TelemWheel,
)
from isimotor_pulse_client._internal.dispatcher import EventDispatcher
from isimotor_pulse_client._internal.state import StateStore


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
            longitudinal_ground_vel=8.0,
        )
        self.assertAlmostEqual(wheel.temperature_celsius[0], 300.0 - 273.15, places=2)
        self.assertAlmostEqual(wheel.carcass_temp_celsius, 330.0 - 273.15, places=2)
        self.assertAlmostEqual(wheel.patch_speed_kmh, 36.0, places=2)
        self.assertAlmostEqual(wheel.ground_speed_kmh, 28.8, places=2)
        self.assertAlmostEqual(wheel.slip_ratio, 0.25, places=2)

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

        po = PhysicsOptions(stability_control=2)
        self.assertEqual(po.stability_control_str, "Medium")

        ext = ExtendedState(current_pit_speed_limit=16.67, physics=po)
        self.assertAlmostEqual(ext.current_pit_speed_limit_kmh, 60.012, places=2)
        self.assertEqual(ext.physics.stability_control_str, "Medium")

    def test_state_store_thread_safety_and_isolation(self):
        """Tests that StateStore updates and retrieves packet types thread-safely."""
        store = StateStore()
        self.assertEqual(store.packet_count, 0)
        self.assertIsNone(store.get_telemetry())

        t = TelemInfo(slot_id=7, engine_rpm=6500.0)
        now = time.time()
        store.update_telemetry(t, now)

        self.assertEqual(store.packet_count, 1)
        self.assertEqual(store.last_packet_time, now)
        cached_t = store.get_telemetry()
        self.assertIsNotNone(cached_t)
        self.assertEqual(cached_t.slot_id, 7)
        self.assertAlmostEqual(cached_t.engine_rpm, 6500.0)

        # Update scoring
        s = CompactScoring(track_name="Spa")
        store.update_scoring(s, now + 0.1)
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

        dispatcher.dispatch_telemetry(telem)
        self.assertEqual(len(received_telemetry), 1)
        self.assertEqual(len(received_any), 1)
        self.assertEqual(len(bus_telemetry), 1)

        dispatcher.dispatch_scoring(scoring)
        self.assertEqual(len(received_telemetry), 1)
        self.assertEqual(len(received_any), 2)
        self.assertEqual(len(bus_telemetry), 1)

    def test_client_facade_composition(self):
        """Tests IsiMotorClient facade high-level composition and getters."""
        client = IsiMotorClient(host="127.0.0.1", base_port=5999)

        received_packets = []
        client.on_telemetry = lambda t: received_packets.append(t)

        # Simulate receiving a datagram via internal ingestion pipeline (SLAP)
        t = TelemInfo(slot_id=99, engine_rpm=7200.0)
        client._state.update_telemetry(t, time.time())
        client._dispatcher.dispatch_telemetry(t)

        self.assertEqual(client.get_latest_telemetry().slot_id, 99)
        self.assertEqual(len(received_packets), 1)
        self.assertEqual(client.packet_count, 1)

        # Context manager enter/exit sanity check
        with client:
            self.assertTrue(client.is_running)
        self.assertFalse(client.is_running)


if __name__ == "__main__":
    unittest.main()
