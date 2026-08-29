"""
Test Suite: Installer and CustomPluginVariables.JSON configuration
Validates default values injection, game JSON structure, and settings preservation.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from isimotor_rawudp_manager.installer import (
    DEFAULT_PLUGIN_VARIABLES,
    configure_game_json,
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
                "TargetPort": "9000",  # User customized to Port 9000
                "TelemetryRate": "60Hz",  # User customized to 60Hz
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

    def test_get_configuration_overview_and_extract_rows(self):
        from isimotor_rawudp_manager.installer import (
            copy_and_install_dll,
            get_configuration_overview,
            read_plugin_json_variables,
        )
        from isimotor_rawudp_manager.sniffer import extract_config_rows

        # 1. Test read_plugin_json_variables on non-existent file returns defaults
        non_existent = self.test_dir / "does_not_exist.json"
        defaults = read_plugin_json_variables(non_existent)
        self.assertEqual(defaults["TargetIP"], "127.0.0.1")
        self.assertEqual(defaults["TargetPort"], "5000")

        # 2. Setup mock game directory and fake source DLL
        game_dir = self.test_dir / "MockGame"
        game_dir.mkdir(parents=True)
        fake_dll = self.test_dir / "isiMotor_RawUDP.dll"
        fake_dll.write_bytes(b"MZ_MOCK_DLL_BINARY")

        # 3. Test copy_and_install_dll with custom dll and target
        success, msg, installed_paths = copy_and_install_dll(
            custom_dll=fake_dll,
            target_dir=game_dir,
        )
        self.assertTrue(success, f"copy_and_install_dll failed: {msg}")
        self.assertGreaterEqual(len(installed_paths), 1)

        # Check files were copied
        dest_plugin_dll = game_dir / "Plugins" / "isiMotor_RawUDP.dll"
        self.assertTrue(dest_plugin_dll.exists())
        self.assertEqual(dest_plugin_dll.read_bytes(), b"MZ_MOCK_DLL_BINARY")

        # 4. Test get_configuration_overview
        overview = get_configuration_overview(custom_dll=fake_dll, custom_target=game_dir)
        self.assertTrue(overview["source_dll"]["exists"])
        self.assertEqual(overview["source_dll"]["size_bytes"], len(b"MZ_MOCK_DLL_BINARY"))
        self.assertEqual(len(overview["games"]), 1)
        g = overview["games"][0]
        self.assertTrue(g["dll_installed"])
        self.assertTrue(g["json_exists"])
        self.assertEqual(g["variables"]["TargetIP"], "127.0.0.1")

        # 5. Test extract_config_rows
        rows = extract_config_rows(overview)
        self.assertGreaterEqual(len(rows), 15)
        row_keys = [r[0] for r in rows]
        self.assertIn("dll.status", row_keys)
        self.assertIn("config.TargetIP", row_keys)
        self.assertIn("config.TargetPort", row_keys)
        self.assertIn("config.TelemetryRate", row_keys)
        self.assertIn("hotreload.architecture", row_keys)

    def test_home_summary_renderers_and_app_navigation(self):
        from isimotor_rawudp_manager.installer import get_configuration_overview
        from isimotor_rawudp_manager.sniffer import (
            IsiMotorBenchmarkApp,
            NAV_COMMANDS,
            NAV_EXPLORER,
            NAV_HOME,
            NAV_INSTALL,
            TAB_TELEM,
            TelemetryEngine,
            VIEW_COMMANDS,
            VIEW_EXPLORER,
            VIEW_HOME,
            VIEW_INSTALL,
            render_home_config_summary,
            render_home_install_summary,
            render_home_network_summary,
        )

        overview = get_configuration_overview()
        engine = TelemetryEngine()

        install_text = render_home_install_summary(overview)
        config_text = render_home_config_summary(overview)
        network_text = render_home_network_summary(engine, 10.0)

        self.assertIn("DLL Binary", install_text)
        self.assertIn("UDP Destination", config_text)
        self.assertIn("Telemetry UDP Socket", network_text)

        app = IsiMotorBenchmarkApp(host="127.0.0.1", port=5000)
        self.assertEqual(app.active_nav, NAV_HOME)
        self.assertEqual(app.active_tab, TAB_TELEM)
        self.assertIsNotNone(app.table_explorer)
        self.assertIsNotNone(app.table_install)
        self.assertIsNotNone(app.table_commands)

    def test_app_async_pilot_navigation(self):
        import asyncio
        from isimotor_rawudp_manager.sniffer import (
            IsiMotorBenchmarkApp,
            NAV_COMMANDS,
            NAV_EXPLORER,
            NAV_HOME,
            NAV_INSTALL,
            TAB_WEATHER,
        )

        async def _run():
            app = IsiMotorBenchmarkApp(host="127.0.0.1", port=5098)
            async with app.run_test() as pilot:
                self.assertEqual(app.active_nav, NAV_HOME)

                app.action_select_nav_install()
                await pilot.pause()
                self.assertEqual(app.active_nav, NAV_INSTALL)

                app.action_select_nav_explorer()
                await pilot.pause()
                self.assertEqual(app.active_nav, NAV_EXPLORER)

                app.action_select_tab_weather()
                await pilot.pause()
                self.assertEqual(app.active_tab, TAB_WEATHER)

                app.action_select_nav_commands()
                await pilot.pause()
                self.assertEqual(app.active_nav, NAV_COMMANDS)

                app.action_select_nav_home()
                await pilot.pause()
                self.assertEqual(app.active_nav, NAV_HOME)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()


