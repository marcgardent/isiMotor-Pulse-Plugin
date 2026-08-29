#!/usr/bin/env python3
"""
isiMotor-RawUDP-Plugin — Automated Game Detector & Plugin Installer.
CLI wrapper forwarding to the official isimotor_rawudp_manager.installer module.

Copyright 2026 Marc GARDENT
Licensed under the Apache License, Version 2.0.
"""

import sys
from pathlib import Path

# Add manager directory and project root to sys.path
_project_root = Path(__file__).resolve().parent.parent
_manager_dir = _project_root / "isimotor-rawudp-manager"
if str(_manager_dir) not in sys.path:
    sys.path.insert(0, str(_manager_dir))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from isimotor_rawudp_manager.installer import (
        DEFAULT_PLUGIN_VARIABLES,
        SUPPORTED_GAMES,
        configure_game_json,
        copy_and_install_dll,
        detect_game_installations,
        find_source_dll,
        get_configuration_overview,
        get_known_game_paths,
        get_project_root,
        get_steam_vdf_candidate_paths,
        install_plugin,
        main,
        parse_vdf_library_paths,
        read_plugin_json_variables,
        show_status,
        uninstall_plugin,
    )
except ImportError:
    from install_plugin import (
        DEFAULT_PLUGIN_VARIABLES,
        SUPPORTED_GAMES,
        configure_game_json,
        copy_and_install_dll,
        detect_game_installations,
        find_source_dll,
        get_configuration_overview,
        get_known_game_paths,
        get_project_root,
        get_steam_vdf_candidate_paths,
        install_plugin,
        main,
        parse_vdf_library_paths,
        read_plugin_json_variables,
        show_status,
        uninstall_plugin,
    )

__all__ = [
    "DEFAULT_PLUGIN_VARIABLES",
    "SUPPORTED_GAMES",
    "configure_game_json",
    "copy_and_install_dll",
    "detect_game_installations",
    "find_source_dll",
    "get_configuration_overview",
    "get_known_game_paths",
    "get_project_root",
    "get_steam_vdf_candidate_paths",
    "install_plugin",
    "main",
    "parse_vdf_library_paths",
    "read_plugin_json_variables",
    "show_status",
    "uninstall_plugin",
]

if __name__ == "__main__":
    main()
