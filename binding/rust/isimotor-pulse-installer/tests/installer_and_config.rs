//! Port of `tests/test_installer_and_config.py`'s config/VDF cases.

use serde_json::{json, Map, Value};
use tempfile::tempdir;

use isimotor_pulse_installer::{
    configure_game_json, default_plugin_variables, parse_vdf_library_paths, read_plugin_json_variables,
    write_plugin_json_variables,
};

#[test]
fn default_plugin_variables_completeness() {
    let required_keys = [
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
    let defaults = default_plugin_variables();
    for key in required_keys {
        assert!(defaults.contains_key(key), "Missing key in default variables: {key}");
    }
}

#[test]
fn configure_game_json_creates_files() {
    let test_dir = tempdir().unwrap();
    let game_dir = test_dir.path().join("Game");
    std::fs::create_dir_all(&game_dir).unwrap();

    let success = configure_game_json(&game_dir, "isiMotor_Pulse.dll").unwrap();
    assert!(success);

    let json_path = game_dir.join("UserData").join("player").join("CustomPluginVariables.JSON");
    assert!(json_path.is_file(), "CustomPluginVariables.JSON was not created");

    let data: Value = serde_json::from_str(&std::fs::read_to_string(&json_path).unwrap()).unwrap();
    let obj = data.as_object().unwrap();
    assert!(obj.contains_key("isiMotor_Pulse.dll"));
    assert!(!obj.contains_key("isiMotor_Pulse"));
    assert!(!obj.contains_key("isiMotor-Pulse"));

    let entry = obj["isiMotor_Pulse.dll"].as_object().unwrap();
    assert_eq!(entry[" Enabled"], json!(1));
    assert_eq!(entry["TcpHost"], json!("127.0.0.1"));
    assert_eq!(entry["TcpBasePort"], json!("5000"));
    assert_eq!(entry["InboundControl"], json!("Enabled"));
    assert_eq!(entry["PlayerTelemetryRate"], json!("unlimited"));
    assert_eq!(entry["OpponentTelemetryRate"], json!("off"));
    assert_eq!(entry["FullScoringRate"], json!("5Hz"));
    assert_eq!(entry["WeatherRate"], json!("1Hz"));
    assert_eq!(entry["ForceFeedbackRate"], json!("unlimited"));
}

#[test]
fn configure_game_json_preserves_customizations() {
    let test_dir = tempdir().unwrap();
    let game_dir = test_dir.path().join("Game");
    let player_dir = game_dir.join("UserData").join("player");
    std::fs::create_dir_all(&player_dir).unwrap();

    let existing = json!({
        "isiMotor_Pulse": {
            " Enabled": 1,
            "TcpHost": "192.168.1.20",
            "TcpBasePort": "9000",
            "TelemetryRate": "60Hz",
        }
    });
    let json_path = player_dir.join("CustomPluginVariables.JSON");
    std::fs::write(&json_path, serde_json::to_string(&existing).unwrap()).unwrap();

    let success = configure_game_json(&game_dir, "isiMotor_Pulse.dll").unwrap();
    assert!(success);

    let data: Value = serde_json::from_str(&std::fs::read_to_string(&json_path).unwrap()).unwrap();
    let obj = data.as_object().unwrap();
    assert!(obj.contains_key("isiMotor_Pulse.dll"));
    assert!(!obj.contains_key("isiMotor_Pulse"));

    let entry = obj["isiMotor_Pulse.dll"].as_object().unwrap();
    assert_eq!(entry["TcpHost"], json!("192.168.1.20"));
    assert_eq!(entry["TcpBasePort"], json!("9000"));
    assert_eq!(entry["TelemetryRate"], json!("60Hz"));
    assert_eq!(entry["InboundControl"], json!("Enabled"));
    assert_eq!(entry["FullScoringRate"], json!("5Hz"));
    assert_eq!(entry["WeatherRate"], json!("1Hz"));
}

#[test]
fn write_and_read_plugin_variables_roundtrip() {
    let test_dir = tempdir().unwrap();

    let mut custom_vars: Map<String, Value> = default_plugin_variables();
    custom_vars.insert("TcpHost".to_string(), json!("10.0.0.99"));
    custom_vars.insert("TcpBasePort".to_string(), json!("5555"));
    custom_vars.insert("TelemetryRate".to_string(), json!("60Hz"));

    let updated = write_plugin_json_variables(test_dir.path(), &custom_vars, "isiMotor_Pulse.dll").unwrap();
    assert!(!updated.is_empty());

    let saved_json = test_dir.path().join("UserData").join("player").join("CustomPluginVariables.JSON");
    assert!(saved_json.is_file());

    let read_back = read_plugin_json_variables(&saved_json, "isiMotor_Pulse.dll");
    assert_eq!(read_back["TcpHost"], json!("10.0.0.99"));
    assert_eq!(read_back["TcpBasePort"], json!("5555"));
    assert_eq!(read_back["TelemetryRate"], json!("60Hz"));
}

#[test]
fn read_plugin_json_variables_missing_file_returns_defaults() {
    let test_dir = tempdir().unwrap();
    let non_existent = test_dir.path().join("does_not_exist.json");
    let defaults = read_plugin_json_variables(&non_existent, "isiMotor_Pulse.dll");
    assert_eq!(defaults["TcpHost"], json!("127.0.0.1"));
    assert_eq!(defaults["TcpBasePort"], json!("5000"));
}

#[test]
fn parse_vdf_library_paths_modern_and_legacy() {
    let test_dir = tempdir().unwrap();
    let steam_root = test_dir.path().join("SteamRoot");
    let secondary_lib = test_dir.path().join("SecondaryLib");
    let legacy_lib = test_dir.path().join("LegacyLib");
    std::fs::create_dir_all(&steam_root).unwrap();
    std::fs::create_dir_all(&secondary_lib).unwrap();
    std::fs::create_dir_all(&legacy_lib).unwrap();

    let vdf_dir = steam_root.join("steamapps");
    std::fs::create_dir_all(&vdf_dir).unwrap();
    let vdf_file = vdf_dir.join("libraryfolders.vdf");

    let content = format!(
        r#""libraryfolders"
{{
    "0"
    {{
        "path"    "{}"
        "label"   ""
        "apps"
        {{
            "2399420"    "10000"
        }}
    }}
    "1"
    {{
        "path"    "{}"
        "apps"
        {{
            "365960"    "20000"
        }}
    }}
    "2"    "{}"
}}"#,
        steam_root.display(),
        secondary_lib.display(),
        legacy_lib.display()
    );
    std::fs::write(&vdf_file, content).unwrap();

    let parsed = parse_vdf_library_paths(&vdf_file);
    let parsed_resolved: Vec<_> = parsed.iter().map(|p| std::fs::canonicalize(p).unwrap()).collect();

    assert!(parsed_resolved.contains(&std::fs::canonicalize(&steam_root).unwrap()));
    assert!(parsed_resolved.contains(&std::fs::canonicalize(&secondary_lib).unwrap()));
    assert!(parsed_resolved.contains(&std::fs::canonicalize(&legacy_lib).unwrap()));
}

#[test]
fn detect_game_installations_uses_vdf_as_single_source_of_truth() {
    use isimotor_pulse_installer::detect_game_installations_from;

    let test_dir = tempdir().unwrap();
    let steam_root = test_dir.path().join("Steam");
    std::fs::create_dir_all(&steam_root).unwrap();
    let vdf_dir = steam_root.join("steamapps");
    std::fs::create_dir_all(&vdf_dir).unwrap();
    let vdf_file = vdf_dir.join("libraryfolders.vdf");

    // 1. Registered Steam library containing LMU.
    let lmu_dir = steam_root.join("steamapps").join("common").join("Le Mans Ultimate");
    std::fs::create_dir_all(&lmu_dir).unwrap();
    std::fs::write(lmu_dir.join("Le Mans Ultimate.exe"), b"MZ_MOCK_EXE").unwrap();

    // 2. Unregistered random folder containing rFactor 2.
    let fake_random_dir = test_dir.path().join("RandomFolder").join("steamapps").join("common").join("rFactor 2");
    std::fs::create_dir_all(&fake_random_dir).unwrap();
    std::fs::write(fake_random_dir.join("rFactor2.exe"), b"MZ_MOCK_EXE").unwrap();

    let content = format!(
        r#""libraryfolders"
{{
    "0"
    {{
        "path"    "{}"
    }}
}}"#,
        steam_root.display()
    );
    std::fs::write(&vdf_file, content).unwrap();

    let detected = detect_game_installations_from(&[vdf_file]);

    let lmu: Vec<_> = detected.iter().filter(|g| g.key == "LMU").collect();
    assert_eq!(lmu.len(), 1);
    assert_eq!(lmu[0].root_dir, std::fs::canonicalize(&lmu_dir).unwrap());

    let rf2: Vec<_> = detected.iter().filter(|g| g.key == "rF2").collect();
    assert_eq!(rf2.len(), 0, "unregistered directory must not be detected");
}
