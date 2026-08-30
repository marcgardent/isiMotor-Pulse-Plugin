# 🏎️ isiMotor-RawUDP-Plugin — User Guide & Configuration Manual

> **Version**: 1.0.0  
> **Compatibility**: Le Mans Ultimate (LMU), rFactor 2 (rF2), isiMotor 2.5 / 3.0  
> **Architecture**: Windows x64 (Universal MinGW native DLL), Linux Proton / Steam Deck  

---

## 📖 1. Overview & Architecture

**`isiMotor-RawUDP-Plugin`** is a high-performance, ultra-low latency native telemetry and scoring plugin for isiMotor simulations (**Le Mans Ultimate**, **rFactor 2**). It streams native binary UDP packets (**SIMP Protocol**) to external applications, hardware dashboards, sim-rig telemetry analyzers, stream overlays, and remote engineering stations with sub-microsecond overhead.

### 🌟 Key Highlights
- **Single Universal Binary (`isiMotor_RawUDP.dll`)**: Runs out-of-the-box on native Windows 10/11 and Linux Proton / Steam Deck without any background daemon or Wine bridges.
- **Zero Third-Party Dependencies**: Pure standalone binary interacting exclusively with the Windows Winsock2 API.
- **Sub-Microsecond Latency (<0.001 ms)**: Zero heap memory allocations during live driving sessions.
- **10 Telemetry & Control Channels**: Supports high-rate vehicle dynamics (60–100Hz+), Force Feedback (400Hz), Compact and Full-Grid Scoring (up to 128 cars), Track Rules/Flags, Pit Strategy Menu, Weather/Environment, Driving Aids/Damage, Camera/Graphics, and Game Session Events.
- **Bi-Directional Inbound Control**: Direct UDP injection for pit menu navigation, cockpit button inputs, and session weather parameters.

---

## 🚀 2. Installation & Setup

### Method 1 — Standalone Manager (AppImage / Exe) — [Recommended]

The simplest and most complete way to install, configure, and monitor the plugin is using the standalone **isiMotor RawUDP Manager** application. It requires **no installation, no Python environment, and no external dependencies**.

#### 📥 Download
Download the latest pre-built standalone executable from the [GitHub Releases](https://github.com/marcgardent/isiMotor-RawUDP-Plugin/releases) page:
- **Windows (x64)**: `isiMotor_RawUDP_Manager.exe`
- **Linux / Steam Deck**: `isiMotor-RawUDP-Manager-x86_64.AppImage`

#### 🎮 One-Click Installation & Configuration
1. **Launch the Manager**:
   - On **Windows**: Double-click `isiMotor_RawUDP_Manager.exe`.
   - On **Linux / Steam Deck**: Double-click `isiMotor-RawUDP-Manager-x86_64.AppImage` (or run `./isiMotor-RawUDP-Manager-x86_64.AppImage`).
2. **Open the Install Tab**:
   - Click on the **`[ 📦 Install ]`** navigation tab (or press `F2`).
   - The Manager automatically discovers your Steam installations for **Le Mans Ultimate** and **rFactor 2** across:
     - Windows Registry & secondary SSD / drive library folders.
     - Linux Native Steam (`~/.local/share/Steam`).
     - Flatpak Steam (`~/.var/app/com.valvesoftware.Steam`).
     - Steam Deck internal storage and MicroSD cards.
3. **Click `[ 📦 Copy DLL ]`**:
   - The manager automatically installs `isiMotor_RawUDP.dll` into the `Plugins/` folder of all detected game installations.
   - It sets `"Enable external plugins": true` in `<GameRoot>/UserData/player/Settings.JSON`.
   - It initializes `CustomPluginVariables.JSON` with optimized default streaming settings.
4. **Customize & Save Settings**:
   - Adjust `Target IP` (e.g., `127.0.0.1` for local apps, `192.168.1.50` for LAN dashboard tablets), `Target Port` (`5000`), and channel refresh rates directly in the UI.
   - Click **`[ 💾 Save ]`** to apply settings across all detected games simultaneously.

---

### Method 2 — Manual Installation

For users who prefer to copy the binary manually without running the Manager:

1. **Copy the DLL**:
   Download `isiMotor_RawUDP.dll` from the GitHub Release and copy it into the `Plugins/` folder of your game:
   - **Le Mans Ultimate**: `<SteamLibrary>/steamapps/common/Le Mans Ultimate/Plugins/isiMotor_RawUDP.dll`
   - **rFactor 2**: `<SteamLibrary>/steamapps/common/rFactor 2/Plugins/isiMotor_RawUDP.dll`

2. **Enable External Plugins**:
   In `<GameRoot>/UserData/player/Settings.JSON`, ensure:
   ```json
   "Enable external plugins": true,
   "Plugin Mask": 255
   ```

3. **Configure Options**:
   Launch the game once to auto-generate `UserData/player/CustomPluginVariables.JSON`, or create the file manually following the reference below.

---

## ⚙️ 3. Configuration Reference (`CustomPluginVariables.JSON`)

The plugin is configured via the standard isiMotor profile settings file located at:
`<GameRoot>/UserData/player/CustomPluginVariables.JSON`

The simulation engine automatically hot-reloads this configuration when modified on disk or via the in-game UI.

### Complete Configuration Schema

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

### 📋 Detailed Parameter Reference

| Parameter | Default | Allowed Values & Syntax | Description |
| :--- | :---: | :--- | :--- |
| **` Enabled`** | `1` | `1` (active), `0` (disabled) | Master plugin toggle handled by the simulation host |
| **`TargetIP`** | `"127.0.0.1"` | IPv4 address (e.g. `"127.0.0.1"`, `"192.168.1.42"`, `"239.255.0.1"`, `"255.255.255.255"`) | Destination IP address (Unicast, Multicast, or Broadcast) |
| **`TargetPort`** | `"5000"` | `"1024"` – `"65535"` (e.g. `"5000"`, `"20777"`) | Outgoing UDP telemetry port |
| **`InboundControl`** | `"Enabled"` | `"Enabled"`, `"Disabled"`, `"1"`, `"0"` | Enables receiver for pit menu and hardware commands |
| **`InboundPort`** | `"5001"` | `"1024"` – `"65535"` | Listening UDP port for external input commands |
| **`TelemetryRate`** | `"unlimited"` | `"off"`, `"unlimited"` (~100Hz), `"100Hz"`, `"60Hz"`, `"30Hz"`, `"20Hz"`, `"10Hz"` | High-frequency vehicle physics & wheel telemetry stream (1888 bytes) |
| **`CompactScoringRate`** | `"unlimited"` | `"off"`, `"unlimited"`, `"10Hz"`, `"5Hz"`, `"2Hz"`, `"1Hz"` | Lightweight single-car timing & sector split stream (168 bytes) |
| **`FullScoringRate`** | `"5Hz"` | `"off"`, `"unlimited"`, `"10Hz"`, `"5Hz"`, `"2Hz"`, `"1Hz"` | Multi-vehicle full-grid scoring table (up to 128 vehicles) |
| **`TrackRulesRate`** | `"3Hz"` | `"off"`, `"unlimited"`, `"5Hz"`, `"3Hz"`, `"1Hz"` | Safety Car, full-course yellows, flags, and caution delta orders |
| **`PitMenuRate`** | `"100Hz"` | `"off"`, `"unlimited"`, `"100Hz"`, `"60Hz"`, `"30Hz"` | Pit menu strategy navigation state stream |
| **`WeatherRate`** | `"1Hz"` | `"off"`, `"unlimited"`, `"2Hz"`, `"1Hz"` | Ambient temperature, track wetness, rainfall, cloudiness, and wind |
| **`ExtendedStateRate`** | `"5Hz"` | `"off"`, `"unlimited"`, `"10Hz"`, `"5Hz"`, `"2Hz"`, `"1Hz"` | Driving aids status (ABS/TC levels), engine damage, and body impact |
| **`ForceFeedbackRate`** | `"unlimited"` | `"off"`, `"unlimited"` (400Hz), `"200Hz"`, `"100Hz"`, `"60Hz"` | Direct-drive steering shaft torque stream |
| **`GraphicsRate`** | `"60Hz"` | `"off"`, `"unlimited"`, `"100Hz"`, `"60Hz"`, `"30Hz"` | Camera world position, orientation matrix & ambient lighting |
| **`SystemEvents`** | `"Enabled"` | `"Enabled"`, `"Disabled"`, `"1"`, `"0"` | Real-time session state transition notifications (Garage, Pits, OnTrack) |
| **`UnsubscribedBuffersMask`** | `"0"` | `"0"` (all enabled), integer bitmask | Low-level bitmask to disable internal buffer serialization |

---

## 🌐 4. Network Topologies & Routing

### Scenario A — Local Dashboard / Overlay / SimHub (Same PC)
- `TargetIP`: `"127.0.0.1"`
- `TargetPort`: `"5000"`
- **Characteristics**: Instantaneous loopback transmission with zero network latency and no firewall configuration required.

### Scenario B — Dedicated Wi-Fi Tablet or Secondary PC on LAN (Unicast)
- `TargetIP`: `"192.168.1.50"` (IP of the tablet or dashboard device)
- `TargetPort`: `"5000"`
- **Why Unicast for Wi-Fi**: Unicast frames use 802.11 hardware MAC link-layer acknowledgements (ACKs) and beamforming, preventing packet loss over Wi-Fi.

### Scenario C — Multi-Device Broadcast / Multicast
- `TargetIP`: `"239.255.0.1"` (Multicast) or `"255.255.255.255"` (LAN Broadcast)
- `TargetPort`: `"5000"`
- **Characteristics**: Allows infinite external listeners (dashboards, overlays, data loggers) to receive telemetry simultaneously without increasing game CPU load.
- **Firewall Rules**: Ensure **UDP port 5000 Outbound** and **UDP port 5001 Inbound** are allowed in Windows Firewall.

---

## 🎮 5. Bi-Directional Inbound UDP Control

The plugin listens on **UDP port 5001** (`InboundPort`) to receive hardware button actions, pit menu navigation, and weather adjustments without keyboard emulation.

### Pit Menu Navigation Commands
Send UDP packet containing ASCII command string or SIMP Type 100 packet:
- `"PitMenuUp"`: Navigate up within the current category items
- `"PitMenuDown"`: Navigate down within the current category items
- `"PitMenuPrevCat"`: Switch to previous pit category (Fuel, Tires, Damage, Strategy)
- `"PitMenuNextCat"`: Switch to next pit category
- `"PitMenuSelect"`: Toggle selection / confirm option

### Cockpit Button Controls
- `"TCIncrease"` / `"TCDecrease"`: Adjust Traction Control setting
- `"ABSIncrease"` / `"ABSDecrease"`: Adjust Anti-Lock Braking setting
- `"BrakeBiasForward"` / `"BrakeBiasRearward"`: Adjust brake balance
- `"Headlights"`: Toggle headlights
- `"Wipers"`: Cycle wiper speeds

---

## 🖥️ 6. Using the Manager for Live Diagnostics

The standalone **isiMotor RawUDP Manager** includes full real-time telemetry inspection capabilities:

1. **Home Tab (`F1`)**: Live dashboard showing stream health, packet frequencies (Hz), and simulator detection status.
2. **Setup Tab (`F2`)**: Automated Steam discovery, DLL installation, and configuration editor.
3. **Explorer Tab (`F3`)**: Deep-packet live inspector displaying:
   - Vehicle dynamics (Speed, Gear, RPM, G-Forces, Tire temperatures and pressures).
   - Multi-car scoring leaderboard with live gaps, lap times, and sector deltas.
   - Force Feedback torque meters and live physics telemetry.
   - Weather and track surface conditions.
4. **Commands Tab (`F4`)**: Interactive testbed to trigger pit menu actions and cockpit inputs directly over UDP.

---

## 🛠️ 7. Troubleshooting Checklist

1. **No telemetry received in dashboard / manager**:
   - Check that `"Enable external plugins": true` is set in `<GameRoot>/UserData/player/Settings.JSON`.
   - Check that `" Enabled": 1` is set in `<GameRoot>/UserData/player/CustomPluginVariables.JSON`.
   - Verify that `isiMotor_RawUDP.dll` exists inside `<GameRoot>/Plugins/`.
   - Ensure the target port (`5000`) matches your dashboard configuration.
2. **Antivirus / Windows Defender warning**:
   - `isiMotor_RawUDP.dll` contains no external runtime dependencies and only uses standard Winsock2. If Windows Defender flags it, add an exclusion for the game `Plugins/` folder.
3. **Steam Deck / Linux Proton specific**:
   - No custom `WINEDLLOVERRIDES` or Proton launch options are needed. The isiMotor 64-bit engine loads the plugin directly from the game's `Plugins/` folder upon startup.
