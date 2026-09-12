"""
Test Suite: Installer and CustomPluginVariables.JSON configuration
Validates default values injection, game JSON structure, and settings preservation.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from isimotor_rawudp_client.install import (
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
            "TcpHost",
            "TcpBasePort",
            "InboundControl",
            "InboundTcpPort",
            "PlayerTelemetryRate",
            "OpponentTelemetryRate",
            "CompactScoringRate",
            "FullScoringRate",
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
        self.assertIn("isiMotor_RawUDP.dll", data)
        self.assertNotIn("isiMotor_RawUDP", data)
        self.assertNotIn("isiMotor-RawUDP", data)

        entry = data["isiMotor_RawUDP.dll"]
        self.assertEqual(entry[" Enabled"], 1)
        self.assertEqual(entry["TcpHost"], "127.0.0.1")
        self.assertEqual(entry["TcpBasePort"], "5000")
        self.assertEqual(entry["InboundControl"], "Enabled")
        self.assertEqual(entry["PlayerTelemetryRate"], "unlimited")
        self.assertEqual(entry["OpponentTelemetryRate"], "off")
        self.assertEqual(entry["FullScoringRate"], "5Hz")
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
                "TcpHost": "192.168.1.20",  # User customized host
                "TcpBasePort": "9000",  # User customized to Port 9000
                "TelemetryRate": "60Hz",  # User customized to 60Hz
            }
        }
        json_path = player_dir / "CustomPluginVariables.JSON"
        json_path.write_text(json.dumps(existing_data), encoding="utf-8")

        success = configure_game_json(game_dir, "isiMotor_RawUDP.dll")
        self.assertTrue(success)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("isiMotor_RawUDP.dll", data)
        self.assertNotIn("isiMotor_RawUDP", data)
        entry = data["isiMotor_RawUDP.dll"]
        # Custom values preserved
        self.assertEqual(entry["TcpHost"], "192.168.1.20")
        self.assertEqual(entry["TcpBasePort"], "9000")
        self.assertEqual(entry["TelemetryRate"], "60Hz")
        # Missing defaults populated
        self.assertEqual(entry["InboundControl"], "Enabled")
        self.assertEqual(entry["FullScoringRate"], "5Hz")
        self.assertEqual(entry["WeatherRate"], "1Hz")

    def test_get_configuration_overview_and_extract_rows(self):
        from isimotor_rawudp_client.install import (
            copy_and_install_dll,
            get_configuration_overview,
            read_plugin_json_variables,
        )
        from isimotor_rawudp_manager.sniffer import extract_config_rows

        # 1. Test read_plugin_json_variables on non-existent file returns defaults
        non_existent = self.test_dir / "does_not_exist.json"
        defaults = read_plugin_json_variables(non_existent)
        self.assertEqual(defaults["TcpHost"], "127.0.0.1")
        self.assertEqual(defaults["TcpBasePort"], "5000")

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
        self.assertEqual(g["variables"]["TcpHost"], "127.0.0.1")

        # 5. Test extract_config_rows
        rows = extract_config_rows(overview)
        self.assertGreaterEqual(len(rows), 15)
        row_keys = [r[0] for r in rows]
        self.assertIn("dll.status", row_keys)
        self.assertIn("config.TcpHost", row_keys)
        self.assertIn("config.TcpBasePort", row_keys)
        self.assertIn("config.EnableLogging", row_keys)
        self.assertIn("config.PlayerTelemetryRate", row_keys)
        self.assertIn("config.OpponentTelemetryRate", row_keys)
        self.assertIn("hotreload.architecture", row_keys)

    def test_home_summary_renderers_and_app_navigation(self):
        from isimotor_rawudp_client.install import get_configuration_overview
        from isimotor_rawudp_manager.sniffer import (
            NAV_HOME,
            TAB_TELEM,
            IsiMotorBenchmarkApp,
            TelemetryEngine,
            render_home_config_summary,
            render_home_install_summary,
            render_home_network_summary,
        )

        overview = get_configuration_overview()
        engine = TelemetryEngine()
        # TelemInfo (Type 1) is a FlatBuffer now (no header/chunking): feed a
        # real one (from the golden dataset) rather than a dummy zero buffer.
        golden_path = os.path.join(os.path.dirname(__file__), "golden", "telemetry_golden.bin")
        with open(golden_path, "rb") as f:
            telem_bytes = f.read()
        engine._process_packet(1, telem_bytes)
        self.assertIsNotNone(engine.latest_telemetry)

        install_text = render_home_install_summary(overview)
        config_text = render_home_config_summary(overview)
        network_text = render_home_network_summary(engine, 10.0)

        self.assertIn("DLL Binary", install_text)
        self.assertIn("ZeroMQ PUB Endpoint", config_text)
        self.assertIn("Telemetry ZeroMQ Base", network_text)

        app = IsiMotorBenchmarkApp(host="127.0.0.1", port=5000)
        self.assertEqual(app.active_nav, NAV_HOME)
        self.assertEqual(app.active_tab, TAB_TELEM)
        self.assertIsNotNone(app.table_explorer)
        self.assertIsNotNone(app.table_install)
        self.assertIsNotNone(app.table_commands)

    def test_app_async_pilot_navigation(self):
        import asyncio

        from isimotor_rawudp_manager.sniffer import (
            NAV_COMMANDS,
            NAV_EXPLORER,
            NAV_HOME,
            NAV_INSTALL,
            TAB_WEATHER,
            IsiMotorBenchmarkApp,
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

                # Test Config Form interactions
                app.action_select_nav_install()
                await pilot.pause()
                self.assertEqual(app.active_nav, NAV_INSTALL)

                # Edit form inputs & dropdowns
                app.cfg_target_ip.value = "192.168.1.50"
                app.cfg_target_port.value = "5055"
                app.sel_rate_telem.value = "limited"
                app.input_rate_telem.value = "100"
                app.sel_rate_opponent_telem.value = "limited"
                app.input_rate_opponent_telem.value = "25"
                app.sel_rate_weather.value = "off"
                app.sel_plugin_enabled.value = "1"
                app.sel_inbound_ctrl.value = "Enabled"
                app.sel_enable_logging.value = "Enabled"
                await pilot.pause()

                self.assertTrue(app.input_rate_telem.display)
                self.assertTrue(app.input_rate_opponent_telem.display)
                self.assertFalse(app.input_rate_weather.display)

                form_vars = app._read_config_from_form()
                self.assertEqual(form_vars["TcpHost"], "192.168.1.50")
                self.assertEqual(form_vars["TcpBasePort"], "5055")
                self.assertEqual(form_vars["PlayerTelemetryRate"], "100Hz")
                self.assertEqual(form_vars["OpponentTelemetryRate"], "25Hz")
                self.assertEqual(form_vars["WeatherRate"], "off")
                self.assertEqual(form_vars[" Enabled"], 1)
                self.assertEqual(form_vars["InboundControl"], "Enabled")
                self.assertEqual(form_vars["EnableLogging"], "Enabled")

                # Test Reset defaults
                app.action_reset_config_defaults()
                await pilot.pause()
                self.assertEqual(app.cfg_target_ip.value, "127.0.0.1")
                self.assertEqual(app.cfg_target_port.value, "5000")
                self.assertEqual(app.sel_rate_telem.value, "unlimited")
                self.assertEqual(app.sel_rate_opponent_telem.value, "off")
                self.assertEqual(app.sel_enable_logging.value, "Disabled")
                self.assertFalse(app.input_rate_telem.display)
                self.assertFalse(app.input_rate_opponent_telem.display)
                self.assertTrue(app.input_rate_full_scoring.display)  # Full scoring default is 5Hz (limited)

                # Test Button clicks
                await pilot.click("#btn-cfg-reset")
                await pilot.pause()
                await pilot.click("#btn-cfg-save")
                await pilot.pause()
                await pilot.click("#btn-install-refresh")
                await pilot.pause()

        asyncio.run(_run())

    def test_write_and_save_plugin_variables(self):
        from isimotor_rawudp_client.install import (
            DEFAULT_PLUGIN_VARIABLES,
            read_plugin_json_variables,
            save_configuration_to_all_games,
            write_plugin_json_variables,
        )

        test_dir = Path(tempfile.mkdtemp(prefix="isimotor_form_test_"))
        try:
            custom_vars = dict(DEFAULT_PLUGIN_VARIABLES)
            custom_vars["TcpHost"] = "10.0.0.99"
            custom_vars["TcpBasePort"] = "5555"
            custom_vars["TelemetryRate"] = "60Hz"

            ok, _msg = write_plugin_json_variables(test_dir, custom_vars)
            self.assertTrue(ok)

            saved_json = test_dir / "UserData" / "player" / "CustomPluginVariables.JSON"
            self.assertTrue(saved_json.exists())
            read_back = read_plugin_json_variables(saved_json)
            self.assertEqual(read_back["TcpHost"], "10.0.0.99")
            self.assertEqual(read_back["TcpBasePort"], "5555")
            self.assertEqual(read_back["TelemetryRate"], "60Hz")

            # Test save_configuration_to_all_games with custom_target
            custom_vars["WeatherRate"] = "2Hz"
            ok2, _msg2, saved_paths = save_configuration_to_all_games(custom_vars, custom_target=test_dir)
            self.assertTrue(ok2)
            self.assertEqual(len(saved_paths), 1)

            read_back2 = read_plugin_json_variables(saved_json)
            self.assertEqual(read_back2["WeatherRate"], "2Hz")
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_parse_vdf_library_paths(self):
        """Tests parsing modern and legacy Steam libraryfolders.vdf structures."""
        from isimotor_rawudp_client.install import parse_vdf_library_paths

        steam_root = self.test_dir / "SteamRoot"
        secondary_lib = self.test_dir / "SecondaryLib"
        legacy_lib = self.test_dir / "LegacyLib"
        steam_root.mkdir(parents=True)
        secondary_lib.mkdir(parents=True)
        legacy_lib.mkdir(parents=True)

        vdf_file = steam_root / "steamapps" / "libraryfolders.vdf"
        vdf_file.parent.mkdir(parents=True)

        vdf_content = f'''"libraryfolders"
{{
    "0"
    {{
        "path"    "{steam_root}"
        "label"   ""
        "apps"
        {{
            "2399420"    "10000"
        }}
    }}
    "1"
    {{
        "path"    "{secondary_lib}"
        "apps"
        {{
            "365960"    "20000"
        }}
    }}
    "2"    "{legacy_lib}"
}}'''
        vdf_file.write_text(vdf_content, encoding="utf-8")

        parsed = parse_vdf_library_paths(vdf_file)
        parsed_resolved = [p.resolve() for p in parsed]
        self.assertIn(steam_root.resolve(), parsed_resolved)
        self.assertIn(secondary_lib.resolve(), parsed_resolved)
        self.assertIn(legacy_lib.resolve(), parsed_resolved)

    def test_detect_game_installations_uses_vdf_as_single_source_of_truth(self):
        """Tests that game detection strictly queries libraries registered in libraryfolders.vdf."""
        from unittest.mock import patch

        from isimotor_rawudp_client.install import detect_game_installations

        steam_root = self.test_dir / "Steam"
        steam_root.mkdir(parents=True)
        vdf_file = steam_root / "steamapps" / "libraryfolders.vdf"
        vdf_file.parent.mkdir(parents=True)

        # 1. Registered Steam library containing LMU
        lmu_dir = steam_root / "steamapps" / "common" / "Le Mans Ultimate"
        lmu_dir.mkdir(parents=True)
        (lmu_dir / "Le Mans Ultimate.exe").write_bytes(b"MZ_MOCK_EXE")

        # 2. Unregistered random folder containing rFactor 2
        fake_random_dir = self.test_dir / "RandomFolder" / "steamapps" / "common" / "rFactor 2"
        fake_random_dir.mkdir(parents=True)
        (fake_random_dir / "rFactor2.exe").write_bytes(b"MZ_MOCK_EXE")

        vdf_content = f'''"libraryfolders"
{{
    "0"
    {{
        "path"    "{steam_root}"
    }}
}}'''
        vdf_file.write_text(vdf_content, encoding="utf-8")

        with patch("isimotor_rawudp_client.install.steam.get_steam_vdf_candidate_paths", return_value=[vdf_file]):
            detected = detect_game_installations()

            # LMU was in registered Steam library -> detected
            self.assertEqual(len(detected["LMU"]), 1)
            self.assertEqual(detected["LMU"][0].resolve(), lmu_dir.resolve())

            # rFactor 2 was in unregistered random directory -> NOT detected (no guesswork!)
            self.assertEqual(len(detected["rF2"]), 0)


if __name__ == "__main__":
    unittest.main()
