//! JSON configuration management for the isiMotor_Pulse plugin.
//!
//! Reads and writes `CustomPluginVariables.JSON` / `Settings.JSON` in a
//! game's `UserData` directory. Port of
//! `isimotor_pulse_client/install/config.py`.

use std::path::Path;

use serde_json::{json, Map, Value};

use crate::InstallError;

/// Default configuration variables matching InternalsPluginV07 CustomVariable
/// definitions (human-readable string values), mirroring
/// `DEFAULT_PLUGIN_VARIABLES` in the Python reference.
pub fn default_plugin_variables() -> Map<String, Value> {
    let mut m = Map::new();
    m.insert(" Enabled".to_string(), json!(1));
    m.insert("EnableLogging".to_string(), json!("Disabled"));
    m.insert("TcpHost".to_string(), json!("127.0.0.1"));
    m.insert("TcpBasePort".to_string(), json!("5000"));
    m.insert("InboundControl".to_string(), json!("Enabled"));
    m.insert("InboundTcpHost".to_string(), json!("127.0.0.1"));
    m.insert("InboundTcpPort".to_string(), json!("5101"));
    m.insert("PlayerTelemetryRate".to_string(), json!("unlimited"));
    m.insert("OpponentTelemetryRate".to_string(), json!("off"));
    m.insert("CompactScoringRate".to_string(), json!("10Hz"));
    m.insert("FullScoringRate".to_string(), json!("5Hz"));
    m.insert("WeatherRate".to_string(), json!("1Hz"));
    m.insert("ExtendedStateRate".to_string(), json!("5Hz"));
    m.insert("ForceFeedbackRate".to_string(), json!("unlimited"));
    m.insert("GraphicsRate".to_string(), json!("60Hz"));
    m.insert("SystemEvents".to_string(), json!("Enabled"));
    m.insert("UnsubscribedBuffersMask".to_string(), json!("0"));
    m
}

const REQUIRED_KEYS: &[&str] = &[
    " Enabled",
    "TcpHost",
    "TcpBasePort",
    "InboundControl",
    "InboundTcpPort",
    "PlayerTelemetryRate",
    "OpponentTelemetryRate",
    "CompactScoringRate",
    "FullScoringRate",
    "WeatherRate",
    "ExtendedStateRate",
    "ForceFeedbackRate",
    "GraphicsRate",
    "SystemEvents",
    "UnsubscribedBuffersMask",
];

/// Sanity check exposed mostly for tests: all `REQUIRED_KEYS` are present.
pub fn default_plugin_variables_are_complete() -> bool {
    let defaults = default_plugin_variables();
    REQUIRED_KEYS.iter().all(|k| defaults.contains_key(*k))
}

fn read_json_object(path: &Path) -> Map<String, Value> {
    match std::fs::read_to_string(path) {
        Ok(content) => {
            let trimmed = content.trim();
            if trimmed.is_empty() {
                Map::new()
            } else {
                match serde_json::from_str::<Value>(trimmed) {
                    Ok(Value::Object(m)) => m,
                    _ => Map::new(),
                }
            }
        }
        Err(_) => Map::new(),
    }
}

fn dll_key_and_aliases(plugin_dll_name: &str) -> (String, String, String) {
    let dll_key = if plugin_dll_name.to_lowercase().ends_with(".dll") {
        plugin_dll_name.to_string()
    } else {
        format!("{plugin_dll_name}.dll")
    };
    let base_name = dll_key.trim_end_matches(".dll").to_string();
    let alt_name = base_name.replace('_', "-");
    (dll_key, base_name, alt_name)
}

/// Configures `CustomPluginVariables.JSON` and `Settings.JSON` in a game's
/// `UserData` directory. Enables external plugins and registers the DLL with
/// full standard default values, merged over any existing customizations.
pub fn configure_game_json(game_dir: &Path, plugin_dll_name: &str) -> Result<bool, InstallError> {
    let mut success = true;
    let (dll_key, base_name, alt_name) = dll_key_and_aliases(plugin_dll_name);

    let json_targets = [
        game_dir.join("UserData").join("player").join("CustomPluginVariables.JSON"),
        game_dir.join("UserData").join("CustomPluginVariables.JSON"),
    ];

    for jpath in &json_targets {
        if let Some(parent) = jpath.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let mut data = read_json_object(jpath);

        let mut merged = default_plugin_variables();
        for k in [&dll_key, &base_name, &alt_name] {
            if let Some(Value::Object(existing)) = data.get(k) {
                for (ek, ev) in existing {
                    merged.insert(ek.clone(), ev.clone());
                }
            }
        }

        data.remove(&base_name);
        data.remove(&alt_name);
        data.insert(dll_key.clone(), Value::Object(merged));

        std::fs::write(jpath, serde_json::to_string_pretty(&Value::Object(data))?)?;
    }

    let settings_targets = [
        game_dir.join("UserData").join("player").join("Settings.JSON"),
        game_dir.join("UserData").join("Settings.JSON"),
    ];
    for spath in &settings_targets {
        if spath.is_file() {
            match std::fs::read_to_string(spath) {
                Ok(content) => {
                    let trimmed = content.trim();
                    let parsed: Value = if trimmed.is_empty() {
                        json!({})
                    } else {
                        serde_json::from_str(trimmed).unwrap_or_else(|_| json!({}))
                    };
                    if let Value::Object(mut sdata) = parsed {
                        {
                            let game_opts = sdata
                                .entry("Game Options".to_string())
                                .or_insert_with(|| Value::Object(Map::new()));
                            if let Value::Object(go) = game_opts {
                                go.insert("Enable external plugins".to_string(), json!(true));
                                go.insert("Plugin Mask".to_string(), json!(255));
                            }
                        }
                        sdata.insert("Enable external plugins".to_string(), json!(true));
                        sdata.insert("Plugin Mask".to_string(), json!(255));
                        std::fs::write(spath, serde_json::to_string_pretty(&Value::Object(sdata))?)?;
                    }
                }
                Err(e) => {
                    success = false;
                    let _ = e;
                }
            }
        }
    }

    Ok(success)
}

/// Reads and parses `CustomPluginVariables.JSON` for isiMotor_Pulse
/// variables, falling back to defaults for any missing key.
pub fn read_plugin_json_variables(json_path: &Path, plugin_name: &str) -> Map<String, Value> {
    let (dll_key, base_name, alt_name) = dll_key_and_aliases(plugin_name);
    let mut result = default_plugin_variables();

    if !json_path.is_file() {
        return result;
    }

    let data = read_json_object(json_path);
    for k in [&dll_key, &base_name, &alt_name] {
        if let Some(Value::Object(existing)) = data.get(k) {
            for (ek, ev) in existing {
                result.insert(ek.clone(), ev.clone());
            }
            break;
        }
    }
    result
}

/// Writes or updates isiMotor_Pulse configuration variables inside
/// `CustomPluginVariables.JSON`, and ensures `Settings.JSON` has external
/// plugins enabled. Returns the list of updated `CustomPluginVariables.JSON`
/// paths.
pub fn write_plugin_json_variables(
    game_dir: &Path,
    variables: &Map<String, Value>,
    plugin_dll_name: &str,
) -> Result<Vec<String>, InstallError> {
    let (dll_key, base_name, alt_name) = dll_key_and_aliases(plugin_dll_name);

    let json_targets = [
        game_dir.join("UserData").join("player").join("CustomPluginVariables.JSON"),
        game_dir.join("UserData").join("CustomPluginVariables.JSON"),
    ];

    let mut updated_files = Vec::new();
    for jpath in &json_targets {
        if let Some(parent) = jpath.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let mut data = read_json_object(jpath);

        let mut merged = default_plugin_variables();
        for k in [&dll_key, &base_name, &alt_name] {
            if let Some(Value::Object(existing)) = data.get(k) {
                for (ek, ev) in existing {
                    merged.insert(ek.clone(), ev.clone());
                }
            }
        }
        for (k, v) in variables {
            merged.insert(k.clone(), v.clone());
        }

        if let Some(enabled) = merged.get(" Enabled").cloned() {
            let as_int = match enabled {
                Value::Number(n) => n.as_i64().unwrap_or(1),
                Value::String(s) => s.parse::<i64>().unwrap_or(1),
                Value::Bool(b) => i64::from(b),
                _ => 1,
            };
            merged.insert(" Enabled".to_string(), json!(as_int));
        }

        data.remove(&base_name);
        data.remove(&alt_name);
        data.insert(dll_key.clone(), Value::Object(merged));

        std::fs::write(jpath, serde_json::to_string_pretty(&Value::Object(data))?)?;
        updated_files.push(jpath.display().to_string());
    }

    let settings_targets = [
        game_dir.join("UserData").join("player").join("Settings.JSON"),
        game_dir.join("UserData").join("Settings.JSON"),
    ];
    for spath in &settings_targets {
        if spath.is_file() {
            if let Ok(content) = std::fs::read_to_string(spath) {
                let trimmed = content.trim();
                let parsed: Value = if trimmed.is_empty() {
                    json!({})
                } else {
                    serde_json::from_str(trimmed).unwrap_or_else(|_| json!({}))
                };
                if let Value::Object(mut sdata) = parsed {
                    sdata.insert("Enable external plugins".to_string(), json!(true));
                    sdata.insert("Plugin Mask".to_string(), json!(255));
                    let _ = std::fs::write(spath, serde_json::to_string_pretty(&Value::Object(sdata))?);
                }
            }
        }
    }

    Ok(updated_files)
}
