"""
Test Suite: Installer and CustomPluginVariables.JSON configuration
Validates default values injection, game JSON structure, and settings preservation.
"""

import json
import tempfile
import shutil
import unittest
from pathlib import Path
from scripts.install_plugin import (
    configure_game_json,
    DEFAULT_PLUGIN_VARIABLES,
)


class TestInstallerAndConfig(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="isimotor_install_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_plugin_variables_completeness(self):
        """Validates that DEFAULT_PLUGIN_VARIABLES contains all required stream and network keys."""
        required_keys = [
            " Enabled",
            "TargetIP",
            "TargetPort",
            "InboundControl",
            "InboundPort",
            "TelemetryRate",
            "CompactScoringRate",
            "FullScoringRate",
            "TrackRulesRate",
            "PitMenuRate",
            "WeatherRate",
            "ExtendedStateRate",
            "ForceFeedbackRate",
            "GraphicsRate",
            "SystemEvents",
            "UnsubscribedBuffersMask",
        ]
        for key in required_keys:
            self.assertIn(key, DEFAULT_PLUGIN_VARIABLES, f"Missing key in default variables: {key}")

    def test_configure_game_json_creates_files(self):
        """Tests that configure_game_json creates CustomPluginVariables.JSON with full defaults."""
        game_dir = self.test_dir / "Game"
        game_dir.mkdir(parents=True)

        success = configure_game_json(game_dir, "isiMotor_RawUDP.dll")
        self.assertTrue(success)

        json_path = game_dir / "UserData" / "player" / "CustomPluginVariables.JSON"
        self.assertTrue(json_path.exists(), "CustomPluginVariables.JSON was not created")

        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("isiMotor_RawUDP", data)
        self.assertIn("isiMotor-RawUDP", data)
        self.assertIn("isiMotor_RawUDP.dll", data)

        entry = data["isiMotor_RawUDP"]
        self.assertEqual(entry[" Enabled"], 1)
        self.assertEqual(entry["TargetIP"], "127.0.0.1")
        self.assertEqual(entry["TargetPort"], "5000")
        self.assertEqual(entry["InboundControl"], "Enabled")
        self.assertEqual(entry["TelemetryRate"], "unlimited")
        self.assertEqual(entry["FullScoringRate"], "5Hz")
        self.assertEqual(entry["TrackRulesRate"], "3Hz")
        self.assertEqual(entry["PitMenuRate"], "100Hz")
        self.assertEqual(entry["WeatherRate"], "1Hz")
        self.assertEqual(entry["ForceFeedbackRate"], "unlimited")

    def test_configure_game_json_preserves_customizations(self):
        """Tests that existing user customizations are retained when merging defaults."""
        game_dir = self.test_dir / "Game"
        player_dir = game_dir / "UserData" / "player"
        player_dir.mkdir(parents=True)

        existing_data = {
            "isiMotor_RawUDP": {
                " Enabled": 1,
                "TargetIP": "239.255.0.1",  # User customized to Multicast
                "TargetPort": "9000",       # User customized to Port 9000
                "TelemetryRate": "60Hz",    # User customized to 60Hz
            }
        }
        json_path = player_dir / "CustomPluginVariables.JSON"
        json_path.write_text(json.dumps(existing_data), encoding="utf-8")

        success = configure_game_json(game_dir, "isiMotor_RawUDP.dll")
        self.assertTrue(success)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        entry = data["isiMotor_RawUDP"]
        # Custom values preserved
        self.assertEqual(entry["TargetIP"], "239.255.0.1")
        self.assertEqual(entry["TargetPort"], "9000")
        self.assertEqual(entry["TelemetryRate"], "60Hz")
        # Missing defaults populated
        self.assertEqual(entry["InboundControl"], "Enabled")
        self.assertEqual(entry["FullScoringRate"], "5Hz")
        self.assertEqual(entry["PitMenuRate"], "100Hz")


if __name__ == "__main__":
    unittest.main()
