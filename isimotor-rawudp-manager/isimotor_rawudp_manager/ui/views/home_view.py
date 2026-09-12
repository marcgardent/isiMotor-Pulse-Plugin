"""
Home Dashboard View composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Static

from ...constants import VIEW_HOME

if TYPE_CHECKING:
    from ..app import IsiMotorBenchmarkApp


def compose_home_view(app: IsiMotorBenchmarkApp) -> ComposeResult:
    """Composes the Home summary view."""
    with Vertical(id=VIEW_HOME):
        with Container(id="home-hero-banner"):
            yield Static(
                "🏎️  [bold #58a6ff]isiMotorRawUDP[/] [bold #3fb950]Manager[/] [dim]│ Low-Latency ZeroMQ/FlatBuffers Telemetry & Bidirectional Inbound Bridge[/]",
                id="home-hero-text",
            )
        with Horizontal(id="home-cards-container"):
            with Vertical(id="card-install", classes="home-card"):
                yield Static("📦 [bold #58a6ff]1. Installation & DLL[/]", classes="home-card-header")
                yield app.lbl_home_install
                with Horizontal(classes="home-card-actions"):
                    yield Button(
                        "🚀 Copy DLL",
                        id="btn-home-copy-dll",
                        variant="success",
                        classes="home-card-btn",
                    )
                    yield Button(
                        "📂 Manage ➔",
                        id="btn-home-goto-install",
                        variant="primary",
                        classes="home-card-btn",
                    )

            with Vertical(id="card-config", classes="home-card"):
                yield Static("⚙️ [bold #e3b341]2. Active Config[/]", classes="home-card-header")
                yield app.lbl_home_config
                with Horizontal(classes="home-card-actions"):
                    yield Button(
                        "⚙️ View Config Details ➔",
                        id="btn-home-goto-config",
                        variant="primary",
                        classes="home-card-btn",
                    )

            with Vertical(id="card-network", classes="home-card"):
                yield Static("🌐 [bold #3fb950]3. ZeroMQ Network & Live[/]", classes="home-card-header")
                yield app.lbl_home_network
                with Horizontal(classes="home-card-actions"):
                    yield Button(
                        "🔍 Explorer ➔",
                        id="btn-home-goto-explorer",
                        variant="primary",
                        classes="home-card-btn",
                    )
                    yield Button(
                        "🎮 Controls ➔",
                        id="btn-home-goto-commands",
                        variant="default",
                        classes="home-card-btn",
                    )
