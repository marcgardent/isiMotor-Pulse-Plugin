# 🏎️ isiMotor-RawUDP-Plugin — User Notice & Configuration Guide

> **Version**: 1.0.0-RC  
> **Compatibility**: Le Mans Ultimate (LMU), rFactor 2 (rF2), isiMotor 2.5 / 3.0  
> **Architecture**: Windows x64 (MSVC / MinGW native DLL), Linux Proton / Steam Deck  

---

## 📖 1. Overview

**`isiMotor-RawUDP-Plugin`** is a high-performance, native telemetry plugin designed to stream telemetry, multi-car timing & scoring, track rules, flags, pit menu navigation, camera matrices, and weather conditions from isiMotor simulations (**Le Mans Ultimate**, **rFactor 2**) using standardized binary UDP streams (**SIMP Protocol**).

### Key Features
- **Zero Third-Party Dependencies**: Pure standalone native binary (Winsock2 sockets only).
- **Zero Dynamic Allocations in Realtime**: Zero memory allocations during active sessions (FFB 400Hz, Telemetry 100Hz+).
- **Sub-Millisecond Latency**: Designed for hardware dashboards, streaming overlays, direct-drive wheelbases, and race engineering setups.
- **Bi-Directional Input**: Control pit menu strategy, cockpit button triggers, and weather injection directly from Stream Decks, button boxes, or external tools.
- **Standard isiMotor Configuration**: Fully integrated with the game engine's native profile configuration system (`CustomPluginVariables.JSON`).

---

## 🚀 2. Installation

### Method A — Automated (Recommended)

Using Python (3.9+):
```bash
python scripts/install_plugin.py
```
The installer automatically discovers your Steam installations for **Le Mans Ultimate** and **rFactor 2** across all mounted drives (Windows registry, Linux Proton, Flatpak, Steam Deck), copies the DLL into `Plugins/`, and configures the JSON files.

To check installation status across detected games:
```bash
python scripts/install_plugin.py --status
```

---

### Method B — Manual

1. **Copy the DLL**:
   Copy `isiMotor_RawUDP.dll` into your game's `Plugins/` directory:
   - *Le Mans Ultimate*: `<SteamLibrary>\steamapps\common\Le Mans Ultimate\Plugins\isiMotor_RawUDP.dll`
   - *rFactor 2*: `<SteamLibrary>\steamapps\common\rFactor 2\Plugins\isiMotor_RawUDP.dll`

2. **Enable in `Settings.JSON`**:
   In `<GameRoot>\UserData\player\Settings.JSON`, ensure the following options are set:
   ```json
   "Enable external plugins": true,
   "Plugin Mask": 255
   ```

3. **Generate Configuration**:
   Launch the game once to automatically create the settings in `CustomPluginVariables.JSON`.

---

## ⚙️ 3. Configuration Guide (`CustomPluginVariables.JSON`)

The plugin is configured via the standard profile settings file:
`<GameRoot>\UserData\player\CustomPluginVariables.JSON`

This file is hot-reloaded by the simulation engine and can also be adjusted directly from in-game plugin menus when supported by the UI.

### Default Configuration Example

```json
{
  "isiMotor_RawUDP": {
    " Enabled": 1,
    "TargetIP": "127.0.0.1",
    "TargetPort": "5000",
    "InboundControl": "Enabled",
    "InboundPort": "5001",
    "TelemetryRate": "unlimited",
    "CompactScoringRate": "unlimited",
    "FullScoringRate": "5Hz",
    "TrackRulesRate": "3Hz",
    "PitMenuRate": "100Hz",
    "WeatherRate": "1Hz",
    "ExtendedStateRate": "5Hz",
    "ForceFeedbackRate": "unlimited",
    "GraphicsRate": "60Hz",
    "SystemEvents": "Enabled",
    "UnsubscribedBuffersMask": "0"
  }
}
```

---

### 📋 Detailed Configuration Parameters

| Parameter | Default Value | Accepted Values & Syntax | Description |
| :--- | :---: | :--- | :--- |
| **` Enabled`** | `1` | `1` (enabled), `0` (disabled) | Master plugin toggle managed by the game host |
| **`TargetIP`** | `"127.0.0.1"` | `"127.0.0.1"`, `"255.255.255.255"`, `"239.255.0.1"`, Any valid IPv4 address (e.g. `"192.168.1.50"`) | Destination IPv4 endpoint (Unicast, Broadcast, Multicast) |
| **`TargetPort`** | `"5000"` | `"5000"`, `"5002"`, `"9000"`, `"20777"` (SimHub), or any valid UDP port | Outgoing telemetry UDP port |
| **`InboundControl`**| `"Enabled"` | `"Enabled"`, `"Disabled"`, `"on"`, `"off"`, `"1"`, `"0"` | Inbound UDP control receiver (Pit Menu, HW commands, Weather) |
| **`InboundPort`** | `"5001"` | `"5001"`, `"5003"`, `"9001"`, or any valid UDP port | Listening port for external commands |
| **`TelemetryRate`** | `"unlimited"` | `"off"`, `"unlimited"` (~90-100Hz+), `"100Hz"`, `"60Hz"`, `"30Hz"`, `"20Hz"`, `"10Hz"` | High-frequency player telemetry stream (1888 bytes) |
| **`CompactScoringRate`** | `"unlimited"` | `"off"`, `"unlimited"`, `"10Hz"`, `"5Hz"`, `"2Hz"`, `"1Hz"` | Lightweight single-car scoring stream (168 bytes) |
| **`FullScoringRate`** | `"5Hz"` | `"off"`, `"unlimited"`, `"10Hz"`, `"5Hz"`, `"2Hz"`, `"1Hz"` | Full grid multi-vehicle scoring up to 128 cars |
| **`TrackRulesRate`** | `"3Hz"` | `"off"`, `"unlimited"`, `"5Hz"`, `"3Hz"`, `"1Hz"` | Track flags, Safety Car / FCY, and caution delta orders |
| **`PitMenuRate`** | `"100Hz"` | `"off"`, `"unlimited"`, `"100Hz"`, `"60Hz"`, `"30Hz"` | Pit menu strategy navigation state stream |
| **`WeatherRate`** | `"1Hz"` | `"off"`, `"unlimited"`, `"2Hz"`, `"1Hz"` | Ambient temperatures, rainfall, cloudiness, and wind |
| **`ExtendedStateRate`**| `"5Hz"` | `"off"`, `"unlimited"`, `"10Hz"`, `"5Hz"`, `"2Hz"`, `"1Hz"` | Driving aids, physics multipliers & accumulated impact damage |
| **`ForceFeedbackRate`**| `"unlimited"` | `"off"`, `"unlimited"` (400Hz), `"200Hz"`, `"100Hz"`, `"60Hz"` | Steering shaft FFB torque output |
| **`GraphicsRate`** | `"60Hz"` | `"off"`, `"unlimited"`, `"100Hz"`, `"60Hz"`, `"30Hz"` | Camera world position, orientation matrix & ambient lighting |
| **`SystemEvents`** | `"Enabled"` | `"Enabled"`, `"Disabled"`, `"on"`, `"off"` | State transition notifications (Garage, Realtime, Session) |
| **`UnsubscribedBuffersMask`** | `"0"` | `"0"` (all streams enabled), or bitmask integer (e.g. `"1"` to cut telemetry) | Compatibility buffer mask |

---

## 📡 4. Network Topologies & Multicast

### Scenario 1 — Dashboard / SimHub / Overlay on the same PC
- `TargetIP`: `"127.0.0.1"`
- `TargetPort`: `"5000"`
- **Best For**: Zero network overhead, no firewall setup required.

### Scenario 2 — Multi-Device Setup (Tablets, Dashboards, Secondary PC)
- `TargetIP`: `"255.255.255.255"` (Broadcast) or `"239.255.0.1"` (Multicast) or Direct IP (e.g. `"192.168.1.42"`)
- `TargetPort`: `"5000"`
- **Benefit**: Infinite listeners can tap into the telemetry stream simultaneously without increasing game CPU overhead.
- **Windows Firewall**: Allow **UDP port 5000 Outbound** and **UDP port 5001 Inbound**.

---

## 🎮 5. Bi-Directional Input (Inbound UDP)

The plugin listens on **UDP port 5001** (configurable via `InboundPort`) to receive hardware and pit menu commands without requiring keyboard emulations:

### Supported Pit Menu Actions
- `"PitMenuUp"`: Navigate up in current category choices
- `"PitMenuDown"`: Navigate down in current choices
- `"PitMenuPrevCat"`: Switch to previous category (Tires, Fuel, Damage...)
- `"PitMenuNextCat"`: Switch to next category
- `"PitMenuSelect"`: Confirm / toggle selection

### Cockpit & Weather Injection
- Standard cockpit controls: `"TCIncrease"`, `"TCDecrease"`, `"ABSIncrease"`, `"BrakeBiasForward"`, etc.
- Dynamic Weather Injection (Packet Type 101): Directly manipulate rain, air/track temperatures, and cloudiness in private practice/testing sessions.

---

## 🔍 6. Diagnostics & Troubleshooting

1. **No telemetry received**:
   - Check `<GameRoot>\UserData\player\Settings.JSON` has `"Enable external plugins": true`.
   - Check `<GameRoot>\UserData\player\CustomPluginVariables.JSON` has `" Enabled": 1`.
   - Ensure UDP port 5000 is not blocked or bound by another application.
2. **Live Protocol Inspection**:
   - Run the included TUI sniffer tool:
     ```bash
     python benchmark/sniffer.py
     ```
   - Or test with the Python client SDK:
     ```python
     from isimotor_rawudp_client import IsiMotorClient

     client = IsiMotorClient(host="127.0.0.1", port=5000)
     client.on_telemetry = lambda t: print(f"RPM: {t.engine_rpm:.0f} | Speed: {t.speed_kmh:.1f} km/h")
     client.start()
     ```
