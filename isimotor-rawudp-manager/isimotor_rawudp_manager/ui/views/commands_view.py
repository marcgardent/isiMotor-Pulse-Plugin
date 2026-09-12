"""
Inbound ZeroMQ Remote Commands View composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.widgets import Button, Static

from ...constants import VIEW_COMMANDS

if TYPE_CHECKING:
    from ..app import IsiMotorBenchmarkApp


def compose_commands_view(app: IsiMotorBenchmarkApp) -> ComposeResult:
    """Composes the Inbound Controls panel view."""
    with Vertical(id=VIEW_COMMANDS):
        yield app.lbl_commands_status
        with Horizontal(id="commands-panels-container"):
            with Vertical(classes="cmd-panel"):
                yield Static("⛽ [bold #e3b341]Pit Menu (Type 100)[/]", classes="cmd-panel-title")
                with Grid(classes="cmd-grid"):
                    yield Button("⬆️ Up", id="btn-cmd-pit-up", classes="cmd-btn")
                    yield Button("⬇️ Down", id="btn-cmd-pit-down", classes="cmd-btn")
                    yield Button("⬅️ Prev", id="btn-cmd-pit-prev", classes="cmd-btn")
                    yield Button("➡️ Next", id="btn-cmd-pit-next", classes="cmd-btn")
                yield Button("✅ Select / Enter", id="btn-cmd-pit-select", variant="success", classes="cmd-btn")

            with Vertical(classes="cmd-panel"):
                yield Static("🌦️ [bold #58a6ff]Weather Override (Type 101)[/]", classes="cmd-panel-title")
                with Grid(classes="cmd-grid"):
                    yield Button("☀️ Clear (0%)", id="btn-cmd-weather-sun", classes="cmd-btn")
                    yield Button("⛅ Drizzle (25%)", id="btn-cmd-weather-drizzle", classes="cmd-btn")
                    yield Button("🌧️ Rain (60%)", id="btn-cmd-weather-rain", classes="cmd-btn")
                    yield Button("⛈️ Storm (95%)", id="btn-cmd-weather-storm", classes="cmd-btn")

            with Vertical(classes="cmd-panel"):
                yield Static("🏎️ [bold #3fb950]Vehicle Aids & Controls[/]", classes="cmd-panel-title")
                with Grid(classes="cmd-grid"):
                    yield Button("🔑 Ignition", id="btn-cmd-ignition", classes="cmd-btn")
                    yield Button("🌧️ Wipers", id="btn-cmd-wipers", classes="cmd-btn")
                    yield Button("🏎️ TC +", id="btn-cmd-tc-up", classes="cmd-btn")
                    yield Button("🏎️ TC -", id="btn-cmd-tc-down", classes="cmd-btn")
                    yield Button("🛑 ABS +", id="btn-cmd-abs-up", classes="cmd-btn")
                    yield Button("🛑 ABS -", id="btn-cmd-abs-down", classes="cmd-btn")

            with Vertical(classes="cmd-panel"):
                yield Static("📤 [bold #bc8cff]Custom Command Sender[/]", classes="cmd-panel-title")
                yield app.input_cmd_name
                yield app.input_cmd_val
                yield Button("📤 Send Command", id="btn-cmd-send-custom", variant="primary", classes="cmd-btn")

        with Container(id="table-container-commands"):
            yield app.table_commands
