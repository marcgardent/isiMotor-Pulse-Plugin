"""
Unit and SOLID architecture tests for isimotor_rawudp_manager modular refactor.
"""

import unittest

from isimotor_rawudp_client.constants import TELEMINFO_SIZE
from isimotor_rawudp_manager.constants import (
    PKT_RAW_TELEMETRY,
)
from isimotor_rawudp_manager.engine import PacketStats, TelemetryEngine
from isimotor_rawudp_manager.extractors import (
    BaseExtractor,
    ConfigExtractor,
    EventExtractor,
    FeedbackExtractor,
    GraphicsExtractor,
    InboundExtractor,
    PhysicsExtractor,
    ScoringExtractor,
    StatsExtractor,
    TelemetryExtractor,
    WeatherExtractor,
)
from isimotor_rawudp_manager.ui import (
    format_mode_and_hz_to_rate,
    parse_rate_to_mode_and_hz,
)
from isimotor_rawudp_types import (
    CompactScoring,
    ExtendedState,
    ForceFeedback,
    FullScoringSession,
    Graphics,
    PhysicsOptions,
    SystemEvent,
    TelemInfo,
    TelemVect3,
    WeatherControl,
)


class TestManagerSolidArchitecture(unittest.TestCase):
    """Validates SOLID, OOP, and SLAP structure of the refactored manager."""

    def test_extractors_inheritance_and_polymorphism(self):
        """Liskov Substitution & Single Responsibility: All extractors inherit from BaseExtractor."""
        extractors: list[BaseExtractor] = [
            TelemetryExtractor(),
            ScoringExtractor(),
            WeatherExtractor(),
            PhysicsExtractor(),
            FeedbackExtractor(),
            GraphicsExtractor(),
            EventExtractor(),
            StatsExtractor(),
            InboundExtractor(),
            ConfigExtractor(),
        ]
        for ext in extractors:
            self.assertIsInstance(ext, BaseExtractor)
            self.assertTrue(callable(ext.extract))
            self.assertTrue(callable(ext.to_dict))

    def test_telemetry_extractor_and_to_dict(self):
        st = PacketStats("TelemInfo", "Sliced/Raw", "1888 B")
        st.record(TELEMINFO_SIZE, 100.0)

        ext = TelemetryExtractor()
        # Empty telemetry
        empty_rows = ext.extract(None, st)
        self.assertGreater(len(empty_rows), 0)
        self.assertIn("status", [r[0] for r in empty_rows])

        # Populated telemetry
        t = TelemInfo()
        t.slot_id = 2
        t.vehicle_name = "Ferrari 499P"
        t.track_name = "Le Mans"
        t.gear = 6
        t.local_vel = TelemVect3(0.0, 0.0, -83.33)

        rows = ext.extract(t, st)
        keys = [r[0] for r in rows]
        self.assertIn("slot_id", keys)
        self.assertIn("vehicle_name", keys)
        self.assertIn("wheels.fl.rotation", keys)

        d = ext.to_dict(t, st)
        self.assertEqual(d["slot_id"], 2)
        self.assertEqual(d["vehicle_name"], "Ferrari 499P")
        self.assertIn("_channel_diagnostics", d)
        self.assertIn("_computed", d)

    def test_scoring_extractor(self):
        ext = ScoringExtractor()
        cs = CompactScoring(track_name="Spa", session=10, current_et=120.5)
        rows = ext.extract(cs, None)
        keys = [r[0] for r in rows]
        self.assertIn("track_name", keys)
        self.assertIn("session_type", keys)

        fs = FullScoringSession(track_name="Monza", session=10, num_vehicles=20)
        fs_rows = ext.extract(None, fs)
        fs_keys = [r[0] for r in fs_rows]
        self.assertIn("grid.track_name", fs_keys)
        self.assertIn("grid.session_type", fs_keys)

    def test_weather_extractor(self):
        ext = WeatherExtractor()
        w = WeatherControl(ambient_temp_k=298.65, raining=((0.0, 0.0, 0.0), (0.0, 0.2, 0.0), (0.0, 0.0, 0.0)))
        rows = ext.extract(w)
        keys = [r[0] for r in rows]
        self.assertIn("weather.ambient_temp_c", keys)
        self.assertIn("weather.origin_raining", keys)

    def test_physics_extractor(self):
        ext = PhysicsExtractor()
        state = ExtendedState(physics=PhysicsOptions(traction_control=2, anti_lock_brakes=1))
        rows = ext.extract(state)
        keys = [r[0] for r in rows]
        self.assertIn("physics.traction_control", keys)
        self.assertIn("physics.anti_lock_brakes", keys)

    def test_feedback_extractor(self):
        ext = FeedbackExtractor()
        ffb = ForceFeedback(force_value=0.85)
        rows = ext.extract(ffb)
        keys = [r[0] for r in rows]
        self.assertIn("ffb.force_value", keys)
        self.assertIn("ffb.percentage", keys)

    def test_graphics_extractor(self):
        ext = GraphicsExtractor()
        gfx = Graphics(camera_type=0)
        rows = ext.extract(gfx)
        keys = [r[0] for r in rows]
        self.assertIn("camera.type", keys)
        self.assertIn("camera.is_cockpit", keys)

    def test_events_extractor(self):
        ext = EventExtractor()
        ev = SystemEvent(event_id=1)
        rows = ext.extract(ev, event_time=123456.0)
        keys = [r[0] for r in rows]
        self.assertIn("event_id", keys)
        self.assertIn("name", keys)

    def test_stats_and_inbound_extractors(self):
        engine = TelemetryEngine()
        stats_ext = StatsExtractor()
        stats_rows = stats_ext.extract(engine)
        self.assertGreater(len(stats_rows), 5)

        inbound_ext = InboundExtractor()
        inbound_rows = inbound_ext.extract(engine)
        self.assertGreater(len(inbound_rows), 3)

    def test_config_extractor(self):
        ext = ConfigExtractor()
        overview = {"source_dll": {"exists": True, "size_bytes": 102400}, "games": [], "active_variables": {}}
        rows = ext.extract(overview)
        keys = [r[0] for r in rows]
        self.assertIn("dll.status", keys)
        self.assertIn("config.TargetIP", keys)
        self.assertIn("config.EnableLogging", keys)
        self.assertIn("config.PlayerTelemetryRate", keys)
        self.assertIn("config.OpponentTelemetryRate", keys)

    def test_rate_helpers(self):
        mode, hz = parse_rate_to_mode_and_hz("unlimited")
        self.assertEqual(mode, "unlimited")

        mode, hz = parse_rate_to_mode_and_hz("off")
        self.assertEqual(mode, "off")

        mode, hz = parse_rate_to_mode_and_hz("60Hz")
        self.assertEqual(mode, "limited")
        self.assertEqual(hz, "60")

        self.assertEqual(format_mode_and_hz_to_rate("unlimited", ""), "unlimited")
        self.assertEqual(format_mode_and_hz_to_rate("off", ""), "off")
        self.assertEqual(format_mode_and_hz_to_rate("limited", "120"), "120Hz")

    def test_facade_backward_compatibility(self):
        """Ensures that importing from isimotor_rawudp_manager.sniffer gives identical API."""
        from isimotor_rawudp_manager import sniffer

        self.assertTrue(hasattr(sniffer, "IsiMotorBenchmarkApp"))
        self.assertTrue(hasattr(sniffer, "TelemetryEngine"))
        self.assertTrue(hasattr(sniffer, "PacketStats"))
        self.assertTrue(hasattr(sniffer, "extract_telemetry_rows"))
        self.assertTrue(hasattr(sniffer, "extract_config_rows"))
        self.assertTrue(hasattr(sniffer, "main"))
        self.assertEqual(sniffer.PKT_RAW_TELEMETRY, PKT_RAW_TELEMETRY)


if __name__ == "__main__":
    unittest.main()
