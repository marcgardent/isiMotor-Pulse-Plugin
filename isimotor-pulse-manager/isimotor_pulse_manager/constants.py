"""
Constants and definitions for the isiMotor Pulse Manager.
"""

from typing import Final

# ── Packet Stream Definitions ──────────────────────────────────────────────────
PKT_RAW_TELEMETRY: Final[str] = "TelemInfoV01 (Raw Binary)"
PKT_COMPACT_SCORING: Final[str] = "CompactScoring (SIMP v2)"
PKT_FULL_SCORING: Final[str] = "FullScoring (SIMP v4 Sliced)"
PKT_WEATHER: Final[str] = "Weather (SIMP v7)"
PKT_EXTENDED_STATE: Final[str] = "ExtendedState (SIMP v8)"
PKT_FORCE_FEEDBACK: Final[str] = "ForceFeedback (SIMP v9 @ 400Hz)"
PKT_GRAPHICS: Final[str] = "Graphics (SIMP v10 @ 60Hz)"
PKT_SYSTEM_EVENT: Final[str] = "SystemEvent (SIMP v3)"
PKT_HW_CONTROL: Final[str] = "HWControl (SIMP v100)"
PKT_WEATHER_CONTROL: Final[str] = "WeatherControl (SIMP v101)"
PKT_FOREIGN: Final[str] = "Foreign / Unknown"

# ── Main Navigation Modes ──────────────────────────────────────────────────────
NAV_HOME: Final[str] = "nav-home"
NAV_INSTALL: Final[str] = "nav-install"
NAV_EXPLORER: Final[str] = "nav-explorer"
NAV_COMMANDS: Final[str] = "nav-commands"

VIEW_HOME: Final[str] = "view-home"
VIEW_INSTALL: Final[str] = "view-install"
VIEW_EXPLORER: Final[str] = "view-explorer"
VIEW_COMMANDS: Final[str] = "view-commands"

# ── Stream Explorer Tabs ───────────────────────────────────────────────────────
TAB_TELEM: Final[str] = "tab-telem"
TAB_SCORING: Final[str] = "tab-scoring"
TAB_COMPACT_SCORING: Final[str] = "tab-compact-scoring"
TAB_WEATHER: Final[str] = "tab-weather"
TAB_FFB: Final[str] = "tab-ffb"
TAB_GRAPHICS: Final[str] = "tab-graphics"
TAB_PHYSICS: Final[str] = "tab-physics"
TAB_EVENT: Final[str] = "tab-event"
TAB_INBOUND: Final[str] = "tab-inbound"
TAB_CONFIG: Final[str] = "tab-config"
TAB_STATS: Final[str] = "tab-stats"

# ── UI Form Choices ────────────────────────────────────────────────────────────
RATE_SELECT_OPTIONS: list[tuple[str, str]] = [
    ("Unlimited", "unlimited"),
    ("Limited (Hz)", "limited"),
    ("Off / Disabled", "off"),
]

PLUGIN_ENABLE_OPTIONS: list[tuple[str, str]] = [
    ("1 - Active", "1"),
    ("0 - Disabled", "0"),
]

INBOUND_ENABLE_OPTIONS: list[tuple[str, str]] = [
    ("Enabled", "Enabled"),
    ("Disabled", "Disabled"),
]

LOGGING_ENABLE_OPTIONS: list[tuple[str, str]] = [
    ("Disabled", "Disabled"),
    ("Enabled", "Enabled"),
]
