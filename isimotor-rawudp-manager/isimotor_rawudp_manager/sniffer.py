"""
isiMotor UDP Telemetry Packet Explorer & Benchmark (Facade Module).
Maintains 100% backward compatibility for all imports and CLI entry points.
"""

import sys
from pathlib import Path

# Support loading parent package and scripts
manager_pkg_dir = Path(__file__).resolve().parent
manager_root = manager_pkg_dir.parent
project_root = manager_root.parent
client_pkg_path = project_root / "isimotor-rawudp-client"
if client_pkg_path.exists():
    sys.path.insert(0, str(client_pkg_path))
if str(manager_pkg_dir) not in sys.path:
    sys.path.insert(0, str(manager_pkg_dir))
if str(manager_root) not in sys.path:
    sys.path.insert(0, str(manager_root))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from .constants import (
    INBOUND_ENABLE_OPTIONS,
    NAV_COMMANDS,
    NAV_EXPLORER,
    NAV_HOME,
    NAV_INSTALL,
    PKT_COMPACT_SCORING,
    PKT_EXTENDED_STATE,
    PKT_FORCE_FEEDBACK,
    PKT_FOREIGN,
    PKT_FULL_SCORING,
    PKT_GRAPHICS,
    PKT_HW_CONTROL,
    PKT_RAW_TELEMETRY,
    PKT_SYSTEM_EVENT,
    PKT_WEATHER,
    PKT_WEATHER_CONTROL,
    PLUGIN_ENABLE_OPTIONS,
    RATE_SELECT_OPTIONS,
    TAB_COMPACT_SCORING,
    TAB_CONFIG,
    TAB_EVENT,
    TAB_FFB,
    TAB_GRAPHICS,
    TAB_INBOUND,
    TAB_PHYSICS,
    TAB_SCORING,
    TAB_STATS,
    TAB_TELEM,
    TAB_WEATHER,
    VIEW_COMMANDS,
    VIEW_EXPLORER,
    VIEW_HOME,
    VIEW_INSTALL,
)
from .engine import (
    PacketStats,
    TelemetryEngine,
)
from .extractors import (
    BaseExtractor,
    ConfigExtractor,
    EventExtractor,
    FeedbackExtractor,
    GraphicsExtractor,
    InboundExtractor,
    PhysicsExtractor,
    ScoringExtractor,
    StatsExtractor,
    TableRow,
    TelemetryExtractor,
    WeatherExtractor,
    extract_config_rows,
    extract_event_rows,
    extract_ffb_rows,
    extract_graphics_rows,
    extract_inbound_rows,
    extract_physics_rows,
    extract_scoring_rows,
    extract_stats_rows,
    extract_telemetry_rows,
    extract_weather_rows,
    format_value,
    model_to_clean_dict,
)
from .installer import (
    DEFAULT_PLUGIN_VARIABLES,
    copy_and_install_dll,
    get_configuration_overview,
    save_configuration_to_all_games,
)
from .ui import (
    APP_CSS,
    IsiMotorBenchmarkApp,
    format_mode_and_hz_to_rate,
    main,
    parse_rate_to_mode_and_hz,
    render_home_config_summary,
    render_home_install_summary,
    render_home_network_summary,
)

__all__ = [
    # UI
    "APP_CSS",
    # Installer
    "DEFAULT_PLUGIN_VARIABLES",
    "INBOUND_ENABLE_OPTIONS",
    "NAV_COMMANDS",
    "NAV_EXPLORER",
    "NAV_HOME",
    "NAV_INSTALL",
    "PKT_COMPACT_SCORING",
    "PKT_EXTENDED_STATE",
    "PKT_FORCE_FEEDBACK",
    "PKT_FOREIGN",
    "PKT_FULL_SCORING",
    "PKT_GRAPHICS",
    "PKT_HW_CONTROL",
    # Constants
    "PKT_RAW_TELEMETRY",
    "PKT_SYSTEM_EVENT",
    "PKT_WEATHER",
    "PKT_WEATHER_CONTROL",
    "PLUGIN_ENABLE_OPTIONS",
    "RATE_SELECT_OPTIONS",
    "TAB_COMPACT_SCORING",
    "TAB_CONFIG",
    "TAB_EVENT",
    "TAB_FFB",
    "TAB_GRAPHICS",
    "TAB_INBOUND",
    "TAB_PHYSICS",
    "TAB_SCORING",
    "TAB_STATS",
    "TAB_TELEM",
    "TAB_WEATHER",
    "VIEW_COMMANDS",
    "VIEW_EXPLORER",
    "VIEW_HOME",
    "VIEW_INSTALL",
    # Extractors
    "BaseExtractor",
    "ConfigExtractor",
    "EventExtractor",
    "FeedbackExtractor",
    "GraphicsExtractor",
    "InboundExtractor",
    "IsiMotorBenchmarkApp",
    # Engine
    "PacketStats",
    "PhysicsExtractor",
    "ScoringExtractor",
    "StatsExtractor",
    "TableRow",
    "TelemetryEngine",
    "TelemetryExtractor",
    "WeatherExtractor",
    "copy_and_install_dll",
    "extract_config_rows",
    "extract_event_rows",
    "extract_ffb_rows",
    "extract_graphics_rows",
    "extract_inbound_rows",
    "extract_physics_rows",
    "extract_scoring_rows",
    "extract_stats_rows",
    "extract_telemetry_rows",
    "extract_weather_rows",
    "format_mode_and_hz_to_rate",
    "format_value",
    "get_configuration_overview",
    "main",
    "model_to_clean_dict",
    "parse_rate_to_mode_and_hz",
    "render_home_config_summary",
    "render_home_install_summary",
    "render_home_network_summary",
    "save_configuration_to_all_games",
]

if __name__ == "__main__":
    main()
