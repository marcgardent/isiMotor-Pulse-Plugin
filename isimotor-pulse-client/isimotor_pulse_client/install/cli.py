#!/usr/bin/env python3
"""
isiMotor-Pulse-Plugin — Automated Game Detector & Plugin Installer CLI.
Auto-detects Steam installations for Le Mans Ultimate and rFactor 2,
copies isiMotor_Pulse.dll to Plugins/, and configures CustomPluginVariables.JSON / Settings.JSON.

Copyright 2026 Marc GARDENT
Licensed under the Apache License, Version 2.0.
"""

import argparse
import logging
import sys
from pathlib import Path

from .dll import install_plugin, uninstall_plugin
from .steam import SUPPORTED_GAMES, detect_game_installations

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("isimotor_pulse_client.install")


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
            plugin_path = d / "Plugins" / "isiMotor_Pulse.dll"
            is_installed = plugin_path.exists()
            status = f"✅ Installed ({plugin_path.stat().st_size:,} B)" if is_installed else "❌ Not Installed"
            logger.info(f"   • Path   : {d}")
            logger.info(f"     Status : {status}")

    if not found_any:
        logger.info("\nNo supported games detected via standard Steam libraries.")


def main() -> None:
    parser = argparse.ArgumentParser(description="isiMotor-Pulse Plugin Installer & Game Detector")
    parser.add_argument("--status", action="store_true", help="Display detected games and installation status")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall plugin from game directory")
    parser.add_argument("--dry-run", action="store_true", help="Simulate installation without writing files")
    parser.add_argument("--dll-path", type=Path, help="Path to custom isiMotor_Pulse.dll")
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
