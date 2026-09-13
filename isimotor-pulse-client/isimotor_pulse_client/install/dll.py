"""
DLL resolution and installation workflow for the isiMotor_Pulse plugin.
Locates the compiled DLL (bundled resource, PyInstaller bundle, or local
build folders), copies it into detected game installations, and configures
their JSON settings.
"""

import logging
import shutil
import sys
from pathlib import Path

from .config import configure_game_json
from .steam import SUPPORTED_GAMES, detect_game_installations

logger = logging.getLogger("isimotor_pulse_client.install")


# ── DLL & Project Path Resolution ──────────────────────────────────────────────


def get_project_root() -> Path:
    """Returns the root path of the isiMotor-Pulse-Plugin repository."""
    current = Path(__file__).resolve()
    for parent in [
        current.parent,
        current.parent.parent,
        current.parent.parent.parent,
        current.parent.parent.parent.parent,
    ]:
        if (parent / "isimotor-pulse-plugin").exists() or (parent / "isimotor-pulse-client").exists():
            return parent
    return current.parent.parent.parent.parent


def find_source_dll(project_root: Path | None = None, custom_dll_path: Path | None = None) -> Path | None:
    """Finds the compiled isiMotor_Pulse.dll binary across bundled resources and build paths."""
    if custom_dll_path and custom_dll_path.exists() and custom_dll_path.is_file():
        return custom_dll_path

    # 1. Bundled Resources (Briefcase / Standalone package data)
    pkg_dir = Path(__file__).resolve().parent.parent
    bundled_candidates = [
        pkg_dir / "resources" / "isiMotor_Pulse.dll",
        pkg_dir.parent / "resources" / "isiMotor_Pulse.dll",
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        meipass_path = Path(meipass)
        bundled_candidates.append(meipass_path / "resources" / "isiMotor_Pulse.dll")
        bundled_candidates.append(meipass_path / "isiMotor_Pulse.dll")

    for cand in bundled_candidates:
        if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
            return cand

    # 2. Local workspace and build folders
    root = project_root or get_project_root()
    candidates = [
        root / "build" / "isiMotor_Pulse.dll",
        root / "build" / "isimotor-pulse-plugin" / "isiMotor_Pulse.dll",
        root / "bin" / "isiMotor_Pulse.dll",
        root / "isimotor-pulse-plugin" / "bin" / "isiMotor_Pulse.dll",
        root / "isimotor-pulse-plugin" / "build" / "isiMotor_Pulse.dll",
        root / "isiMotor_Pulse.dll",
        root / "build" / "Release" / "isiMotor_Pulse.dll",
        root / "bin" / "Release" / "isiMotor_Pulse.dll",
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file() and cand.stat().st_size > 0:
            return cand
    return None


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
        logger.error("❌ Error: Compiled 'isiMotor_Pulse.dll' not found.")
        logger.error("   Run 'make cross' (or 'make build') to compile the DLL before installing.")
        return False

    logger.info("==================================================================")
    logger.info("  🏎️  isiMotor-Pulse-Plugin — Installer")
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
        logger.warning('   python -m isimotor_pulse_client.install.cli --target-dir "/path/to/game"')
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
    """Removes isiMotor_Pulse.dll from detected game installations."""
    logger.info("==================================================================")
    logger.info("  🗑️  isiMotor-Pulse-Plugin — Uninstaller")
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
        for dll_path in [gdir / "Plugins" / "isiMotor_Pulse.dll", gdir / "isiMotor_Pulse.dll"]:
            if dll_path.exists():
                try:
                    dll_path.unlink()
                    logger.info(f"  ✓ Removed: {dll_path}")
                    removed += 1
                except Exception as e:
                    logger.error(f"  ✗ Could not remove {dll_path}: {e}")

    logger.info(f"\n✨ Uninstallation complete ({removed} file(s) removed).")
    return True


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
            "Compiled 'isiMotor_Pulse.dll' not found. Run 'make cross' to compile the DLL.",
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
