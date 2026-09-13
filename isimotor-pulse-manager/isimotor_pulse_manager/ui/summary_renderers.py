"""
Rich markup renderers for home dashboard cards.
"""

from pathlib import Path
from typing import Any

from ..engine.telemetry_engine import TelemetryEngine


def render_home_install_summary(overview: dict[str, Any]) -> str:
    """Renders formatted Rich markup for the Home Installation summary card."""
    src = overview.get("source_dll", {})
    dll_exists = src.get("exists", False)
    dll_size = src.get("size_bytes", 0)
    dll_mtime = src.get("mtime_str", "-")
    dll_path = src.get("path", "")

    lines: list[str] = []
    if dll_exists:
        lines.append(f"• [bold white]DLL Binary :[/] [bold green]✓ Compiled[/] [dim]({dll_size:,} B)[/dim]")
        lines.append(f"• [bold white]Last Build :[/] [dim]{dll_mtime}[/dim]")
        if dll_path:
            lines.append(f"• [bold white]Source :[/] [cyan]{Path(dll_path).name}[/]")
    else:
        lines.append("• [bold white]DLL Binary :[/] [bold red]✗ Not compiled[/] [dim]('make cross')[/dim]")

    lines.append("[bold #58a6ff]Detected Simulators :[/]")
    games = overview.get("games", [])
    if not games:
        lines.append("  [dim]• None in default Steam library[/dim]")
    else:
        for g in games:
            g_name = g.get("name", "Game")
            g_inst = g.get("dll_installed", False)
            g_ext = g.get("external_plugins_enabled", False)
            inst_tag = "[bold green]✓ Installed[/]" if g_inst else "[bold red]✗ Missing[/]"
            ext_tag = "[bold green]✓ Active[/]" if g_ext else "[yellow]⚠️ Inactive[/]"
            lines.append(f"  • [white]{g_name}[/] : {inst_tag} | {ext_tag}")

    return "\n".join(lines)


def render_home_config_summary(overview: dict[str, Any]) -> str:
    """Renders formatted Rich markup for the Home Configuration summary card."""
    vars_dict = overview.get("active_variables", {})
    target_ip = vars_dict.get("TcpHost", "127.0.0.1")
    target_port = vars_dict.get("TcpBasePort", "5000")
    inbound_ctrl = vars_dict.get("InboundControl", "Enabled")
    inbound_port = vars_dict.get("InboundTcpPort", "5101")
    player_telem = vars_dict.get("PlayerTelemetryRate", vars_dict.get("TelemetryRate", "unlimited"))
    opponent_telem = vars_dict.get("OpponentTelemetryRate", "off")
    scoring_rate = vars_dict.get("FullScoringRate", "5Hz")
    compact_rate = vars_dict.get("CompactScoringRate", "10Hz")
    weather_rate = vars_dict.get("WeatherRate", "1Hz")
    ffb_rate = vars_dict.get("ForceFeedbackRate", "unlimited (400Hz)")

    lines = [
        f"• [bold white]ZeroMQ PUB Endpoint:[/] [bold cyan]tcp://{target_ip}:{target_port}[/]",
        f"• [bold white]Inbound Control    :[/] [bold green]{inbound_ctrl}[/] [dim](Port {inbound_port})[/dim]",
        f"• [bold white]Player / Opponents :[/] [bold #58a6ff]{player_telem}[/] / [cyan]{opponent_telem}[/]",
        f"• [bold white]Scoring (Full / C) :[/] [cyan]{scoring_rate}[/] / [cyan]{compact_rate}[/]",
        f"• [bold white]Weather Rate       :[/] [cyan]{weather_rate}[/]",
        f"• [bold white]Force Feedback     :[/] [bold #bc8cff]{ffb_rate}[/]",
    ]
    return "\n".join(lines)


def render_home_network_summary(engine: TelemetryEngine, elapsed: float) -> str:
    """Renders formatted Rich markup for the Home Connectivity summary card."""
    total_kb_s = sum(s.bandwidth_kb_s for s in engine.stats.values())
    total_freq = sum(s.display_freq for s in engine.stats.values())

    if engine.total_packets > 0 and total_freq > 0.1:
        status_tag = "[bold green]🟢 Streaming (Game Active)[/]"
    elif engine.total_packets > 0:
        status_tag = "[bold yellow]🟡 Paused (No new packets)[/]"
    else:
        status_tag = "[bold yellow]🟡 Listening (Waiting for game)[/]"

    min_sec = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}s"

    lines = [
        f"• [bold white]Telemetry ZeroMQ Base:[/] [bold cyan]{engine.host}:{engine.port}[/]",
        f"• [bold white]Connection Status    :[/] {status_tag}",
        f"• [bold white]Total Packets        :[/] [bold yellow]{engine.total_packets:,}[/] pkts",
        f"• [bold white]Current Bandwidth    :[/] [bold magenta]{total_kb_s:5.1f} KB/s[/] [dim]({total_freq:5.1f} Hz)[/dim]",
        f"• [bold white]Session Duration     :[/] [bold green]{min_sec}[/]",
        f"• [bold white]Inbound Commands     :[/] [cyan]{engine.inbound_target_host}:{engine.inbound_target_port}[/]",
    ]
    return "\n".join(lines)
