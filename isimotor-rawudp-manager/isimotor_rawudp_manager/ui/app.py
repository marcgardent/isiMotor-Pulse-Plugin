"""
Main Textual TUI Application for isiMotor RawUDP Manager.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
    Tab,
    Tabs,
)

from ..constants import (
    INBOUND_ENABLE_OPTIONS,
    NAV_COMMANDS,
    NAV_EXPLORER,
    NAV_HOME,
    NAV_INSTALL,
    PKT_COMPACT_SCORING,
    PKT_EXTENDED_STATE,
    PKT_FORCE_FEEDBACK,
    PKT_FULL_SCORING,
    PKT_GRAPHICS,
    PKT_RAW_TELEMETRY,
    PKT_SYSTEM_EVENT,
    PKT_WEATHER,
    PLUGIN_ENABLE_OPTIONS,
    RATE_SELECT_OPTIONS,
    TAB_EVENT,
    TAB_FFB,
    TAB_GRAPHICS,
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
from ..engine.telemetry_engine import TelemetryEngine
from ..extractors import (
    TableRow,
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
    model_to_clean_dict,
)
from ..installer import (
    DEFAULT_PLUGIN_VARIABLES,
    copy_and_install_dll,
    get_configuration_overview,
    save_configuration_to_all_games,
)
from .helpers import format_mode_and_hz_to_rate, parse_rate_to_mode_and_hz
from .styles import APP_CSS
from .summary_renderers import (
    render_home_config_summary,
    render_home_install_summary,
    render_home_network_summary,
)
from .views import (
    compose_commands_view,
    compose_explorer_view,
    compose_home_view,
    compose_install_view,
)

manager_pkg_dir = Path(__file__).resolve().parent.parent
manager_root = manager_pkg_dir.parent
project_root = manager_root.parent


class IsiMotorBenchmarkApp(App):
    """Raw UDP Telemetry Explorer & Benchmark for isiMotor."""

    CSS = APP_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("h", "select_nav_home", "Home", show=True),
        Binding("p", "select_nav_install", "Install/Config", show=True),
        Binding("s", "save_config", "Save Config", show=True),
        Binding("e", "select_nav_explorer", "Explorer", show=True),
        Binding("i", "select_nav_commands", "Commands", show=True),
        Binding("c", "copy_json", "Copy JSON", show=True),
        Binding("t", "copy_table", "Copy Table", show=True),
        Binding("r", "reset_stats", "Reset Stats", show=True),
        Binding("k", "copy_dll_action", "Copy DLL", show=False),
        Binding("slash", "focus_search", "Search", show=True),
        Binding("1", "select_tab_telem", "Telem", show=False),
        Binding("2", "select_tab_scoring", "Scoring", show=False),
        Binding("3", "select_tab_weather", "Weather", show=False),
        Binding("4", "select_tab_ffb", "FFB", show=False),
        Binding("5", "select_tab_graphics", "Graphics", show=False),
        Binding("6", "select_tab_physics", "Physics", show=False),
        Binding("7", "select_tab_event", "Event", show=False),
        Binding("8", "select_tab_stats", "Stats", show=False),
        Binding("w", "inbound_rain_toggle", "Rain Toggle", show=False),
    ]

    active_nav = reactive(NAV_HOME)
    active_tab = reactive(TAB_TELEM)
    search_query_explorer = reactive("")
    search_query_install = reactive("")

    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        super().__init__()
        self.host = host
        self.port = port

        self.engine = TelemetryEngine(host=host, port=port)
        self.config_overview: dict[str, Any] = {}
        self.refresh_config_overview()

        # Top Navigation Tabs
        self.main_tabs = Tabs(
            Tab("🏠 Home", id=NAV_HOME),
            Tab("📦 Installer & Config", id=NAV_INSTALL),
            Tab("🔍 Packet Explorer", id=NAV_EXPLORER),
            Tab("🎮 Inbound Controls", id=NAV_COMMANDS),
            active=NAV_HOME,
            id="main-nav-tabs",
        )

        # Global Metric widgets
        self.lbl_elapsed = Static("⏱️ Session: [bold green]00:00s[/]", classes="metric-box")
        self.lbl_packets = Static("📦 Packets: [bold yellow]0[/]", classes="metric-box")
        self.lbl_channel_freq = Static("📶 Stream: [bold yellow]0.0 Hz[/]", classes="metric-box")
        self.lbl_rate = Static("⚡ Total: [bold magenta]0.0 KB/s[/]", classes="metric-box")
        self.lbl_visible_rows = Static("🔍 Fields: [bold cyan]0 / 0[/]", classes="metric-box")

        # Home View widgets
        self.lbl_home_install = Static(render_home_install_summary(self.config_overview), classes="home-card-content")
        self.lbl_home_config = Static(render_home_config_summary(self.config_overview), classes="home-card-content")
        self.lbl_home_network = Static(render_home_network_summary(self.engine, 0.0), classes="home-card-content")

        # Install / Config Form widgets
        self.cfg_target_ip = Input(placeholder="127.0.0.1", id="cfg-target-ip", classes="cfg-input-text")
        self.cfg_target_port = Input(placeholder="5000", id="cfg-target-port", classes="cfg-input-text")
        self.cfg_inbound_port = Input(placeholder="5001", id="cfg-inbound-port", classes="cfg-input-text")
        self.cfg_unsub_mask = Input(placeholder="0", id="cfg-unsub-mask", classes="cfg-input-text")

        self.sel_plugin_enabled = Select(
            PLUGIN_ENABLE_OPTIONS, value="1", allow_blank=False, id="sel-plugin-enabled", classes="cfg-select-box"
        )
        self.sel_inbound_ctrl = Select(
            INBOUND_ENABLE_OPTIONS, value="Enabled", allow_blank=False, id="sel-inbound-ctrl", classes="cfg-select-box"
        )
        self.sel_sys_events = Select(
            INBOUND_ENABLE_OPTIONS, value="Enabled", allow_blank=False, id="sel-sys-events", classes="cfg-select-box"
        )

        self.sel_rate_telem = Select(
            RATE_SELECT_OPTIONS, value="unlimited", allow_blank=False, id="sel-rate-telem", classes="cfg-rate-select"
        )
        self.input_rate_telem = Input(placeholder="100", id="input-rate-telem", classes="cfg-rate-hz-input")

        self.sel_rate_ffb = Select(
            RATE_SELECT_OPTIONS, value="unlimited", allow_blank=False, id="sel-rate-ffb", classes="cfg-rate-select"
        )
        self.input_rate_ffb = Input(placeholder="400", id="input-rate-ffb", classes="cfg-rate-hz-input")

        self.sel_rate_full_scoring = Select(
            RATE_SELECT_OPTIONS, value="limited", allow_blank=False, id="sel-rate-full-scoring", classes="cfg-rate-select"
        )
        self.input_rate_full_scoring = Input(placeholder="5", id="input-rate-full-scoring", classes="cfg-rate-hz-input")

        self.sel_rate_compact_scoring = Select(
            RATE_SELECT_OPTIONS, value="unlimited", allow_blank=False, id="sel-rate-compact-scoring", classes="cfg-rate-select"
        )
        self.input_rate_compact_scoring = Input(placeholder="20", id="input-rate-compact-scoring", classes="cfg-rate-hz-input")

        self.sel_rate_weather = Select(
            RATE_SELECT_OPTIONS, value="limited", allow_blank=False, id="sel-rate-weather", classes="cfg-rate-select"
        )
        self.input_rate_weather = Input(placeholder="1", id="input-rate-weather", classes="cfg-rate-hz-input")

        self.sel_rate_extended = Select(
            RATE_SELECT_OPTIONS, value="limited", allow_blank=False, id="sel-rate-extended", classes="cfg-rate-select"
        )
        self.input_rate_extended = Input(placeholder="5", id="input-rate-extended", classes="cfg-rate-hz-input")

        self.sel_rate_graphics = Select(
            RATE_SELECT_OPTIONS, value="limited", allow_blank=False, id="sel-rate-graphics", classes="cfg-rate-select"
        )
        self.input_rate_graphics = Input(placeholder="60", id="input-rate-graphics", classes="cfg-rate-hz-input")

        self.lbl_cfg_target_info = Static("", id="cfg-target-info")

        self.search_install = Input(placeholder="🔍 Filter configuration parameters...", id="install-search-box")
        self.table_install: DataTable[Any] = DataTable(cursor_type="row")
        self._current_install_keys: list[str] = []

        # Explorer View widgets
        self.packet_tabs = Tabs(
            Tab("🏎️ TelemInfo (1888 B)", id=TAB_TELEM),
            Tab("🏁 Grid Scoring", id=TAB_SCORING),
            Tab("🌦️ Weather", id=TAB_WEATHER),
            Tab("⚡ FFB (400Hz)", id=TAB_FFB),
            Tab("🎥 Graphics", id=TAB_GRAPHICS),
            Tab("🔧 Physics & Aids", id=TAB_PHYSICS),
            Tab("🔔 Events (6 B)", id=TAB_EVENT),
            Tab("📊 Stream Rates", id=TAB_STATS),
            active=TAB_TELEM,
            id="packet-tabs",
        )
        self.search_explorer = Input(
            placeholder="🔍 Filter fields by name or description... (Press '/' to focus)", id="search-box"
        )
        self.table_explorer: DataTable[Any] = DataTable(cursor_type="row")
        self._current_explorer_keys: list[str] = []

        # Commands View widgets
        self.lbl_commands_status = Static(
            f"🎮 Inbound Target: [bold cyan]{self.engine.inbound_target_host}:{self.engine.inbound_target_port}[/] | "
            f"Last Command: [bold #58a6ff]{self.engine.last_inbound_cmd_sent}[/] | Pulse: [bold yellow]50 ms[/]",
            id="commands-status-bar",
        )
        self.input_cmd_name = Input(placeholder="Name (e.g. PitMenuSelect, BrakeBiasForward)", id="input-cmd-name")
        self.input_cmd_val = Input(placeholder="Value (default: 1.0)", id="input-cmd-val")
        self.table_commands: DataTable[Any] = DataTable(cursor_type="row")
        self._current_commands_keys: list[str] = []

        # Content Switcher reference
        self.switcher = ContentSwitcher(initial=VIEW_HOME, id="main-content-switcher")

    def refresh_config_overview(self) -> None:
        """Refreshes the detected game installations and JSON configuration overview."""
        try:
            self.config_overview = get_configuration_overview(project_root=project_root)
        except Exception as e:
            self.config_overview = {"error": str(e), "source_dll": {}, "games": [], "active_variables": {}}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="top-nav-bar"):
            yield self.main_tabs

        with Horizontal(id="metrics-bar"):
            yield Static("🏎️ [bold cyan]isiMotorRawUDP[/]", classes="metric-box")
            yield self.lbl_elapsed
            yield self.lbl_packets
            yield self.lbl_channel_freq
            yield self.lbl_rate
            yield self.lbl_visible_rows
            yield Static(f"🌐 [bold cyan]{self.host}:{self.port}[/]", classes="metric-box")

        with ContentSwitcher(initial=VIEW_HOME, id="main-content-switcher"):
            yield from compose_home_view(self)
            yield from compose_install_view(self)
            yield from compose_explorer_view(self)
            yield from compose_commands_view(self)

        yield Footer()

    def on_mount(self) -> None:
        self.title = "isiMotorRawUDP Manager"
        self.sub_title = "Le Mans Ultimate & rFactor 2 Telemetry Hub"

        # Initialize DataTable columns
        for dt in [self.table_explorer, self.table_install, self.table_commands]:
            dt.add_column("Field / Key", key="col_key", width=34)
            dt.add_column("Current Value", key="col_val", width=32)
            dt.add_column("Description & Units", key="col_desc")

        # Start UDP receiver engine
        self.engine.start()

        # Populate tables, form inputs, and home cards
        self._update_home_cards()
        self._load_config_into_form()
        self._rebuild_explorer_rows()
        self._rebuild_install_rows()
        self._rebuild_commands_rows()

        # High-frequency UI tick (30 FPS)
        self.timer = self.set_interval(0.033, self._update_ui)

    # ── Tab & Navigation Handlers ──────────────────────────────────────────────

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        switcher = self.query_one(ContentSwitcher)
        if event.tabs.id == "main-nav-tabs":
            if event.tab and event.tab.id:
                self.active_nav = event.tab.id
                if self.active_nav == NAV_HOME:
                    switcher.current = VIEW_HOME
                    self.refresh_config_overview()
                    self._update_home_cards()
                elif self.active_nav == NAV_INSTALL:
                    switcher.current = VIEW_INSTALL
                    self.refresh_config_overview()
                    self._load_config_into_form()
                    self._rebuild_install_rows()
                elif self.active_nav == NAV_EXPLORER:
                    switcher.current = VIEW_EXPLORER
                    self._rebuild_explorer_rows()
                elif self.active_nav == NAV_COMMANDS:
                    switcher.current = VIEW_COMMANDS
                    self._rebuild_commands_rows()
        elif event.tabs.id == "packet-tabs":
            if event.tab and event.tab.id:
                self.active_tab = event.tab.id
                self._rebuild_explorer_rows()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-box":
            self.search_query_explorer = event.value.strip().lower()
            self._rebuild_explorer_rows()
        elif event.input.id == "install-search-box":
            self.search_query_install = event.value.strip().lower()
            self._rebuild_install_rows()

    def on_select_changed(self, event: Select.Changed) -> None:
        sel_id = event.select.id
        if sel_id and sel_id.startswith("sel-rate-"):
            inp_id = sel_id.replace("sel-rate-", "input-rate-")
            box_id = sel_id.replace("sel-rate-", "box-rate-")
            is_limited = (event.value == "limited")
            try:
                box_widget = self.query_one(f"#{box_id}")
                box_widget.display = is_limited
            except Exception:
                pass
            try:
                inp_widget = self.query_one(f"#{inp_id}", Input)
                inp_widget.display = is_limited
                if is_limited:
                    inp_widget.focus()
            except Exception:
                pass

    # ── Keyboard Action Handlers ───────────────────────────────────────────────

    def action_select_nav_home(self) -> None:
        self.main_tabs.active = NAV_HOME

    def action_select_nav_install(self) -> None:
        self.main_tabs.active = NAV_INSTALL

    def action_select_nav_explorer(self) -> None:
        self.main_tabs.active = NAV_EXPLORER

    def action_select_nav_commands(self) -> None:
        self.main_tabs.active = NAV_COMMANDS

    def action_focus_search(self) -> None:
        if self.active_nav == NAV_EXPLORER:
            self.search_explorer.focus()
        elif self.active_nav == NAV_INSTALL:
            self.cfg_target_ip.focus()
        elif self.active_nav == NAV_COMMANDS:
            self.input_cmd_name.focus()

    def action_save_config(self) -> None:
        """Saves form values into CustomPluginVariables.JSON files across all detected games."""
        vars_dict = self._read_config_from_form()
        success, msg, saved_paths = save_configuration_to_all_games(vars_dict, project_root=project_root)
        self.refresh_config_overview()
        self._update_home_cards()
        self._load_config_into_form()
        self._rebuild_install_rows()
        if success:
            self.notify(
                f"Configuration saved to {len(saved_paths)} game(s)!",
                title="💾 Configuration Saved",
                severity="information",
            )
        else:
            self.notify(msg, title="❌ Save Error", severity="error")

    def action_reset_config_defaults(self) -> None:
        """Resets the form fields to standard default configuration values."""
        self.config_overview["active_variables"] = dict(DEFAULT_PLUGIN_VARIABLES)
        self._load_config_into_form()
        self.notify("Form reset to standard defaults (click 'Save' to apply).", title="🔄 Reset Form")

    def action_select_tab_telem(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_TELEM

    def action_select_tab_scoring(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_SCORING

    def action_select_tab_weather(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_WEATHER

    def action_select_tab_ffb(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_FFB

    def action_select_tab_graphics(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_GRAPHICS

    def action_select_tab_physics(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_PHYSICS

    def action_select_tab_event(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_EVENT

    def action_select_tab_stats(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_STATS

    def action_copy_dll_action(self) -> None:
        self.action_copy_dll()

    def action_copy_dll(self) -> None:
        """Copies compiled DLL to detected games and configures JSON settings."""
        success, msg, _paths = copy_and_install_dll(project_root=project_root)
        self.refresh_config_overview()
        self._update_home_cards()
        self._load_config_into_form()
        self._rebuild_install_rows()
        if success:
            self.notify(msg, title="📦 DLL Copied Successfully!", severity="information")
        else:
            self.notify(msg, title="❌ DLL Installation Error", severity="error")

    def action_inbound_pit_up(self) -> None:
        self.engine.send_hw_control("PitMenuUp", 1.0, 50)
        self.notify("Sent command: PitMenuUp", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_pit_down(self) -> None:
        self.engine.send_hw_control("PitMenuDown", 1.0, 50)
        self.notify("Sent command: PitMenuDown", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_pit_prev(self) -> None:
        self.engine.send_hw_control("PitMenuPrev", 1.0, 50)
        self.notify("Sent command: PitMenuPrev", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_pit_next(self) -> None:
        self.engine.send_hw_control("PitMenuNext", 1.0, 50)
        self.notify("Sent command: PitMenuNext", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_pit_select(self) -> None:
        self.engine.send_hw_control("PitMenuSelect", 1.0, 50)
        self.notify("Sent command: PitMenuSelect", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_rain_toggle(self) -> None:
        current_rain = self.engine.latest_weather.origin_raining if self.engine.latest_weather else 0.0
        new_rain = 0.0 if current_rain > 0.3 else 0.85
        self.engine.send_weather_override(ambient_temp=25.0, raining=new_rain)
        self.notify(f"Injected Weather: Rain={new_rain * 100:.0f}%", title="Weather Override")
        self._rebuild_commands_rows()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ["btn-home-goto-install", "btn-hub-install", "btn-home-goto-config"]:
            self.main_tabs.active = NAV_INSTALL
        elif bid in ["btn-home-goto-explorer", "btn-hub-explorer"]:
            self.main_tabs.active = NAV_EXPLORER
        elif bid in ["btn-home-goto-commands", "btn-hub-commands"]:
            self.main_tabs.active = NAV_COMMANDS
        elif bid == "btn-cfg-save":
            self.action_save_config()
        elif bid == "btn-cfg-reset":
            self.action_reset_config_defaults()
        elif bid in ["btn-home-copy-dll", "btn-install-copy-dll"]:
            self.action_copy_dll()
        elif bid == "btn-install-refresh":
            self.refresh_config_overview()
            self._update_home_cards()
            self._load_config_into_form()
            self._rebuild_install_rows()
            self.notify("Configuration reloaded from disk.", title="🔄 Reload Complete")
        elif bid in ["btn-explorer-copy-json", "btn-install-copy-json"]:
            self.action_copy_json()
        elif bid in ["btn-explorer-copy-table", "btn-install-copy-table"]:
            self.action_copy_table()
        elif bid == "btn-explorer-reset-stats":
            self.action_reset_stats()
        elif bid == "btn-cmd-pit-up":
            self.action_inbound_pit_up()
        elif bid == "btn-cmd-pit-down":
            self.action_inbound_pit_down()
        elif bid == "btn-cmd-pit-prev":
            self.action_inbound_pit_prev()
        elif bid == "btn-cmd-pit-next":
            self.action_inbound_pit_next()
        elif bid == "btn-cmd-pit-select":
            self.action_inbound_pit_select()
        elif bid == "btn-cmd-weather-sun":
            self.engine.send_weather_override(ambient_temp=25.0, raining=0.0)
            self.notify("Injected Weather: Clear (0% rain)", title="Weather Override")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-weather-drizzle":
            self.engine.send_weather_override(ambient_temp=22.0, raining=0.25)
            self.notify("Injected Weather: Drizzle (25% rain)", title="Weather Override")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-weather-rain":
            self.engine.send_weather_override(ambient_temp=19.0, raining=0.60)
            self.notify("Injected Weather: Rain (60% rain)", title="Weather Override")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-weather-storm":
            self.engine.send_weather_override(ambient_temp=16.0, raining=0.95)
            self.notify("Injected Weather: Storm (95% rain)", title="Weather Override")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-ignition":
            self.engine.send_hw_control("Ignition", 1.0, 50)
            self.notify("Sent command: Ignition", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-wipers":
            self.engine.send_hw_control("Wipers", 1.0, 50)
            self.notify("Sent command: Wipers", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-tc-up":
            self.engine.send_hw_control("TCIncrease", 1.0, 50)
            self.notify("Sent command: TCIncrease", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-tc-down":
            self.engine.send_hw_control("TCDecrease", 1.0, 50)
            self.notify("Sent command: TCDecrease", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-abs-up":
            self.engine.send_hw_control("ABSIncrease", 1.0, 50)
            self.notify("Sent command: ABSIncrease", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-abs-down":
            self.engine.send_hw_control("ABSDecrease", 1.0, 50)
            self.notify("Sent command: ABSDecrease", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-send-custom":
            name = self.input_cmd_name.value.strip()
            val_str = self.input_cmd_val.value.strip()
            if not name:
                self.notify("Please enter a control identifier", title="Error", severity="error")
            else:
                try:
                    val = float(val_str) if val_str else 1.0
                except ValueError:
                    val = 1.0
                self.engine.send_hw_control(name, val, 50)
                self.notify(f"Sent command: {name}={val}", title="HW Control")
                self._rebuild_commands_rows()

    # ── Data Extraction Helpers ────────────────────────────────────────────────

    def _get_active_explorer_rows(self) -> list[TableRow]:
        """Returns the raw rows for the currently selected stream in the Explorer."""
        if self.active_tab == TAB_TELEM:
            return extract_telemetry_rows(self.engine.latest_telemetry, self.engine.stats[PKT_RAW_TELEMETRY])
        elif self.active_tab == TAB_SCORING:
            st = (
                self.engine.stats.get(PKT_FULL_SCORING)
                if self.engine.latest_full_scoring
                else self.engine.stats[PKT_COMPACT_SCORING]
            )
            return extract_scoring_rows(self.engine.latest_scoring, self.engine.latest_full_scoring, st)
        elif self.active_tab == TAB_WEATHER:
            return extract_weather_rows(self.engine.latest_weather, self.engine.stats[PKT_WEATHER])
        elif self.active_tab == TAB_FFB:
            return extract_ffb_rows(self.engine.latest_force_feedback, self.engine.stats[PKT_FORCE_FEEDBACK])
        elif self.active_tab == TAB_GRAPHICS:
            return extract_graphics_rows(self.engine.latest_graphics, self.engine.stats[PKT_GRAPHICS])
        elif self.active_tab == TAB_PHYSICS:
            return extract_physics_rows(self.engine.latest_extended_state, self.engine.stats[PKT_EXTENDED_STATE])
        elif self.active_tab == TAB_EVENT:
            return extract_event_rows(
                self.engine.latest_event, self.engine.stats[PKT_SYSTEM_EVENT], self.engine.latest_event_time
            )
        elif self.active_tab == TAB_STATS:
            return extract_stats_rows(self.engine)
        return []

    def _get_active_model_dict(self) -> dict[str, Any]:
        """Returns clean dictionary for JSON export based on active navigation mode."""
        if self.active_nav == NAV_INSTALL:
            return self.config_overview
        elif self.active_nav == NAV_COMMANDS:
            rows = extract_inbound_rows(self.engine)
            return {k: raw for k, raw, _, _ in rows}
        elif self.active_nav == NAV_HOME:
            return {
                "config_overview": self.config_overview,
                "engine_stats": {k: s.count for k, s in self.engine.stats.items()},
                "total_packets": self.engine.total_packets,
            }

        # Explorer view export
        if self.active_tab == TAB_TELEM:
            st = self.engine.stats[PKT_RAW_TELEMETRY]
            if self.engine.latest_telemetry:
                d = model_to_clean_dict(self.engine.latest_telemetry)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "jitter_ms": round(st.jitter_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                d["_computed"] = {
                    "speed_kmh": self.engine.latest_telemetry.speed_kmh,
                    "forward_speed_kmh": self.engine.latest_telemetry.forward_speed_kmh,
                    "gear_str": self.engine.latest_telemetry.gear_str,
                }
                return d
            return {"status": "No TelemInfo packet received yet"}
        elif self.active_tab == TAB_SCORING:
            if self.engine.latest_full_scoring:
                st = self.engine.stats[PKT_FULL_SCORING]
                d = model_to_clean_dict(self.engine.latest_full_scoring)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            elif self.engine.latest_scoring:
                st = self.engine.stats[PKT_COMPACT_SCORING]
                d = model_to_clean_dict(self.engine.latest_scoring)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No Scoring packet received yet"}
        elif self.active_tab == TAB_WEATHER:
            st = self.engine.stats[PKT_WEATHER]
            if self.engine.latest_weather:
                d = model_to_clean_dict(self.engine.latest_weather)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No Weather packet received yet"}
        elif self.active_tab == TAB_FFB:
            st = self.engine.stats[PKT_FORCE_FEEDBACK]
            if self.engine.latest_force_feedback:
                d = model_to_clean_dict(self.engine.latest_force_feedback)
                d["percentage"] = self.engine.latest_force_feedback.percentage
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "jitter_ms": round(st.jitter_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No ForceFeedback packet received yet"}
        elif self.active_tab == TAB_GRAPHICS:
            st = self.engine.stats[PKT_GRAPHICS]
            if self.engine.latest_graphics:
                d = model_to_clean_dict(self.engine.latest_graphics)
                d["camera_type_str"] = self.engine.latest_graphics.camera_type_str
                d["is_cockpit_view"] = self.engine.latest_graphics.is_cockpit_view
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No Graphics packet received yet"}
        elif self.active_tab == TAB_PHYSICS:
            st = self.engine.stats[PKT_EXTENDED_STATE]
            if self.engine.latest_extended_state:
                d = model_to_clean_dict(self.engine.latest_extended_state)
                d["pit_speed_limit_kmh"] = self.engine.latest_extended_state.current_pit_speed_limit_kmh
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No ExtendedState packet received yet"}
        elif self.active_tab == TAB_EVENT:
            st = self.engine.stats[PKT_SYSTEM_EVENT]
            if self.engine.latest_event:
                d = model_to_clean_dict(self.engine.latest_event)
                d["name"] = self.engine.latest_event.name
                d["timestamp"] = self.engine.latest_event_time
                d["_channel_diagnostics"] = {
                    "packets_count": st.count,
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No SystemEvent packet received yet"}
        elif self.active_tab == TAB_STATS:
            rows = extract_stats_rows(self.engine)
            return {k: raw for k, raw, _, _ in rows}
        return {}

    # ── Clipboard Export Actions ───────────────────────────────────────────────

    def action_copy_json(self) -> None:
        """Copies JSON representation of currently active view/packet to clipboard."""
        data_dict = self._get_active_model_dict()
        json_text = json.dumps(data_dict, indent=2)
        try:
            self.copy_to_clipboard(json_text)
            self.notify(f"JSON copied to clipboard ({len(data_dict)} items)!", title="📋 JSON Copied")
        except Exception as e:
            self.notify(f"Could not copy to clipboard: {e}", title="Error", severity="error")

    def action_copy_table(self) -> None:
        """Copies formatted table (Key, Value, Description) to clipboard."""
        if self.active_nav == NAV_INSTALL:
            rows = extract_config_rows(self.config_overview)
        elif self.active_nav == NAV_COMMANDS:
            rows = extract_inbound_rows(self.engine)
        else:
            rows = self._get_active_explorer_rows()

        lines = ["Key\tValue\tDescription"]
        for key, _raw_val, fmt_val, desc in rows:
            clean_fmt = (
                fmt_val.replace("[bold]", "")
                .replace("[/bold]", "")
                .replace("[bold #58a6ff]", "")
                .replace("[bold #3fb950]", "")
                .replace("[bold #f85149]", "")
                .replace("[bold #e3b341]", "")
                .replace("[bold #f1e05a]", "")
                .replace("[bold #bc8cff]", "")
                .replace("[#a5d6ff]", "")
                .replace("[dim]", "")
                .replace("[/dim]", "")
                .replace("[/]", "")
            )
            lines.append(f"{key}\t{clean_fmt}\t{desc}")

        table_text = "\n".join(lines)
        try:
            self.copy_to_clipboard(table_text)
            self.notify(f"Table copied to clipboard ({len(rows)} rows)!", title="📑 Table Copied")
        except Exception as e:
            self.notify(f"Could not copy to clipboard: {e}", title="Error", severity="error")

    def action_reset_stats(self) -> None:
        self.engine.reset_stats()
        self._rebuild_explorer_rows()
        self.notify("Statistics & packet counters reset.", title="🔄 Reset Complete")

    # ── Table & UI Rendering Helpers ───────────────────────────────────────────

    def _update_home_cards(self) -> None:
        """Updates the 3 dashboard cards on the Home page."""
        elapsed = time.time() - self.engine.start_time
        self.lbl_home_install.update(render_home_install_summary(self.config_overview))
        self.lbl_home_config.update(render_home_config_summary(self.config_overview))
        self.lbl_home_network.update(render_home_network_summary(self.engine, elapsed))

    def _rebuild_explorer_rows(self) -> None:
        """Rebuilds the Explorer DataTable rows."""
        all_rows = self._get_active_explorer_rows()
        query = self.search_query_explorer.lower()

        if query:
            filtered_rows = [
                r for r in all_rows if query in r[0].lower() or query in r[3].lower() or query in str(r[1]).lower()
            ]
        else:
            filtered_rows = all_rows

        self.table_explorer.clear()
        self._current_explorer_keys = []

        for key, _raw_val, fmt_val, desc in filtered_rows:
            self.table_explorer.add_row(f"[bold #58a6ff]{key}[/]", fmt_val, desc, key=key)
            self._current_explorer_keys.append(key)

        self.lbl_visible_rows.update(f"🔍 Fields: [bold cyan]{len(filtered_rows)} / {len(all_rows)}[/]")

    def _load_config_into_form(self) -> None:
        """Loads active variables from config_overview into form widgets."""
        vars_dict = self.config_overview.get("active_variables", dict(DEFAULT_PLUGIN_VARIABLES))

        # Endpoints
        self.cfg_target_ip.value = str(vars_dict.get("TargetIP", "127.0.0.1"))
        self.cfg_target_port.value = str(vars_dict.get("TargetPort", "5000"))
        self.cfg_inbound_port.value = str(vars_dict.get("InboundPort", "5001"))
        self.cfg_unsub_mask.value = str(vars_dict.get("UnsubscribedBuffersMask", "0"))

        # Activations
        enabled_raw = vars_dict.get(" Enabled", vars_dict.get("Enabled", 1))
        enabled_str = str(enabled_raw).strip()
        self.sel_plugin_enabled.value = "1" if enabled_str in ["1", "true", "True", "enabled", "Enabled"] else "0"

        inbound_raw = vars_dict.get("InboundControl", "Enabled")
        inbound_str = str(inbound_raw).strip()
        self.sel_inbound_ctrl.value = "Enabled" if inbound_str.lower() in ["enabled", "1", "true"] else "Disabled"

        events_raw = vars_dict.get("SystemEvents", "Enabled")
        events_str = str(events_raw).strip()
        self.sel_sys_events.value = "Enabled" if events_str.lower() in ["enabled", "1", "true"] else "Disabled"

        # Stream Rates
        rate_configs = [
            (self.sel_rate_telem, self.input_rate_telem, "box-rate-telem", "TelemetryRate", "100"),
            (self.sel_rate_ffb, self.input_rate_ffb, "box-rate-ffb", "ForceFeedbackRate", "400"),
            (self.sel_rate_full_scoring, self.input_rate_full_scoring, "box-rate-full-scoring", "FullScoringRate", "5"),
            (self.sel_rate_compact_scoring, self.input_rate_compact_scoring, "box-rate-compact-scoring", "CompactScoringRate", "20"),
            (self.sel_rate_weather, self.input_rate_weather, "box-rate-weather", "WeatherRate", "1"),
            (self.sel_rate_extended, self.input_rate_extended, "box-rate-extended", "ExtendedStateRate", "5"),
            (self.sel_rate_graphics, self.input_rate_graphics, "box-rate-graphics", "GraphicsRate", "60"),
        ]

        for sel, inp, box_id, key, def_hz in rate_configs:
            raw_val = vars_dict.get(key, def_hz)
            mode, hz_num = parse_rate_to_mode_and_hz(raw_val, def_hz)
            sel.value = mode
            inp.value = hz_num
            inp.display = (mode == "limited")
            try:
                box_widget = self.query_one(f"#{box_id}")
                box_widget.display = (mode == "limited")
            except Exception:
                pass

        # Simulator info
        games = self.config_overview.get("games", [])
        if games:
            lines = ["[bold #58a6ff]Detected Simulator Configurations :[/]"]
            for g in games:
                jpath = g.get("json_path", "-")
                status = "[bold green]✓ Active[/]" if g.get("json_exists") else "[yellow]Will create on Save[/]"
                lines.append(f"  • [bold white]{g.get('name')}[/] : [cyan]{jpath}[/] ({status})")
            self.lbl_cfg_target_info.update("\n".join(lines))
        else:
            self.lbl_cfg_target_info.update(
                "[yellow]⚠️ No games detected in standard Steam libraries. Save will create files on custom targets.[/]"
            )

    def _read_config_from_form(self) -> dict[str, Any]:
        """Reads user inputs and dropdown selections from the configuration form."""
        try:
            val = self.sel_plugin_enabled.value
            enabled_int = int(str(val)) if val not in (Select.BLANK, Select.NULL, None) else 1
        except Exception:
            enabled_int = 1

        inbound_str = str(self.sel_inbound_ctrl.value) if self.sel_inbound_ctrl.value != Select.NULL else "Enabled"
        sys_events_str = str(self.sel_sys_events.value) if self.sel_sys_events.value != Select.NULL else "Enabled"

        return {
            " Enabled": enabled_int,
            "TargetIP": self.cfg_target_ip.value.strip() or "127.0.0.1",
            "TargetPort": self.cfg_target_port.value.strip() or "5000",
            "InboundControl": inbound_str,
            "InboundPort": self.cfg_inbound_port.value.strip() or "5001",
            "TelemetryRate": format_mode_and_hz_to_rate(str(self.sel_rate_telem.value), self.input_rate_telem.value, "100"),
            "ForceFeedbackRate": format_mode_and_hz_to_rate(str(self.sel_rate_ffb.value), self.input_rate_ffb.value, "400"),
            "FullScoringRate": format_mode_and_hz_to_rate(str(self.sel_rate_full_scoring.value), self.input_rate_full_scoring.value, "5"),
            "CompactScoringRate": format_mode_and_hz_to_rate(str(self.sel_rate_compact_scoring.value), self.input_rate_compact_scoring.value, "20"),
            "WeatherRate": format_mode_and_hz_to_rate(str(self.sel_rate_weather.value), self.input_rate_weather.value, "1"),
            "ExtendedStateRate": format_mode_and_hz_to_rate(str(self.sel_rate_extended.value), self.input_rate_extended.value, "5"),
            "GraphicsRate": format_mode_and_hz_to_rate(str(self.sel_rate_graphics.value), self.input_rate_graphics.value, "60"),
            "SystemEvents": sys_events_str,
            "UnsubscribedBuffersMask": self.cfg_unsub_mask.value.strip() or "0",
        }

    def _rebuild_install_rows(self) -> None:
        """Rebuilds the Install / Config DataTable rows."""
        all_rows = extract_config_rows(self.config_overview)
        query = self.search_query_install.lower()

        if query:
            filtered_rows = [
                r for r in all_rows if query in r[0].lower() or query in r[3].lower() or query in str(r[1]).lower()
            ]
        else:
            filtered_rows = all_rows

        self.table_install.clear()
        self._current_install_keys = []

        for key, _raw_val, fmt_val, desc in filtered_rows:
            self.table_install.add_row(f"[bold #58a6ff]{key}[/]", fmt_val, desc, key=key)
            self._current_install_keys.append(key)

    def _rebuild_commands_rows(self) -> None:
        """Rebuilds the Commands / Inbound DataTable rows."""
        all_rows = extract_inbound_rows(self.engine)
        self.table_commands.clear()
        self._current_commands_keys = []

        for key, _raw_val, fmt_val, desc in all_rows:
            self.table_commands.add_row(f"[bold #58a6ff]{key}[/]", fmt_val, desc, key=key)
            self._current_commands_keys.append(key)

        self.lbl_commands_status.update(
            f"🎮 Inbound Target: [bold cyan]{self.engine.inbound_target_host}:{self.engine.inbound_target_port}[/] | "
            f"Last Command: [bold #58a6ff]{self.engine.last_inbound_cmd_sent}[/] | Pulse: [bold yellow]50 ms[/]"
        )

    def _update_ui(self) -> None:
        """Periodic UI update: polls UDP socket and refreshes active view cells."""
        if not self.is_running:
            return

        self.engine.poll()

        now = time.time()
        elapsed = now - self.engine.start_time
        current_kb_s = sum(s.bandwidth_kb_s for s in self.engine.stats.values())
        current_total_freq = sum(s.current_freq for s in self.engine.stats.values())

        # Update Top Global Metrics Bar
        self.lbl_elapsed.update(f"⏱️ Elapsed: [bold green]{int(elapsed // 60):02d}:{int(elapsed % 60):02d}s[/]")
        self.lbl_packets.update(f"📦 Packets: [bold yellow]{self.engine.total_packets:,}[/]")
        self.lbl_rate.update(f"⚡ Total: [bold magenta]{current_kb_s:5.1f} KB/s[/]")

        # Update Channel Real Reception Frequency
        if self.active_nav == NAV_HOME:
            self.lbl_channel_freq.update(f"📶 [bold cyan]All Streams:[/] [bold yellow]{current_total_freq:5.1f} Hz[/]")
            self._update_home_cards()
        elif self.active_nav == NAV_INSTALL:
            src = self.config_overview.get("source_dll", {})
            status = "Compiled" if src.get("exists") else "Not Compiled"
            self.lbl_channel_freq.update(
                f"⚙️ [bold cyan]Config JSON:[/] [bold {'green' if src.get('exists') else 'red'}]{status}[/]"
            )
            # In-place cell update for Install table
            rows = extract_config_rows(self.config_overview)
            row_map = {r[0]: r[2] for r in rows}
            for key in self._current_install_keys:
                if key in row_map:
                    try:
                        self.table_install.update_cell(key, "col_val", row_map[key])
                    except Exception:
                        pass
        elif self.active_nav == NAV_COMMANDS:
            self.lbl_channel_freq.update(
                f"📶 [bold cyan]Inbound:[/] [bold yellow]{self.engine.inbound_target_host}:{self.engine.inbound_target_port}[/]"
            )
            # In-place cell update for Commands table
            rows = extract_inbound_rows(self.engine)
            row_map = {r[0]: r[2] for r in rows}
            for key in self._current_commands_keys:
                if key in row_map:
                    try:
                        self.table_commands.update_cell(key, "col_val", row_map[key])
                    except Exception:
                        pass
        elif self.active_nav == NAV_EXPLORER:
            if self.active_tab == TAB_TELEM:
                st = self.engine.stats[PKT_RAW_TELEMETRY]
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]TelemInfo:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_SCORING:
                st = (
                    self.engine.stats[PKT_FULL_SCORING]
                    if self.engine.latest_full_scoring and PKT_FULL_SCORING in self.engine.stats
                    else self.engine.stats[PKT_COMPACT_SCORING]
                )
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]Scoring:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_WEATHER:
                st = self.engine.stats[PKT_WEATHER]
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]Weather:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_FFB:
                st = self.engine.stats[PKT_FORCE_FEEDBACK]
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]FFB (400Hz):[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_GRAPHICS:
                st = self.engine.stats[PKT_GRAPHICS]
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]Graphics:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_PHYSICS:
                st = self.engine.stats[PKT_EXTENDED_STATE]
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]Physics & Aids:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_EVENT:
                st = self.engine.stats[PKT_SYSTEM_EVENT]
                self.lbl_channel_freq.update(f"📶 [bold cyan]Events:[/] [bold yellow]{st.count}[/] [dim]pkts[/dim]")
            elif self.active_tab == TAB_STATS:
                self.lbl_channel_freq.update(f"📶 [bold cyan]All Streams:[/] [bold yellow]{current_total_freq:5.1f} Hz[/]")

            # In-place table cell updates for smooth 30 FPS rendering
            rows = self._get_active_explorer_rows()
            row_map = {r[0]: r[2] for r in rows}

            for key in self._current_explorer_keys:
                if key in row_map:
                    try:
                        self.table_explorer.update_cell(key, "col_val", row_map[key])
                    except Exception:
                        pass

    def on_unmount(self) -> None:
        self.engine.stop()


def main():
    parser = argparse.ArgumentParser(description="isiMotor UDP Raw Telemetry Explorer & Benchmark (Textual)")
    parser.add_argument("--host", default="0.0.0.0", help="UDP listening host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="UDP listening port (default: 5000)")
    args = parser.parse_args()

    app = IsiMotorBenchmarkApp(host=args.host, port=args.port)
    app.run()


if __name__ == "__main__":
    main()
