"""
Installation and Configuration Form View composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Label, Static

from ...constants import VIEW_INSTALL

if TYPE_CHECKING:
    from ..app import IsiMotorBenchmarkApp


def compose_install_view(app: IsiMotorBenchmarkApp) -> ComposeResult:
    """Composes the Plugin Installation and JSON Configuration view."""
    with Vertical(id=VIEW_INSTALL):
        with Horizontal(id="install-controls"):
            yield Button("💾 Save Config", id="btn-cfg-save", classes="btn-action")
            yield Button("🔄 Reset Defaults", id="btn-cfg-reset", classes="btn-action")
            yield Button("📦 Copy DLL", id="btn-install-copy-dll", classes="btn-action")
            yield Button("🔄 Reload Disk", id="btn-install-refresh", classes="btn-action")
            yield Button("📋 Copy JSON", id="btn-install-copy-json", classes="btn-action")

        with Horizontal(id="install-form-container"):
            # Left Column: Network, Activations & Files
            with Vertical(classes="cfg-column"):
                with Container(classes="form-section-card"):
                    yield Static("🌐 [bold #58a6ff]1. Network & UDP Socket Setup[/]", classes="form-section-title")
                    with Horizontal(classes="cfg-form-row"):
                        yield Label("Target IP [default: 127.0.0.1]:", classes="cfg-label")
                        yield app.cfg_target_ip
                    with Horizontal(classes="cfg-form-row"):
                        yield Label("Telemetry Port [default: 5000]:", classes="cfg-label")
                        yield app.cfg_target_port
                    with Horizontal(classes="cfg-form-row"):
                        yield Label("Inbound Port [default: 5001]:", classes="cfg-label")
                        yield app.cfg_inbound_port
                    with Horizontal(classes="cfg-form-row"):
                        yield Label("Buffer Skip Mask [default: 0]:", classes="cfg-label")
                        yield app.cfg_unsub_mask

                with Container(classes="form-section-card"):
                    yield Static("🔌 [bold #3fb950]2. Plugin & Feature Activations[/]", classes="form-section-title")
                    with Horizontal(classes="cfg-form-row"):
                        yield Label("Plugin Active [default: 1]:", classes="cfg-label")
                        yield app.sel_plugin_enabled
                    with Horizontal(classes="cfg-form-row"):
                        yield Label("Inbound Control [default: Enabled]:", classes="cfg-label")
                        yield app.sel_inbound_ctrl
                    with Horizontal(classes="cfg-form-row"):
                        yield Label("System Events [default: Enabled]:", classes="cfg-label")
                        yield app.sel_sys_events

                with Container(classes="form-section-card"):
                    yield Static("📂 [bold #e3b341]3. Detected Simulators & JSON Files[/]", classes="form-section-title")
                    yield app.lbl_cfg_target_info

            # Right Column: SIMP Stream Rates
            with Vertical(classes="cfg-column"), Container(classes="form-section-card"):
                yield Static("🏎️ [bold #58a6ff]4. SIMP Stream Rates (Unlimited / Limited Hz / Off)[/]", classes="form-section-title")
                with Horizontal(classes="cfg-rate-row"):
                    yield Label("Telemetry (1888B) [default: unlimited]:", classes="cfg-rate-label")
                    yield app.sel_rate_telem
                    with Horizontal(id="box-rate-telem", classes="cfg-rate-input-box"):
                        yield app.input_rate_telem
                        yield Label("Hz", classes="cfg-hz-unit")
                with Horizontal(classes="cfg-rate-row"):
                    yield Label("Force Feedback [default: unlimited]:", classes="cfg-rate-label")
                    yield app.sel_rate_ffb
                    with Horizontal(id="box-rate-ffb", classes="cfg-rate-input-box"):
                        yield app.input_rate_ffb
                        yield Label("Hz", classes="cfg-hz-unit")
                with Horizontal(classes="cfg-rate-row"):
                    yield Label("Full Scoring (Grid) [default: 5Hz]:", classes="cfg-rate-label")
                    yield app.sel_rate_full_scoring
                    with Horizontal(id="box-rate-full-scoring", classes="cfg-rate-input-box"):
                        yield app.input_rate_full_scoring
                        yield Label("Hz", classes="cfg-hz-unit")
                with Horizontal(classes="cfg-rate-row"):
                    yield Label("Compact Scoring [default: unlimited]:", classes="cfg-rate-label")
                    yield app.sel_rate_compact_scoring
                    with Horizontal(id="box-rate-compact-scoring", classes="cfg-rate-input-box"):
                        yield app.input_rate_compact_scoring
                        yield Label("Hz", classes="cfg-hz-unit")

                with Horizontal(classes="cfg-rate-row"):
                    yield Label("Weather [default: 1Hz]:", classes="cfg-rate-label")
                    yield app.sel_rate_weather
                    with Horizontal(id="box-rate-weather", classes="cfg-rate-input-box"):
                        yield app.input_rate_weather
                        yield Label("Hz", classes="cfg-hz-unit")
                with Horizontal(classes="cfg-rate-row"):
                    yield Label("Extended State & Aids [default: 5Hz]:", classes="cfg-rate-label")
                    yield app.sel_rate_extended
                    with Horizontal(id="box-rate-extended", classes="cfg-rate-input-box"):
                        yield app.input_rate_extended
                        yield Label("Hz", classes="cfg-hz-unit")
                with Horizontal(classes="cfg-rate-row"):
                    yield Label("Graphics & Cameras [default: 60Hz]:", classes="cfg-rate-label")
                    yield app.sel_rate_graphics
                    with Horizontal(id="box-rate-graphics", classes="cfg-rate-input-box"):
                        yield app.input_rate_graphics
                        yield Label("Hz", classes="cfg-hz-unit")
