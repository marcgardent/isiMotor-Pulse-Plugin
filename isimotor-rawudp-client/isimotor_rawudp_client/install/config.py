"""
JSON configuration management for the isiMotor_RawUDP plugin.
Reads and writes CustomPluginVariables.JSON / Settings.JSON in a game's
UserData directory, and builds a structured configuration overview.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from .steam import SUPPORTED_GAMES, detect_game_installations

logger = logging.getLogger("isimotor_rawudp_client.install")

# Default configuration variables matching InternalsPluginV07 CustomVariable definitions (Human-readable string values)
DEFAULT_PLUGIN_VARIABLES: dict[str, int | str] = {
    " Enabled": 1,
    "EnableLogging": "Disabled",
    "TcpHost": "127.0.0.1",
    "TcpPort": "5000",
    "InboundControl": "Enabled",
    "InboundTcpHost": "127.0.0.1",
    "InboundTcpPort": "5001",
    "PlayerTelemetryRate": "unlimited",
    "OpponentTelemetryRate": "off",
    "CompactScoringRate": "10Hz",
    "FullScoringRate": "5Hz",
    "WeatherRate": "1Hz",
    "ExtendedStateRate": "5Hz",
    "ForceFeedbackRate": "unlimited",
    "GraphicsRate": "60Hz",
    "SystemEvents": "Enabled",
    "UnsubscribedBuffersMask": "0",
}


def configure_game_json(game_dir: Path, plugin_dll_name: str = "isiMotor_RawUDP.dll") -> bool:
    """
    Configures CustomPluginVariables.JSON and Settings.JSON in game UserData directory.
    Enables external plugins and registers the DLL with full standard default values.
    """
    success = True
    dll_key = plugin_dll_name if plugin_dll_name.lower().endswith(".dll") else f"{plugin_dll_name}.dll"
    base_name = dll_key.replace(".dll", "")
    alt_name = base_name.replace("_", "-")

    # 1. Configure CustomPluginVariables.JSON
    json_targets = [
        game_dir / "UserData" / "player" / "CustomPluginVariables.JSON",
        game_dir / "UserData" / "CustomPluginVariables.JSON",
    ]

    for jpath in json_targets:
        try:
            jpath.parent.mkdir(parents=True, exist_ok=True)
            data: dict[str, dict] = {}
            if jpath.exists():
                try:
                    content = jpath.read_text(encoding="utf-8", errors="ignore").strip()
                    parsed = json.loads(content) if content else {}
                    if isinstance(parsed, dict):
                        data = parsed
                except Exception:
                    data = {}

            # Read existing configuration from dll_key or legacy names
            merged = dict(DEFAULT_PLUGIN_VARIABLES)
            for k in [dll_key, base_name, alt_name]:
                if k in data and isinstance(data[k], dict):
                    merged.update(data[k])

            # Clean up redundant legacy keys without .dll
            data.pop(base_name, None)
            data.pop(alt_name, None)

            # Store ONLY under the exact .dll key (standard ISI / rFactor 2 convention)
            data[dll_key] = merged

            jpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.info(f"  ✓ Configured plugin variables: {jpath}")
        except Exception as e:
            logger.error(f"  ✗ Error writing JSON {jpath}: {e}")
    # 2. Configure Settings.JSON (Plugin Mask = 255, Enable external plugins = True)
    settings_targets = [
        game_dir / "UserData" / "player" / "Settings.JSON",
        game_dir / "UserData" / "Settings.JSON",
    ]
    for spath in settings_targets:
        if spath.exists():
            try:
                content = spath.read_text(encoding="utf-8", errors="ignore").strip()
                sdata = json.loads(content) if content else {}
                if isinstance(sdata, dict):
                    game_opts = sdata.setdefault("Game Options", {})
                    if isinstance(game_opts, dict):
                        game_opts["Enable external plugins"] = True
                        game_opts["Plugin Mask"] = 255
                    sdata["Enable external plugins"] = True
                    sdata["Plugin Mask"] = 255
                    spath.write_text(json.dumps(sdata, indent=2), encoding="utf-8")
                    logger.info(f"  ✓ Enabled external plugins mask in: {spath}")
            except Exception as e:
                logger.error(f"  ✗ Error writing Settings.JSON {spath}: {e}")
                success = False

    return success


def read_plugin_json_variables(json_path: Path, plugin_name: str = "isiMotor_RawUDP.dll") -> dict[str, Any]:
    """Reads and parses CustomPluginVariables.JSON for isiMotor_RawUDP variables."""
    base_name = plugin_name.replace(".dll", "")
    alt_name = base_name.replace("_", "-")
    result = dict(DEFAULT_PLUGIN_VARIABLES)

    if not json_path.exists():
        return result

    try:
        content = json_path.read_text(encoding="utf-8", errors="ignore").strip()
        data = json.loads(content) if content else {}
        if isinstance(data, dict):
            for k in [plugin_name, base_name, alt_name]:
                if k in data and isinstance(data[k], dict):
                    result.update(data[k])
                    break
    except Exception as e:
        logger.warning(f"Warning reading plugin variables from {json_path}: {e}")

    return result


def write_plugin_json_variables(
    game_dir: Path,
    variables: dict[str, Any],
    plugin_dll_name: str = "isiMotor_RawUDP.dll",
) -> tuple[bool, str]:
    """Writes or updates isiMotor_RawUDP configuration variables inside CustomPluginVariables.JSON."""
    dll_key = plugin_dll_name if plugin_dll_name.lower().endswith(".dll") else f"{plugin_dll_name}.dll"
    base_name = dll_key.replace(".dll", "")
    alt_name = base_name.replace("_", "-")

    json_targets = [
        game_dir / "UserData" / "player" / "CustomPluginVariables.JSON",
        game_dir / "UserData" / "CustomPluginVariables.JSON",
    ]

    updated_files: list[str] = []
    for jpath in json_targets:
        try:
            jpath.parent.mkdir(parents=True, exist_ok=True)
            data: dict[str, dict] = {}
            if jpath.exists():
                try:
                    content = jpath.read_text(encoding="utf-8", errors="ignore").strip()
                    parsed = json.loads(content) if content else {}
                    if isinstance(parsed, dict):
                        data = parsed
                except Exception:
                    data = {}

            # Prepare merged dict preserving type for ' Enabled'
            merged = dict(DEFAULT_PLUGIN_VARIABLES)
            for k in [dll_key, base_name, alt_name]:
                if k in data and isinstance(data[k], dict):
                    merged.update(data[k])
            merged.update(variables)

            if " Enabled" in merged:
                try:
                    merged[" Enabled"] = int(merged[" Enabled"])
                except Exception:
                    merged[" Enabled"] = 1

            # Clean up redundant legacy keys without .dll
            data.pop(base_name, None)
            data.pop(alt_name, None)

            # Store ONLY under the exact .dll key (standard ISI / rFactor 2 convention)
            data[dll_key] = merged

            jpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
            updated_files.append(str(jpath))
        except Exception as e:
            return False, f"Failed writing {jpath}: {e}"

    # Also make sure Settings.JSON has external plugins enabled
    settings_targets = [
        game_dir / "UserData" / "player" / "Settings.JSON",
        game_dir / "UserData" / "Settings.JSON",
    ]
    for spath in settings_targets:
        if spath.exists():
            try:
                content = spath.read_text(encoding="utf-8", errors="ignore").strip()
                sdata = json.loads(content) if content else {}
                if isinstance(sdata, dict):
                    sdata["Enable external plugins"] = True
                    sdata["Plugin Mask"] = 255
                    spath.write_text(json.dumps(sdata, indent=2), encoding="utf-8")
            except Exception:
                pass

    return True, f"Updated {len(updated_files)} JSON file(s)"


def save_configuration_to_all_games(
    variables: dict[str, Any],
    custom_target: Path | None = None,
    project_root: Path | None = None,
) -> tuple[bool, str, list[str]]:
    """Saves the provided variables dictionary into all detected game installations (or custom target)."""
    targets: list[Path] = []
    if custom_target:
        targets.append(Path(custom_target))
    else:
        detected = detect_game_installations()
        for dirs in detected.values():
            for d in dirs:
                if d not in targets:
                    targets.append(d)

    if not targets:
        return False, "No game installations found to save configuration to.", []

    saved_paths: list[str] = []
    for gdir in targets:
        ok, msg = write_plugin_json_variables(gdir, variables)
        if ok:
            saved_paths.append(str(gdir))
        else:
            return False, msg, saved_paths

    return True, f"Configuration successfully saved to {len(saved_paths)} game installation(s)!", saved_paths


def get_configuration_overview(
    project_root: Path | None = None,
    custom_dll: Path | None = None,
    custom_target: Path | None = None,
) -> dict[str, Any]:
    """
    Returns a comprehensive structured overview of compiled DLL status,
    detected game installations, JSON config files, and active variables.
    """
    from .dll import find_source_dll, get_project_root  # local import: avoid circular import with dll.py

    root = project_root or get_project_root()
    src_dll = find_source_dll(root, custom_dll)

    dll_info: dict[str, Any] = {
        "path": str(src_dll) if src_dll else "",
        "filename": src_dll.name if src_dll else "isiMotor_RawUDP.dll",
        "exists": bool(src_dll and src_dll.exists()),
        "size_bytes": src_dll.stat().st_size if (src_dll and src_dll.exists()) else 0,
        "mtime": src_dll.stat().st_mtime if (src_dll and src_dll.exists()) else 0.0,
        "mtime_str": (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(src_dll.stat().st_mtime))
            if (src_dll and src_dll.exists())
            else "-"
        ),
    }

    targets: list[tuple[str, str, Path]] = []
    if custom_target:
        targets.append(("CUSTOM", "Custom Target Path", Path(custom_target)))
    else:
        detected = detect_game_installations()
        for game_key, dirs in detected.items():
            name = SUPPORTED_GAMES[game_key]["name"]
            for d in dirs:
                targets.append((game_key, name, d))

    games_list: list[dict[str, Any]] = []
    active_vars: dict[str, Any] = dict(DEFAULT_PLUGIN_VARIABLES)

    for game_key, game_name, gdir in targets:
        plugin_dll = gdir / "Plugins" / "isiMotor_RawUDP.dll"
        root_dll = gdir / "isiMotor_RawUDP.dll"
        dll_installed = plugin_dll.exists() or root_dll.exists()
        active_dll_path = plugin_dll if plugin_dll.exists() else root_dll

        json_player = gdir / "UserData" / "player" / "CustomPluginVariables.JSON"
        json_root = gdir / "UserData" / "CustomPluginVariables.JSON"
        active_json_path = json_player if json_player.exists() else json_root
        json_exists = active_json_path.exists()
        parsed_vars = read_plugin_json_variables(active_json_path) if json_exists else dict(DEFAULT_PLUGIN_VARIABLES)

        if json_exists and active_vars == DEFAULT_PLUGIN_VARIABLES:
            active_vars = dict(parsed_vars)

        settings_player = gdir / "UserData" / "player" / "Settings.JSON"
        settings_root = gdir / "UserData" / "Settings.JSON"
        active_settings = settings_player if settings_player.exists() else settings_root
        settings_exists = active_settings.exists()
        ext_enabled = False
        plugin_mask = 0

        if settings_exists:
            try:
                s_content = active_settings.read_text(encoding="utf-8", errors="ignore").strip()
                s_data = json.loads(s_content) if s_content else {}
                if isinstance(s_data, dict):
                    ext_enabled = bool(s_data.get("Enable external plugins", False))
                    plugin_mask = int(s_data.get("Plugin Mask", 0))
            except Exception:
                pass

        games_list.append(
            {
                "key": game_key,
                "name": game_name,
                "root_dir": str(gdir),
                "plugins_dir": str(gdir / "Plugins"),
                "dll_path": str(active_dll_path),
                "dll_installed": dll_installed,
                "dll_size": active_dll_path.stat().st_size if dll_installed else 0,
                "dll_mtime_str": (
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(active_dll_path.stat().st_mtime))
                    if dll_installed
                    else "-"
                ),
                "json_path": str(active_json_path),
                "json_exists": json_exists,
                "variables": parsed_vars,
                "settings_path": str(active_settings),
                "settings_exists": settings_exists,
                "external_plugins_enabled": ext_enabled,
                "plugin_mask": plugin_mask,
            }
        )

    return {
        "source_dll": dll_info,
        "games": games_list,
        "active_variables": active_vars,
        "default_variables": DEFAULT_PLUGIN_VARIABLES,
    }
