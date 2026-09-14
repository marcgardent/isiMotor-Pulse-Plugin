//! High-level install/uninstall workflow: resolves a DLL (downloaded from
//! GitHub Releases, or a local path), copies it into a game's `Plugins/`
//! directory, and configures its JSON settings. Port of
//! `isimotor_pulse_client/install/dll.py`.

use std::path::PathBuf;

use crate::config::configure_game_json;
use crate::release::{download_dll, download_latest_dll};
use crate::steam::GameInstall;
use crate::InstallError;

/// Name of the plugin DLL as copied into `Plugins/`.
pub const PLUGIN_DLL_NAME: &str = "isiMotor_Pulse.dll";

/// Where to source the plugin DLL from when installing.
#[derive(Debug, Clone)]
pub enum DllSource {
    /// Download from this repository's GitHub Releases. `tag: None` resolves
    /// to [`crate::release::COMPATIBLE_PLUGIN_TAG`] — the release this build
    /// of the crate was versioned against — not the latest release; pass an
    /// explicit tag, or use `DllSource::Latest`, to opt out of that pinning.
    Download { tag: Option<String> },
    /// Always download the newest GitHub release, regardless of this
    /// crate's own version.
    Latest,
    /// Use an already-compiled DLL from the local filesystem.
    LocalPath(PathBuf),
}

fn resolve_dll_path(source: &DllSource) -> Result<PathBuf, InstallError> {
    match source {
        DllSource::Download { tag } => download_dll(tag.as_deref()),
        DllSource::Latest => download_latest_dll(),
        DllSource::LocalPath(p) => {
            if p.is_file() {
                Ok(p.clone())
            } else {
                Err(InstallError::DllNotFound(p.clone()))
            }
        }
    }
}

/// Installs the plugin DLL into a single game installation: copies it into
/// `Plugins/` and configures `CustomPluginVariables.JSON` / `Settings.JSON`.
pub fn install_for_game(game: &GameInstall, dll_source: DllSource) -> Result<PathBuf, InstallError> {
    let src_dll = resolve_dll_path(&dll_source)?;

    let plugins_dir = game.root_dir.join("Plugins");
    std::fs::create_dir_all(&plugins_dir)?;
    let dest = plugins_dir.join(PLUGIN_DLL_NAME);
    std::fs::copy(&src_dll, &dest)?;

    configure_game_json(&game.root_dir, PLUGIN_DLL_NAME)?;

    Ok(dest)
}

/// Removes `isiMotor_Pulse.dll` from a game installation's `Plugins/`
/// directory (and its root directory, for older installs that placed it
/// there directly). Returns the number of files removed.
pub fn uninstall_for_game(game: &GameInstall) -> Result<usize, InstallError> {
    let mut removed = 0;
    for candidate in [
        game.root_dir.join("Plugins").join(PLUGIN_DLL_NAME),
        game.root_dir.join(PLUGIN_DLL_NAME),
    ] {
        if candidate.is_file() {
            std::fs::remove_file(&candidate)?;
            removed += 1;
        }
    }
    Ok(removed)
}
