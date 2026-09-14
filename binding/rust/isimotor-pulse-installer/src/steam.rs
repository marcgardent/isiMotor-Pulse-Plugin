//! Steam library & isiMotor game detection.
//!
//! Locates Steam's `libraryfolders.vdf` across Windows (Registry + Env vars),
//! Linux (Native), Linux (Flatpak), Snap and Steam Deck, and resolves it into
//! installed Le Mans Ultimate / rFactor 2 game directories.
//!
//! Port of `isimotor_pulse_client/install/steam.py`.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use regex::Regex;

/// One supported game's static metadata.
#[derive(Debug, Clone, Copy)]
pub struct GameInfo {
    pub key: &'static str,
    pub name: &'static str,
    pub appid: &'static str,
    pub subpath: &'static str,
    pub exe: &'static str,
}

/// Supported games, matching `SUPPORTED_GAMES` in the Python reference.
pub const SUPPORTED_GAMES: &[GameInfo] = &[
    GameInfo {
        key: "LMU",
        name: "Le Mans Ultimate",
        appid: "2399420",
        subpath: "Le Mans Ultimate",
        exe: "Le Mans Ultimate.exe",
    },
    GameInfo {
        key: "rF2",
        name: "rFactor 2",
        appid: "365960",
        subpath: "rFactor 2",
        exe: "rFactor2.exe",
    },
];

/// A single detected game installation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GameInstall {
    /// Short key, e.g. "LMU" or "rF2".
    pub key: String,
    /// Human-readable name, e.g. "Le Mans Ultimate".
    pub name: String,
    /// Absolute path to the game's root install directory.
    pub root_dir: PathBuf,
}

/// Returns candidate paths for Steam's `libraryfolders.vdf` configuration file
/// across Windows (Registry + Env vars), Linux (Native), Linux (Flatpak), Snap
/// and Steam Deck.
pub fn get_steam_vdf_candidate_paths() -> Vec<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    #[cfg(target_os = "windows")]
    {
        windows_registry_candidates(&mut candidates);

        for env_var in ["ProgramFiles(x86)", "ProgramFiles", "ProgramW6432"] {
            if let Ok(pf) = std::env::var(env_var) {
                if !pf.is_empty() {
                    let vdf = Path::new(&pf).join("Steam").join("steamapps").join("libraryfolders.vdf");
                    push_unique(&mut candidates, vdf);
                }
            }
        }

        let sys_drive = std::env::var("SystemDrive").unwrap_or_else(|_| "C:".to_string());
        let vdf = Path::new(&format!("{sys_drive}/"))
            .join("Steam")
            .join("steamapps")
            .join("libraryfolders.vdf");
        push_unique(&mut candidates, vdf);
    }

    if let Some(home) = dirs::home_dir() {
        let linux_paths = [
            home.join(".local/share/Steam/steamapps/libraryfolders.vdf"),
            home.join(".steam/steam/steamapps/libraryfolders.vdf"),
            home.join(".steam/root/steamapps/libraryfolders.vdf"),
            home.join(".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/libraryfolders.vdf"),
            home.join(".var/app/com.valvesoftware.Steam/.steam/steam/steamapps/libraryfolders.vdf"),
            home.join("snap/steam/common/.local/share/Steam/steamapps/libraryfolders.vdf"),
        ];
        for p in linux_paths {
            push_unique(&mut candidates, p);
        }
    }

    candidates
}

fn push_unique(candidates: &mut Vec<PathBuf>, p: PathBuf) {
    if !candidates.contains(&p) {
        candidates.push(p);
    }
}

#[cfg(target_os = "windows")]
fn windows_registry_candidates(candidates: &mut Vec<PathBuf>) {
    // Mirrors the Python reference's three registry lookups, in the same
    // order, so a Steam install moved to a custom location is still found:
    //   HKCU\Software\Valve\Steam                       -> SteamPath
    //   HKLM\SOFTWARE\WOW6432Node\Valve\Steam           -> InstallPath
    //   HKLM\SOFTWARE\Valve\Steam                       -> InstallPath
    use winreg::enums::{HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE};
    use winreg::{RegKey, HKEY};

    let lookups: [(HKEY, &str, &str); 3] = [
        (HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ];

    for (hive, reg_path, val_name) in lookups {
        let root = RegKey::predef(hive);
        if let Ok(key) = root.open_subkey(reg_path) {
            if let Ok(val) = key.get_value::<String, _>(val_name) {
                if !val.is_empty() {
                    let vdf = Path::new(&val).join("steamapps").join("libraryfolders.vdf");
                    push_unique(candidates, vdf);
                }
            }
        }
    }
}

/// Parses a Steam `libraryfolders.vdf` file and extracts all registered
/// library roots. Acts as the single source of truth for Steam library
/// locations.
pub fn parse_vdf_library_paths(vdf_path: &Path) -> Vec<PathBuf> {
    let mut library_paths: Vec<PathBuf> = Vec::new();
    if !vdf_path.is_file() {
        return library_paths;
    }

    // Root Steam directory containing steamapps/libraryfolders.vdf is always a library.
    if let Some(steamapps_dir) = vdf_path.parent() {
        if let Some(root_lib) = steamapps_dir.parent() {
            if root_lib.is_dir() {
                push_unique_resolved(&mut library_paths, root_lib);
            }
        }
    }

    let content = match std::fs::read_to_string(vdf_path) {
        Ok(c) => c,
        Err(_) => return library_paths,
    };

    // Modern VDF format: "path" "/path/to/library"
    let path_re = Regex::new(r#"(?i)"path"\s+"([^"]+)""#).unwrap();
    for cap in path_re.captures_iter(&content) {
        let raw = cap[1].replace("\\\\", "\\");
        let p = PathBuf::from(raw);
        if p.is_dir() {
            push_unique_resolved(&mut library_paths, &p);
        }
    }

    // Legacy VDF format (Steam pre-2021): "1" "D:\\SteamLibrary"
    let legacy_re = Regex::new(r#""\d+"\s+"([^"]+)""#).unwrap();
    for cap in legacy_re.captures_iter(&content) {
        let raw = cap[1].replace("\\\\", "\\");
        let p = PathBuf::from(raw);
        if p.is_dir() {
            push_unique_resolved(&mut library_paths, &p);
        }
    }

    library_paths
}

fn push_unique_resolved(library_paths: &mut Vec<PathBuf>, p: &Path) {
    let resolved = std::fs::canonicalize(p).unwrap_or_else(|_| p.to_path_buf());
    if !library_paths.contains(&resolved) {
        library_paths.push(resolved);
    }
}

/// Detects all installed isiMotor / rFactor 2 / Le Mans Ultimate game
/// directories. Strictly uses Steam's `libraryfolders.vdf` as the single
/// source of truth (no guesswork against random directories).
pub fn detect_game_installations() -> Vec<GameInstall> {
    detect_game_installations_from(&get_steam_vdf_candidate_paths())
}

/// Same as [`detect_game_installations`], but takes the list of VDF
/// candidate paths explicitly (useful for tests).
pub fn detect_game_installations_from(vdf_candidates: &[PathBuf]) -> Vec<GameInstall> {
    let mut all_lib_paths: Vec<PathBuf> = Vec::new();
    for vdf in vdf_candidates {
        if vdf.is_file() {
            for lib in parse_vdf_library_paths(vdf) {
                if !all_lib_paths.contains(&lib) {
                    all_lib_paths.push(lib);
                }
            }
        }
    }

    let mut results: Vec<GameInstall> = Vec::new();
    for info in SUPPORTED_GAMES {
        for lib in &all_lib_paths {
            let game_dir = lib.join("steamapps").join("common").join(info.subpath);
            if game_dir.is_dir() && game_dir.join(info.exe).is_file() {
                let resolved = std::fs::canonicalize(&game_dir).unwrap_or(game_dir);
                let install = GameInstall {
                    key: info.key.to_string(),
                    name: info.name.to_string(),
                    root_dir: resolved,
                };
                if !results.contains(&install) {
                    results.push(install);
                }
            }
        }
    }

    results
}

/// Groups detected installations by game key, mirroring the Python
/// `dict[str, list[Path]]` return shape.
pub fn detect_game_installations_grouped() -> HashMap<String, Vec<PathBuf>> {
    let mut map: HashMap<String, Vec<PathBuf>> = HashMap::new();
    for info in SUPPORTED_GAMES {
        map.insert(info.key.to_string(), Vec::new());
    }
    for install in detect_game_installations() {
        map.entry(install.key).or_default().push(install.root_dir);
    }
    map
}
