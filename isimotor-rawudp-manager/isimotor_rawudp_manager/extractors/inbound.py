"""
Inbound controls and live feedback extractor.
"""

import time
from typing import Any

from ..engine.telemetry_engine import TelemetryEngine
from .base import BaseExtractor, TableRow


def extract_inbound_rows(engine: TelemetryEngine) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for Inbound Control testing."""
    rows: list[TableRow] = []
    rows.append(("_inbound.status", "Active", "[bold green]Online / Ready[/]", "Status of Inbound UDP Control socket"))
    rows.append(
        (
            "_inbound.target_host",
            engine.inbound_target_host,
            f"[cyan]{engine.inbound_target_host}[/]",
            "Destination IP for HW / Weather commands",
        )
    )
    rows.append(
        (
            "_inbound.target_port",
            engine.inbound_target_port,
            f"[yellow]{engine.inbound_target_port}[/]",
            "Destination Inbound UDP Port (default: 5001)",
        )
    )
    rows.append(
        (
            "_inbound.last_command",
            engine.last_inbound_cmd_sent,
            f"[bold #58a6ff]{engine.last_inbound_cmd_sent}[/]",
            "Last transmitted command name or payload",
        )
    )
    rows.append(
        (
            "_inbound.last_command_time",
            engine.last_inbound_cmd_time,
            f"{time.strftime('%H:%M:%S', time.localtime(engine.last_inbound_cmd_time))}"
            if engine.last_inbound_cmd_time > 0
            else "-",
            "Timestamp of last command sent",
        )
    )
    rows.append(("_inbound.pulse_duration", 50, "50 ms", "Default pulse hold time before auto-release"))
    rows.append(
        (
            "_inbound.interactive_keys",
            "U / D / L / R / Enter / W",
            "[bold yellow]U[/]: Pit Up | [bold yellow]D[/]: Pit Down | [bold yellow]L[/]: Prev | [bold yellow]R[/]: Next | [bold yellow]Enter[/]: Select | [bold yellow]W[/]: Rain Injection",
            "Interactive Keyboard Shortcuts to trigger live UDP commands",
        )
    )
    rows.append(
        (
            "_inbound.supported_controls",
            "12 items",
            "PitMenuUp/Down/Prev/Next/Select, TCIncrease/Decrease, ABSIncrease/Decrease, BrakeBias, Ignition, Wipers",
            "Supported CheckHWControl identifiers",
        )
    )

    # Live Feedback from connected channels
    if engine.latest_weather:
        w = engine.latest_weather
        rows.append(
            (
                "live_feedback.ambient_temp_c",
                w.ambient_temp_c,
                f"[bold green]{w.ambient_temp_c:.1f} °C[/]",
                "Live ambient temperature reflected from Type 7 stream",
            )
        )
        rows.append(
            (
                "live_feedback.rain_intensity",
                w.origin_raining,
                f"[bold green]{w.origin_raining * 100:.1f} %[/]",
                "Live rain intensity reflected from Type 7 stream",
            )
        )

    return rows


class InboundExtractor(BaseExtractor):
    """Inbound commands & bridge diagnostics presentation extractor."""

    def extract(self, engine: TelemetryEngine) -> list[TableRow]:
        return extract_inbound_rows(engine)

    def to_dict(self, engine: TelemetryEngine) -> dict[str, Any]:
        rows = extract_inbound_rows(engine)
        return {k: raw for k, raw, _, _ in rows}
