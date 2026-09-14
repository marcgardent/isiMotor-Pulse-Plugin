//! Downloads the compiled `isiMotor_Pulse.dll` from this repository's GitHub
//! Releases, extracting it from the `isiMotor-Pulse-Plugin-<TAG>-Windows-x64-MinGW-w64.zip`
//! asset published by `.github/workflows/release.yml`, with a local on-disk
//! cache keyed by tag so repeated installs don't re-download.

use std::path::{Path, PathBuf};

use serde::Deserialize;

use crate::InstallError;

/// GitHub repository that publishes releases containing the plugin DLL.
pub const GITHUB_OWNER: &str = "marcgardent";
pub const GITHUB_REPO: &str = "isiMotor-Pulse-Plugin";

/// Name of the DLL file inside the release zip, and the name written into
/// game `Plugins/` directories.
pub const DLL_FILE_NAME: &str = "isiMotor_Pulse.dll";

/// Release tag of the plugin DLL this build of `isimotor-pulse-installer`
/// was written/tested against, derived from this crate's own version.
///
/// The crate's `Cargo.toml` version is kept in lockstep with the plugin's
/// release tags by `make version VERSION=x.y.z` (see `scripts/bump_version.py`),
/// so `vX.Y.Z` here always names a real GitHub release. [`download_dll`]
/// defaults to this tag (rather than "latest") so an integration pulls a DLL
/// this crate was actually built to talk to, instead of silently drifting to
/// whatever gets tagged next.
pub const COMPATIBLE_PLUGIN_TAG: &str = concat!("v", env!("CARGO_PKG_VERSION"));

#[derive(Debug, Deserialize)]
struct GhReleaseAsset {
    name: String,
    browser_download_url: String,
}

#[derive(Debug, Deserialize)]
struct GhRelease {
    tag_name: String,
    assets: Vec<GhReleaseAsset>,
}

fn zip_asset_name_for_tag(tag: &str) -> String {
    format!("isiMotor-Pulse-Plugin-{tag}-Windows-x64-MinGW-w64.zip")
}

/// Directory used to cache downloaded/extracted DLLs, one subdirectory per tag.
pub fn cache_dir() -> Result<PathBuf, InstallError> {
    let base = dirs::cache_dir().ok_or(InstallError::NoCacheDir)?;
    Ok(base.join("isimotor-pulse-installer"))
}

fn cached_dll_path(tag: &str) -> Result<PathBuf, InstallError> {
    Ok(cache_dir()?.join(tag).join(DLL_FILE_NAME))
}

fn http_client() -> Result<reqwest::blocking::Client, InstallError> {
    Ok(reqwest::blocking::Client::builder()
        .user_agent("isimotor-pulse-installer")
        .build()?)
}

/// Fetches the GitHub release metadata for a given tag, or the latest
/// release when `tag` is `None`.
fn fetch_release(client: &reqwest::blocking::Client, tag: Option<&str>) -> Result<GhRelease, InstallError> {
    let url = match tag {
        Some(t) => format!("https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tags/{t}"),
        None => format!("https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"),
    };
    let resp = client.get(&url).send()?.error_for_status()?;
    Ok(resp.json::<GhRelease>()?)
}

/// Downloads (or reuses a cached) `isiMotor_Pulse.dll` for the given tag, or
/// [`COMPATIBLE_PLUGIN_TAG`] (this crate's own version) when `tag` is `None`.
/// Pass `Some("latest")`-equivalent behavior explicitly via
/// [`download_latest_dll`] if you deliberately want the newest release
/// regardless of compatibility. Returns the local path to the extracted DLL.
pub fn download_dll(tag: Option<&str>) -> Result<PathBuf, InstallError> {
    let tag = tag.unwrap_or(COMPATIBLE_PLUGIN_TAG);
    let client = http_client()?;
    let release = fetch_release(&client, Some(tag))?;
    download_dll_from_release(&client, &release)
}

/// Downloads (or reuses a cached) `isiMotor_Pulse.dll` from the latest
/// GitHub release, whatever tag that happens to be. Prefer [`download_dll`]
/// (with `tag: None`) unless you specifically want to opt out of the
/// version-pinning behavior.
pub fn download_latest_dll() -> Result<PathBuf, InstallError> {
    let client = http_client()?;
    let release = fetch_release(&client, None)?;
    download_dll_from_release(&client, &release)
}

fn download_dll_from_release(client: &reqwest::blocking::Client, release: &GhRelease) -> Result<PathBuf, InstallError> {
    let resolved_tag = release.tag_name.clone();

    let dest = cached_dll_path(&resolved_tag)?;
    if dest.is_file() {
        return Ok(dest);
    }

    let asset_name = zip_asset_name_for_tag(&resolved_tag);
    let asset = release
        .assets
        .iter()
        .find(|a| a.name == asset_name)
        .ok_or_else(|| InstallError::AssetNotFound(asset_name.clone()))?;

    let zip_bytes = client.get(&asset.browser_download_url).send()?.error_for_status()?.bytes()?;

    extract_dll_from_zip_bytes(&zip_bytes, &dest)?;
    Ok(dest)
}

/// Extracts `isiMotor_Pulse.dll` from an in-memory zip archive into `dest`.
fn extract_dll_from_zip_bytes(zip_bytes: &[u8], dest: &Path) -> Result<(), InstallError> {
    if let Some(parent) = dest.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let reader = std::io::Cursor::new(zip_bytes);
    let mut archive = zip::ZipArchive::new(reader)?;

    let mut found = false;
    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let name = file.name().to_string();
        if name == DLL_FILE_NAME || name.ends_with(&format!("/{DLL_FILE_NAME}")) {
            let mut out = std::fs::File::create(dest)?;
            std::io::copy(&mut file, &mut out)?;
            found = true;
            break;
        }
    }

    if !found {
        return Err(InstallError::AssetNotFound(DLL_FILE_NAME.to_string()));
    }
    Ok(())
}
