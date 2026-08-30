#!/usr/bin/env python3
"""
isiMotor-RawUDP-Plugin — Automated Game Detector & Plugin Installer.
Auto-detects Steam installations for Le Mans Ultimate and rFactor 2,
copies isiMotor_RawUDP.dll to Plugins/, and configures CustomPluginVariables.JSON / Settings.JSON.

Copyright 2026 Marc GARDENT
Licensed under the Apache License, Version 2.0.
"""

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("installer")


# ── Steam VDF Discovery ────────────────────────────────────────────────────────


def get_steam_vdf_candidate_paths() -> list[Path]:
    """
    Returns candidate paths for Steam's libraryfolders.vdf configuration file
    across Windows (Registry + Env vars), Linux (Native), Linux (Flatpak), and SteamDeck.
    """
    candidates: list[Path] = []

    # 1. Windows: Registry & Environment Variables
    if sys.platform == "win32":
        try:
            import winreg

            for hkey, reg_path, val_name in [
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
            ]:
                try:
                    with winreg.OpenKey(hkey, reg_path) as key:
                        val, _ = winreg.QueryValueEx(key, val_name)
                        if val:
                            vdf = Path(val) / "steamapps" / "libraryfolders.vdf"
                            if vdf not in candidates:
                                candidates.append(vdf)
                except OSError:
                    pass
        except ImportError:
            pass

        for env_var in ["ProgramFiles(x86)", "ProgramFiles", "ProgramW6432"]:
            pf = os.environ.get(env_var)
            if pf:
                vdf = Path(pf) / "Steam" / "steamapps" / "libraryfolders.vdf"
                if vdf not in candidates:
                    candidates.append(vdf)

        sys_drive = os.environ.get("SystemDrive", "C:")
        vdf = Path(sys_drive + "/") / "Steam" / "steamapps" / "libraryfolders.vdf"
        if vdf not in candidates:
            candidates.append(vdf)

    # 2. Linux (Native, Flatpak, Snap, Steam Deck)
    home = Path.home()
    linux_paths = [
        home / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf",
        home / ".steam" / "steam" / "steamapps" / "libraryfolders.vdf",
        home / ".steam" / "root" / "steamapps" / "libraryfolders.vdf",
        home
        / ".var"
        / "app"
        / "com.valvesoftware.Steam"
        / ".local"
        / "share"
        / "Steam"
        / "steamapps"
        / "libraryfolders.vdf",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".steam" / "steam" / "steamapps" / "libraryfolders.vdf",
        home / "snap" / "steam" / "common" / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf",
    ]
    for p in linux_paths:
        if p not in candidates:
            candidates.append(p)

    return candidates


def parse_vdf_library_paths(vdf_path: Path) -> list[Path]:
    """Parses a Steam libraryfolders.vdf file and extracts all registered library roots."""
    import re

    library_paths: list[Path] = []
    if not vdf_path.exists():
        return library_paths

    try:
        content = vdf_path.read_text(encoding="utf-8", errors="ignore")
        matches = re.findall(r'"path"\s+"([^"]+)"', content, flags=re.IGNORECASE)
        for raw_path in matches:
            cleaned_path = raw_path.replace("\\\\", "\\")
            p = Path(cleaned_path)
            if p.exists() and p not in library_paths:
                library_paths.append(p)
    except Exception as e:
        logger.warning(f"Warning reading VDF {vdf_path}: {e}")

    return library_paths


# ── Game Detection ─────────────────────────────────────────────────────────────

SUPPORTED_GAMES = {
    "LMU": {
        "name": "Le Mans Ultimate",
        "subpath": "Le Mans Ultimate",
        "exe": "Le Mans Ultimate.exe",
    },
    "rF2": {
        "name": "rFactor 2",
        "subpath": "rFactor 2",
        "exe": "rFactor2.exe",
    },
}


def get_known_game_paths(game_subpath: str, game_exe: str) -> list[Path]:
    """Fallback list of known game installation directories."""
    paths: list[Path] = []
    if os.name == "nt":
        for env_var in ["ProgramFiles(x86)", "ProgramFiles", "ProgramW6432"]:
            pf = os.environ.get(env_var)
            if pf:
                paths.append(Path(pf) / "Steam" / "steamapps" / "common" / game_subpath)
        for drive in ["C:/", "D:/", "E:/", "F:/", "G:/", "Z:/"]:
            paths.append(Path(drive) / "SteamLibrary" / "steamapps" / "common" / game_subpath)
            paths.append(Path(drive) / "Games" / "Steam" / "steamapps" / "common" / game_subpath)

    home = Path.home()
    paths.extend(
        [
            home / ".steam" / "steam" / "steamapps" / "common" / game_subpath,
            home / ".local" / "share" / "Steam" / "steamapps" / "common" / game_subpath,
            home
            / ".var"
            / "app"
            / "com.valvesoftware.Steam"
            / ".local"
            / "share"
            / "Steam"
            / "steamapps"
            / "common"
            / game_subpath,
            home
            / ".var"
            / "app"
            / "com.valvesoftware.Steam"
            / ".steam"
            / "steam"
            / "steamapps"
            / "common"
            / game_subpath,
        ]
    )
    return paths


def detect_game_installations() -> dict[str, list[Path]]:
    """Detects all installed isiMotor / rFactor 2 / Le Mans Ultimate game directories."""
    results: dict[str, list[Path]] = {"LMU": [], "rF2": []}
    vdf_candidates = get_steam_vdf_candidate_paths()
    all_lib_paths: list[Path] = []

    for vdf in vdf_candidates:
        if vdf.exists():
            for lib in parse_vdf_library_paths(vdf):
                if lib not in all_lib_paths:
                    all_lib_paths.append(lib)

    for game_key, info in SUPPORTED_GAMES.items():
        found = results[game_key]
        for lib in all_lib_paths:
            game_dir = lib / "steamapps" / "common" / info["subpath"]
            if game_dir.exists() and (game_dir / info["exe"]).exists():
                if game_dir not in found:
                    found.append(game_dir)

        for fallback in get_known_game_paths(info["subpath"], info["exe"]):
            if fallback.exists() and (fallback / info["exe"]).exists():
                if fallback not in found:
                    found.append(fallback)

    return results


# ── DLL & Project Path Resolution ──────────────────────────────────────────────


def get_project_root() -> Path:
    """Returns the root path of the isiMotor-RawUDP-Plugin repository."""
    current = Path(__file__).resolve()
    for parent in [current.parent, current.parent.parent, current.parent.parent.parent]:
        if (parent / "isimotor-rawudp-plugin").exists() or (parent / "isimotor-rawudp-client").exists():
            return parent
    return current.parent.parent.parent


def find_source_dll(project_root: Path | None = None, custom_dll_path: Path | None = None) -> Path | None:
    """Finds the compiled isiMotor_RawUDP.dll binary across bundled resources and build paths."""
    if custom_dll_path and custom_dll_path.exists() and custom_dll_path.is_file():
        return custom_dll_path

    # 1. Bundled Resources (Briefcase / Standalone package data)
    pkg_dir = Path(__file__).resolve().parent
    bundled_candidates = [
        pkg_dir / "resources" / "isiMotor_RawUDP.dll",
        pkg_dir.parent / "resources" / "isiMotor_RawUDP.dll",
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        meipass_path = Path(meipass)
        bundled_candidates.append(meipass_path / "resources" / "isiMotor_RawUDP.dll")
        bundled_candidates.append(meipass_path / "isiMotor_RawUDP.dll")

    for cand in bundled_candidates:
        if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
            return cand

    # 2. Local workspace and build folders
    root = project_root or get_project_root()
    candidates = [
        root / "build" / "isiMotor_RawUDP.dll",
        root / "build" / "isimotor-rawudp-plugin" / "isiMotor_RawUDP.dll",
        root / "bin" / "isiMotor_RawUDP.dll",
        root / "isimotor-rawudp-plugin" / "bin" / "isiMotor_RawUDP.dll",
        root / "isimotor-rawudp-plugin" / "build" / "isiMotor_RawUDP.dll",
        root / "isiMotor_RawUDP.dll",
        root / "build" / "Release" / "isiMotor_RawUDP.dll",
        root / "bin" / "Release" / "isiMotor_RawUDP.dll",
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
            return cand
    return None


# Default configuration variables matching InternalsPluginV07 CustomVariable definitions (Human-readable string values)
DEFAULT_PLUGIN_VARIABLES: dict[str, int | str] = {
    " Enabled": 1,
    "TargetIP": "127.0.0.1",
    "TargetPort": "5000",
    "InboundControl": "Enabled",
    "InboundPort": "5001",
    "TelemetryRate": "unlimited",
    "CompactScoringRate": "unlimited",
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


# ── Installer Workflow ─────────────────────────────────────────────────────────


def install_plugin(
    project_root: Path | None = None,
    custom_dll: Path | None = None,
    target_dir: Path | None = None,
    dry_run: bool = False,
) -> bool:
    """Executes full plugin installation and configuration workflow."""
    root = project_root or get_project_root()
    src_dll = find_source_dll(root, custom_dll)

    if not src_dll:
        logger.error("❌ Error: Compiled 'isiMotor_RawUDP.dll' not found.")
        logger.error("   Run 'make cross' (or 'make build') to compile the DLL before installing.")
        return False

    logger.info("==================================================================")
    logger.info("  🏎️  isiMotor-RawUDP-Plugin — Installer")
    logger.info("==================================================================")
    logger.info(f"Source Binary : {src_dll} ({src_dll.stat().st_size:,} bytes)")

    targets: list[tuple[str, Path]] = []
    if target_dir:
        targets.append(("Custom Path", Path(target_dir)))
    else:
        detected = detect_game_installations()
        for game_key, dirs in detected.items():
            name = SUPPORTED_GAMES[game_key]["name"]
            for d in dirs:
                targets.append((name, d))

    if not targets:
        logger.warning("\n⚠️  No Le Mans Ultimate or rFactor 2 installations were detected.")
        logger.warning("   You can specify your game directory manually in the Manager UI or via CLI:")
        logger.warning('   python -m isimotor_rawudp_manager.installer --target-dir "/path/to/game"')
        return False

    installed_count = 0
    for game_name, gdir in targets:
        logger.info(f"\n📂 Installing into: {game_name} ({gdir})")
        plugins_dir = gdir / "Plugins"

        if dry_run:
            logger.info(f"  [DRY-RUN] Would copy {src_dll.name} -> {plugins_dir / src_dll.name}")
            logger.info("  [DRY-RUN] Would configure CustomPluginVariables.JSON & Settings.JSON")
            continue

        try:
            plugins_dir.mkdir(parents=True, exist_ok=True)
            target_plugin_dll = plugins_dir / src_dll.name
            shutil.copy2(src_dll, target_plugin_dll)
            logger.info(f"  ✓ Copied DLL -> {target_plugin_dll}")

            # Configure JSON settings
            configure_game_json(gdir, src_dll.name)
            installed_count += 1
        except Exception as e:
            logger.error(f"  ✗ Failed to install in {gdir}: {e}")

    if dry_run:
        logger.info("\n✨ Dry run complete.")
        return True

    if installed_count > 0:
        logger.info(f"\n🎉 Plugin successfully installed into {installed_count} game installation(s)!")
        logger.info("   You can now launch the game and run 'make benchmark' to inspect live packets.")
        return True

    return False


def uninstall_plugin(target_dir: Path | None = None) -> bool:
    """Removes isiMotor_RawUDP.dll from detected game installations."""
    logger.info("==================================================================")
    logger.info("  🗑️  isiMotor-RawUDP-Plugin — Uninstaller")
    logger.info("==================================================================")

    targets: list[Path] = []
    if target_dir:
        targets.append(Path(target_dir))
    else:
        detected = detect_game_installations()
        for dirs in detected.values():
            targets.extend(dirs)

    removed = 0
    for gdir in targets:
        logger.info(f"\n📂 Checking: {gdir}")
        for dll_path in [gdir / "Plugins" / "isiMotor_RawUDP.dll", gdir / "isiMotor_RawUDP.dll"]:
            if dll_path.exists():
                try:
                    dll_path.unlink()
                    logger.info(f"  ✓ Removed: {dll_path}")
                    removed += 1
                except Exception as e:
                    logger.error(f"  ✗ Could not remove {dll_path}: {e}")

    logger.info(f"\n✨ Uninstallation complete ({removed} file(s) removed).")
    return True


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


def get_configuration_overview(
    project_root: Path | None = None,
    custom_dll: Path | None = None,
    custom_target: Path | None = None,
) -> dict[str, Any]:
    """
    Returns a comprehensive structured overview of compiled DLL status,
    detected game installations, JSON config files, and active variables.
    """
    import time

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


def copy_and_install_dll(
    project_root: Path | None = None,
    custom_dll: Path | None = None,
    target_dir: Path | None = None,
) -> tuple[bool, str, list[str]]:
    """
    Copies compiled DLL to detected games / target directory and configures JSON settings.
    Returns (success: bool, message: str, installed_paths: list[str]).
    """
    root = project_root or get_project_root()
    src_dll = find_source_dll(root, custom_dll)

    if not src_dll:
        return (
            False,
            "Compiled 'isiMotor_RawUDP.dll' not found. Run 'make cross' to compile the DLL.",
            [],
        )

    targets: list[tuple[str, Path]] = []
    if target_dir:
        targets.append(("Custom Path", Path(target_dir)))
    else:
        detected = detect_game_installations()
        for game_key, dirs in detected.items():
            name = SUPPORTED_GAMES[game_key]["name"]
            for d in dirs:
                targets.append((name, d))

    if not targets:
        return (
            False,
            "No Le Mans Ultimate or rFactor 2 installations detected. Specify target directory manually.",
            [],
        )

    installed_paths: list[str] = []
    for game_name, gdir in targets:
        try:
            plugins_dir = gdir / "Plugins"
            plugins_dir.mkdir(parents=True, exist_ok=True)
            target_plugin_dll = plugins_dir / src_dll.name
            shutil.copy2(src_dll, target_plugin_dll)
            installed_paths.append(str(target_plugin_dll))

            root_dll = gdir / src_dll.name
            shutil.copy2(src_dll, root_dll)

            configure_game_json(gdir, src_dll.name)
        except Exception as e:
            return (False, f"Failed copying to {game_name} ({gdir}): {e}", installed_paths)

    msg = f"Successfully installed {src_dll.name} into {len(installed_paths)} game path(s)."
    return (True, msg, installed_paths)


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


def show_status() -> None:
    """Displays status of detected games and plugin installation."""
    logger.info("==================================================================")
    logger.info("  🔍 isiMotor Game Detection & Plugin Status")
    logger.info("==================================================================")

    detected = detect_game_installations()
    found_any = False

    for game_key, info in SUPPORTED_GAMES.items():
        dirs = detected.get(game_key, [])
        logger.info(f"\n🎮 {info['name']}:")
        if not dirs:
            logger.info("   (Not detected)")
            continue

        found_any = True
        for d in dirs:
            plugin_path = d / "Plugins" / "isiMotor_RawUDP.dll"
            is_installed = plugin_path.exists()
            status = f"✅ Installed ({plugin_path.stat().st_size:,} B)" if is_installed else "❌ Not Installed"
            logger.info(f"   • Path   : {d}")
            logger.info(f"     Status : {status}")

    if not found_any:
        logger.info("\nNo supported games detected via standard Steam libraries.")


# ── CLI Entry Point ────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="isiMotor-RawUDP Plugin Installer & Game Detector")
    parser.add_argument("--status", action="store_true", help="Display detected games and installation status")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall plugin from game directory")
    parser.add_argument("--dry-run", action="store_true", help="Simulate installation without writing files")
    parser.add_argument("--dll-path", type=Path, help="Path to custom isiMotor_RawUDP.dll")
    parser.add_argument("--target-dir", type=Path, help="Manual path to game root directory")

    args = parser.parse_args()

    if args.status:
        show_status()
        sys.exit(0)

    if args.uninstall:
        uninstall_plugin(args.target_dir)
        sys.exit(0)

    success = install_plugin(custom_dll=args.dll_path, target_dir=args.target_dir, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
