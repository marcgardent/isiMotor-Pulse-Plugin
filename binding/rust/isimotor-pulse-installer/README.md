# isimotor-pulse-installer (Rust)

Steam game detection, `CustomPluginVariables.JSON` / `Settings.JSON` writer, and a
GitHub Releases-based installer/uninstaller for the isiMotor_Pulse plugin DLL
(Le Mans Ultimate & rFactor 2). Rust port of
`isimotor-pulse-client/isimotor_pulse_client/install/*`.

Not published to crates.io - add it as a **Git dependency** pinned to a release tag:

```toml
[dependencies]
isimotor-pulse-installer = { git = "https://github.com/marcgardent/isiMotor-Pulse-Plugin", tag = "v0.6.2" }
```

## Usage

```rust
use isimotor_pulse_installer::{detect_game_installations, install_for_game, DllSource};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let games = detect_game_installations();
    if games.is_empty() {
        println!("No Le Mans Ultimate / rFactor 2 installation detected via Steam.");
        return Ok(());
    }

    for game in &games {
        println!("Found {} at {}", game.name, game.root_dir.display());

        // Downloads the isiMotor_Pulse.dll release asset tagged
        // `COMPATIBLE_PLUGIN_TAG` (this crate's own version, see "Tag
        // propagation" below) - cached locally per tag - copies it into
        // `Plugins/`, and writes CustomPluginVariables.JSON / Settings.JSON.
        let dest = install_for_game(game, DllSource::Download { tag: None })?;

        // To always fetch the newest release instead of the pinned one:
        // install_for_game(game, DllSource::Latest)?;
        println!("Installed -> {}", dest.display());

        // Or, install an already-compiled DLL from disk instead:
        // install_for_game(game, DllSource::LocalPath("./build/isiMotor_Pulse.dll".into()))?;
    }

    Ok(())
}
```

To remove the plugin from a detected installation:

```rust
use isimotor_pulse_installer::uninstall_for_game;

uninstall_for_game(&game)?;
```

## Tag propagation

`DllSource::Download { tag: None }` does **not** fetch the latest GitHub
release - it fetches the release tagged `v<this crate's Cargo.toml version>`
(exposed as `isimotor_pulse_installer::COMPATIBLE_PLUGIN_TAG`). This crate's
version is bumped in lockstep with every plugin release tag by
`make version VERSION=x.y.z` (`scripts/bump_version.py`), so pinning to it
means an integration always downloads the DLL this build of the crate was
actually written/tested against, rather than silently drifting whenever a
newer plugin release is tagged. Pass an explicit `tag: Some("vX.Y.Z")`, or
`DllSource::Latest`, to opt out of that pinning.

## Notes / known limitations

- Windows Steam-path discovery mirrors the Python reference exactly: the
  Windows Registry (`HKCU\Software\Valve\Steam\SteamPath`,
  `HKLM\SOFTWARE\WOW6432Node\Valve\Steam\InstallPath`,
  `HKLM\SOFTWARE\Valve\Steam\InstallPath`, via the Windows-only `winreg`
  dependency) is checked first, then the environment-variable
  (`ProgramFiles`, `ProgramFiles(x86)`, `ProgramW6432`) and
  `SystemDrive`-based fallback paths.
- `detect_game_installations()` strictly follows Steam's
  `libraryfolders.vdf` as the single source of truth, exactly like the
  Python implementation - it does not guess at unregistered directories.
- The GitHub Releases downloader expects the `isiMotor-Pulse-Plugin-<TAG>-Windows-x64-MinGW-w64.zip`
  asset published by `.github/workflows/release.yml` and caches the
  extracted DLL under the OS cache directory
  (`isimotor-pulse-installer/<tag>/isiMotor_Pulse.dll`), keyed by tag so a
  given release is only downloaded once.
