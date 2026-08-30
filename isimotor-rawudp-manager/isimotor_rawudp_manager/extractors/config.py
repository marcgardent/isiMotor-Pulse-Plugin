"""
Game installation and CustomPluginVariables.JSON configuration extractor.
"""

from typing import Any

from .base import BaseExtractor, TableRow


def extract_config_rows(overview: dict[str, Any]) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for JSON Configuration overview."""
    rows: list[TableRow] = []

    src = overview.get("source_dll", {})
    dll_exists = src.get("exists", False)
    dll_size = src.get("size_bytes", 0)
    dll_path = src.get("path", "")
    dll_mtime_str = src.get("mtime_str", "-")

    # 1. Source DLL Information
    rows.append(
        (
            "dll.status",
            "Compiled" if dll_exists else "Missing",
            f"[bold green]✓ Compiled ({dll_size:,} B)[/]"
            if dll_exists
            else "[bold red]✗ Not Compiled (run 'make cross')[/]",
            "Status of compiled isiMotor_RawUDP.dll binary",
        )
    )
    rows.append(
        (
            "dll.source_path",
            dll_path if dll_path else "Not found",
            f"[cyan]{dll_path}[/]" if dll_path else "[dim]None[/dim]",
            "Local filesystem path of compiled DLL binary",
        )
    )
    rows.append(
        (
            "dll.last_build",
            dll_mtime_str,
            f"[dim]{dll_mtime_str}[/dim]",
            "Last compilation timestamp",
        )
    )

    # 2. Detected Game Installations
    games = overview.get("games", [])
    if not games:
        rows.append(
            (
                "games.detected",
                0,
                "[bold yellow]⚠️ No games detected in standard Steam library folders[/]",
                "Auto-detection via Steam VDF registry / Linux / SteamDeck paths",
            )
        )
    else:
        for g in games:
            g_name = g.get("name", "Unknown Game")
            g_key = g.get("key", "").lower()
            g_installed = g.get("dll_installed", False)
            g_size = g.get("dll_size", 0)
            g_mtime = g.get("dll_mtime_str", "-")
            g_json = g.get("json_path", "")
            g_json_exists = g.get("json_exists", False)
            g_ext_enabled = g.get("external_plugins_enabled", False)
            g_mask = g.get("plugin_mask", 0)

            rows.append(
                (
                    f"game.{g_key}.name",
                    g_name,
                    f"[bold #58a6ff]{g_name}[/]",
                    f"Root: {g.get('root_dir', '')}",
                )
            )
            rows.append(
                (
                    f"game.{g_key}.dll_status",
                    "Installed" if g_installed else "Not Installed",
                    f"[bold green]✓ Installed ({g_size:,} B, {g_mtime})[/]"
                    if g_installed
                    else "[bold red]✗ Missing in Plugins/[/]",
                    f"Path: {g.get('dll_path', '')}",
                )
            )
            rows.append(
                (
                    f"game.{g_key}.json_config",
                    "Found" if g_json_exists else "Default",
                    f"[bold green]✓ Active[/] [dim]({g_json})[/dim]"
                    if g_json_exists
                    else f"[bold yellow]Default / Not created yet[/] [dim]({g_json})[/dim]",
                    "CustomPluginVariables.JSON profile configuration",
                )
            )
            rows.append(
                (
                    f"game.{g_key}.settings_mask",
                    g_mask,
                    f"[bold green]Enabled: {g_ext_enabled} (Mask: {g_mask})[/]"
                    if g_ext_enabled
                    else "[bold yellow]Disabled in Settings.JSON[/]",
                    "Settings.JSON external plugin execution mask",
                )
            )

    # 3. Active Plugin Variables (CustomPluginVariables.JSON)
    active_vars = overview.get("active_variables", {})
    rows.append(
        (
            "config.Enabled",
            active_vars.get(" Enabled", 1),
            f"[bold {'green' if active_vars.get(' Enabled', 1) else 'red'}]{active_vars.get(' Enabled', 1)}[/]",
            "Main plugin enable switch in isiMotor engine (1=Active, 0=Disabled)",
        )
    )
    rows.append(
        (
            "config.TargetIP",
            active_vars.get("TargetIP", "127.0.0.1"),
            f"[bold cyan]{active_vars.get('TargetIP', '127.0.0.1')}[/]",
            "Target UDP destination IP (Unicast, Multicast 239.x or Broadcast 255.255.255.255)",
        )
    )
    rows.append(
        (
            "config.TargetPort",
            active_vars.get("TargetPort", "5000"),
            f"[bold yellow]{active_vars.get('TargetPort', '5000')}[/]",
            "Target UDP destination port (Default: 5000)",
        )
    )
    rows.append(
        (
            "config.InboundControl",
            active_vars.get("InboundControl", "Enabled"),
            f"[bold {'green' if str(active_vars.get('InboundControl')).lower() in ('enabled', 'true', '1') else 'red'}]{active_vars.get('InboundControl', 'Enabled')}[/]",
            "Bi-directional UDP remote control & hardware inputs (Enabled / Disabled)",
        )
    )
    rows.append(
        (
            "config.InboundPort",
            active_vars.get("InboundPort", "5001"),
            f"[bold yellow]{active_vars.get('InboundPort', '5001')}[/]",
            "Listening UDP port for remote commands (Default: 5001)",
        )
    )
    rows.append(
        (
            "config.TelemetryRate",
            active_vars.get("TelemetryRate", "unlimited"),
            f"[bold #e3b341]{active_vars.get('TelemetryRate', 'unlimited')}[/]",
            "Raw binary TelemInfo streaming rate (unlimited, 60Hz, 100Hz, Off)",
        )
    )
    rows.append(
        (
            "config.CompactScoringRate",
            active_vars.get("CompactScoringRate", "unlimited"),
            f"[bold #e3b341]{active_vars.get('CompactScoringRate', 'unlimited')}[/]",
            "Compact timing & lap scoring stream rate (unlimited, 10Hz, 5Hz, Off)",
        )
    )
    rows.append(
        (
            "config.FullScoringRate",
            active_vars.get("FullScoringRate", "5Hz"),
            f"[bold #e3b341]{active_vars.get('FullScoringRate', '5Hz')}[/]",
            "Multi-vehicle full grid scoring stream rate (5Hz, 10Hz, Off)",
        )
    )
    rows.append(
        (
            "config.TrackRulesRate",
            active_vars.get("TrackRulesRate", "3Hz"),
            f"[bold #e3b341]{active_vars.get('TrackRulesRate', '3Hz')}[/]",
            "Safety car, FCY & track rules stream rate (3Hz, 5Hz, Off)",
        )
    )
    rows.append(
        (
            "config.PitMenuRate",
            active_vars.get("PitMenuRate", "100Hz"),
            f"[bold #e3b341]{active_vars.get('PitMenuRate', '100Hz')}[/]",
            "Interactive pit stop menu stream rate (100Hz, 60Hz, Off)",
        )
    )
    rows.append(
        (
            "config.WeatherRate",
            active_vars.get("WeatherRate", "1Hz"),
            f"[bold #e3b341]{active_vars.get('WeatherRate', '1Hz')}[/]",
            "Ambient weather conditions stream rate (1Hz, 2Hz, Off)",
        )
    )
    rows.append(
        (
            "config.ExtendedStateRate",
            active_vars.get("ExtendedStateRate", "5Hz"),
            f"[bold #e3b341]{active_vars.get('ExtendedStateRate', '5Hz')}[/]",
            "Physics aids, multipliers, damage impact stream rate (5Hz, 10Hz, Off)",
        )
    )
    rows.append(
        (
            "config.ForceFeedbackRate",
            active_vars.get("ForceFeedbackRate", "unlimited"),
            f"[bold #e3b341]{active_vars.get('ForceFeedbackRate', 'unlimited')}[/]",
            "Steering wheel FFB torque stream rate (unlimited @ 400Hz, Off)",
        )
    )
    rows.append(
        (
            "config.GraphicsRate",
            active_vars.get("GraphicsRate", "60Hz"),
            f"[bold #e3b341]{active_vars.get('GraphicsRate', '60Hz')}[/]",
            "Camera & graphics info stream rate (60Hz, 100Hz, Off)",
        )
    )
    rows.append(
        (
            "config.SystemEvents",
            active_vars.get("SystemEvents", "Enabled"),
            f"[bold {'green' if str(active_vars.get('SystemEvents')).lower() in ('enabled', 'true', '1') else 'red'}]{active_vars.get('SystemEvents', 'Enabled')}[/]",
            "Realtime session state change notification events (Enabled / Disabled)",
        )
    )
    rows.append(
        (
            "config.UnsubscribedBuffersMask",
            active_vars.get("UnsubscribedBuffersMask", "0"),
            f"[bold cyan]{active_vars.get('UnsubscribedBuffersMask', '0')}[/]",
            "Shared memory stream disable mask bitfield (0 = all enabled)",
        )
    )

    # 4. Native Hot-Reload Architecture
    rows.append(
        (
            "hotreload.architecture",
            "InternalsPluginV07 Standard",
            "[bold green]✓ Native AccessCustomVariable Callback[/]",
            "Standard isiMotor hot-reload mechanism triggered on game configuration changes",
        )
    )
    rows.append(
        (
            "hotreload.action",
            "Copy DLL",
            "[bold yellow]Click '📦 Copy DLL'[/] to install or update plugin in detected games",
            "Copies DLL and configures CustomPluginVariables.JSON & Settings.JSON automatically",
        )
    )

    return rows


class ConfigExtractor(BaseExtractor):
    """Game installation & configuration presentation extractor."""

    def extract(self, overview: dict[str, Any]) -> list[TableRow]:
        return extract_config_rows(overview)

    def to_dict(self, overview: dict[str, Any]) -> dict[str, Any]:
        return overview
