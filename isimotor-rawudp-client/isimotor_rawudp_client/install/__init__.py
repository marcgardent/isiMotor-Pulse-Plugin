"""
Public installation API for isiMotor_RawUDP: Steam game detection, DLL
installation/removal, and CustomPluginVariables.JSON / Settings.JSON
configuration for Le Mans Ultimate and rFactor 2.
"""

from .config import (
    DEFAULT_PLUGIN_VARIABLES,
    configure_game_json,
    get_configuration_overview,
    read_plugin_json_variables,
    save_configuration_to_all_games,
    write_plugin_json_variables,
)
from .dll import (
    copy_and_install_dll,
    find_source_dll,
    get_project_root,
    install_plugin,
    uninstall_plugin,
)
from .steam import (
    SUPPORTED_GAMES,
    detect_game_installations,
    get_steam_vdf_candidate_paths,
    parse_vdf_library_paths,
)

__all__ = [
    "DEFAULT_PLUGIN_VARIABLES",
    "SUPPORTED_GAMES",
    "configure_game_json",
    "copy_and_install_dll",
    "detect_game_installations",
    "find_source_dll",
    "get_configuration_overview",
    "get_project_root",
    "get_steam_vdf_candidate_paths",
    "install_plugin",
    "parse_vdf_library_paths",
    "read_plugin_json_variables",
    "save_configuration_to_all_games",
    "uninstall_plugin",
    "write_plugin_json_variables",
]
