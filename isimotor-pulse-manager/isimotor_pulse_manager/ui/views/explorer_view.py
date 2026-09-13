"""
Live Stream Explorer View composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button

from ...constants import VIEW_EXPLORER

if TYPE_CHECKING:
    from ..app import IsiMotorBenchmarkApp


def compose_explorer_view(app: IsiMotorBenchmarkApp) -> ComposeResult:
    """Composes the Stream Explorer view with tab bar, search input and data table."""
    with Vertical(id=VIEW_EXPLORER):
        with Horizontal(id="explorer-controls"):
            yield app.packet_tabs
            yield app.search_explorer
            with Horizontal(classes="actions-box"):
                yield Button("📋 Copy JSON", id="btn-explorer-copy-json", classes="btn-action")
                yield Button("📑 Copy Table", id="btn-explorer-copy-table", classes="btn-action")
                yield Button("🔄 Reset Stats", id="btn-explorer-reset-stats", classes="btn-action")
        with Container(id="table-container-explorer"):
            yield app.table_explorer
