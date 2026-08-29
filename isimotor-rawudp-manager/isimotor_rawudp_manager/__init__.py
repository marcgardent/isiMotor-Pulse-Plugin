"""
isiMotor-RawUDP-Manager — Telemetry Diagnostics, Stream Inspector & Plugin Installer.
"""

from .installer import (
    DEFAULT_PLUGIN_VARIABLES,
    SUPPORTED_GAMES,
    configure_game_json,
    copy_and_install_dll,
    detect_game_installations,
    find_source_dll,
    get_configuration_overview,
    install_plugin,
    read_plugin_json_variables,
    show_status,
    uninstall_plugin,
)
from .sniffer import IsiMotorBenchmarkApp, extract_config_rows, main

__all__ = [
    "DEFAULT_PLUGIN_VARIABLES",
    "SUPPORTED_GAMES",
    "IsiMotorBenchmarkApp",
    "configure_game_json",
    "copy_and_install_dll",
    "detect_game_installations",
    "extract_config_rows",
    "find_source_dll",
    "get_configuration_overview",
    "install_plugin",
    "main",
    "read_plugin_json_variables",
    "show_status",
    "uninstall_plugin",
]
