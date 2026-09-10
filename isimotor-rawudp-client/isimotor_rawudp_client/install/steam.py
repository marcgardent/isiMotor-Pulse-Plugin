"""
Steam library & isiMotor game detection.
Locates Steam's libraryfolders.vdf across Windows (Registry + Env vars),
Linux (Native), Linux (Flatpak), Snap and Steam Deck, and resolves it into
installed Le Mans Ultimate / rFactor 2 game directories.
"""

import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger("isimotor_rawudp_client.install")


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
    """
    Parses a Steam libraryfolders.vdf file and extracts all registered library roots.
    Acts as the single source of truth for Steam library locations.
    """
    library_paths: list[Path] = []
    if not vdf_path.exists() or not vdf_path.is_file():
        return library_paths

    # Root Steam directory containing steamapps/libraryfolders.vdf is always a library
    root_lib = vdf_path.parent.parent
    if root_lib.exists() and root_lib.is_dir():
        try:
            resolved_root = root_lib.resolve()
            if resolved_root not in library_paths:
                library_paths.append(resolved_root)
        except Exception:
            if root_lib not in library_paths:
                library_paths.append(root_lib)

    try:
        content = vdf_path.read_text(encoding="utf-8", errors="ignore")
        # Modern VDF format: "path" "/path/to/library"
        matches = re.findall(r'"path"\s+"([^"]+)"', content, flags=re.IGNORECASE)
        for raw_path in matches:
            cleaned_path = raw_path.replace("\\\\", "\\")
            p = Path(cleaned_path)
            if p.exists() and p.is_dir():
                try:
                    resolved = p.resolve()
                except Exception:
                    resolved = p
                if resolved not in library_paths:
                    library_paths.append(resolved)

        # Legacy VDF format (Steam pre-2021): "1" "D:\\SteamLibrary"
        legacy_matches = re.findall(r'"\d+"\s+"([^"]+)"', content)
        for raw_path in legacy_matches:
            cleaned_path = raw_path.replace("\\\\", "\\")
            p = Path(cleaned_path)
            if p.exists() and p.is_dir():
                try:
                    resolved = p.resolve()
                except Exception:
                    resolved = p
                if resolved not in library_paths:
                    library_paths.append(resolved)
    except Exception as e:
        logger.warning(f"Warning reading VDF {vdf_path}: {e}")

    return library_paths


# ── Game Detection ─────────────────────────────────────────────────────────────

SUPPORTED_GAMES = {
    "LMU": {
        "name": "Le Mans Ultimate",
        "appid": "2399420",
        "subpath": "Le Mans Ultimate",
        "exe": "Le Mans Ultimate.exe",
    },
    "rF2": {
        "name": "rFactor 2",
        "appid": "365960",
        "subpath": "rFactor 2",
        "exe": "rFactor2.exe",
    },
}


def detect_game_installations() -> dict[str, list[Path]]:
    """
    Detects all installed isiMotor / rFactor 2 / Le Mans Ultimate game directories.
    Strictly uses Steam's libraryfolders.vdf as the single source of truth.
    """
    results: dict[str, list[Path]] = {"LMU": [], "rF2": []}
    vdf_candidates = get_steam_vdf_candidate_paths()
    all_lib_paths: list[Path] = []

    for vdf in vdf_candidates:
        if vdf.exists() and vdf.is_file():
            for lib in parse_vdf_library_paths(vdf):
                if lib not in all_lib_paths:
                    all_lib_paths.append(lib)

    for game_key, info in SUPPORTED_GAMES.items():
        found = results[game_key]
        for lib in all_lib_paths:
            game_dir = lib / "steamapps" / "common" / info["subpath"]
            if game_dir.exists() and (game_dir / info["exe"]).exists():
                try:
                    resolved_dir = game_dir.resolve()
                except Exception:
                    resolved_dir = game_dir
                if resolved_dir not in found:
                    found.append(resolved_dir)

    return results
