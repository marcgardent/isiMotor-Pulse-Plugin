//! Rust port of `isimotor_pulse_client/install/*`: Steam game detection,
//! `CustomPluginVariables.JSON` / `Settings.JSON` configuration, and a
//! GitHub Releases-based installer/uninstaller for the isiMotor_Pulse
//! plugin DLL.

pub mod config;
pub mod install;
pub mod release;
pub mod steam;

pub use config::{
    configure_game_json, default_plugin_variables, read_plugin_json_variables, write_plugin_json_variables,
};
pub use install::{install_for_game, uninstall_for_game, DllSource, PLUGIN_DLL_NAME};
pub use release::{download_dll, download_latest_dll, COMPATIBLE_PLUGIN_TAG};
pub use steam::{
    detect_game_installations, detect_game_installations_from, detect_game_installations_grouped,
    get_steam_vdf_candidate_paths, parse_vdf_library_paths, GameInfo, GameInstall, SUPPORTED_GAMES,
};

/// Errors produced by this crate's installer, configuration and release
/// download operations.
#[derive(Debug, thiserror::Error)]
pub enum InstallError {
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    #[error("zip error: {0}")]
    Zip(#[from] zip::result::ZipError),

    #[error("could not determine a user cache directory")]
    NoCacheDir,

    #[error("asset '{0}' not found in the release")]
    AssetNotFound(String),

    #[error("DLL not found at {0}")]
    DllNotFound(std::path::PathBuf),
}
