# 🏎️ isiMotor RawUDP Manager — User Guide

> **Version**: 0.2.1  
> **Supported Simulators**: Le Mans Ultimate (LMU), rFactor 2 (rF2)  
> **Platforms**: Windows 10/11 (x64), Linux & Steam Deck (SteamOS)  

---

## 📖 1. Overview

**isiMotor RawUDP Manager** is a standalone desktop application designed to easily install, configure, inspect, and test the **isiMotor-RawUDP-Plugin** across your simulation games.

### 🌟 Key Highlights
- **Portable & Standalone**: Single executable file. No Python environment, external runtimes, or dependencies required.
- **One-Click Automated Setup**: Automatically scans your drives to detect **Le Mans Ultimate** and **rFactor 2**, installs the native plugin DLL, and configures game settings in one click.
- **Live Stream Diagnostics**: Real-time inspection of high-rate vehicle telemetry, full-grid scoring (up to 128 cars), pit menu strategy, track rules, flags, weather, and Force Feedback (400Hz).
- **Interactive Control Testbed**: Send live pit menu commands, cockpit button inputs, and weather adjustments directly over UDP.

---

## 🚀 2. Getting Started

### Download
Download the latest standalone executable from the [GitHub Releases](https://github.com/marcgardent/isiMotor-RawUDP-Plugin/releases) page:
- **Windows**: `isiMotor_RawUDP_Manager.exe`
- **Linux & Steam Deck**: `isiMotor-RawUDP-Manager-x86_64.AppImage`

### Launching the Application
- **Windows**: Double-click `isiMotor_RawUDP_Manager.exe`.
- **Linux / Steam Deck**: Double-click `isiMotor-RawUDP-Manager-x86_64.AppImage` to open the graphical manager.

### Interface Navigation

The Manager features a top navigation bar with 4 dedicated views:

| View | Shortcut | Purpose |
| :--- | :---: | :--- |
| **`🏠 Home`** | `F1` | Connection status, stream health, packet frequencies (Hz), and bandwidth |
| **`📦 Install`** | `F2` | Automated game discovery, one-click DLL installation & profile configuration editor |
| **`📊 Explorer`** | `F3` | Deep-packet live telemetry inspector, scoring leaderboards & clipboard export |
| **`🎮 Commands`** | `F4` | Interactive UDP command transmitter for pit menu navigation & cockpit buttons |

---

## 📦 3. Installing & Configuring the Plugin (`[ 📦 Install ]` Tab - `F2`)

1. Open the Manager and click on the **`[ 📦 Install ]`** tab (or press `F2`).
2. **Automatic Game Discovery**:
   - The Manager automatically scans all connected drives, Steam libraries, Windows Registry, Linux Native paths, Flatpak, and Steam Deck MicroSD cards.
   - Detected game installations for **Le Mans Ultimate** and **rFactor 2** are displayed in the status table.
3. **One-Click Installation**:
   - Click the **`[ 📦 Copy DLL ]`** button (or press `k`).
   - The Manager installs the embedded universal `isiMotor_RawUDP.dll` into the `Plugins/` directory of all detected games.
   - It enables external plugins in `<GameRoot>/UserData/player/Settings.JSON` (`"Enable external plugins": true`).
   - It initializes `CustomPluginVariables.JSON` with optimized default settings.
4. **Configuring Streaming Options**:
   - Adjust options directly in the configuration editor:
     - **Target IP**: Destination address (`127.0.0.1` for local overlays, `192.168.1.50` for LAN dashboard tablets, `239.255.0.1` for Multicast).
     - **Target Port**: Outgoing UDP telemetry port (default `5000`).
     - **Channel Refresh Rates**: Customize individual refresh frequencies for Telemetry (`unlimited` / `100Hz`), Full Scoring (`5Hz`), Pit Menu (`100Hz`), Weather (`1Hz`), and Force Feedback (`unlimited` / `400Hz`).
     - **Inbound Port**: Inbound command listening port (default `5001`).
   - Click **`[ 💾 Save ]`** to apply changes across all detected games simultaneously. The simulation engine automatically hot-reloads these settings.
5. **Uninstalling**:
   - Click **`[ 🗑️ Uninstall ]`** to safely remove the plugin DLL from detected installations.

---

## 📊 4. Live Telemetry & Grid Explorer (`[ 📊 Explorer ]` Tab - `F3`)

The Explorer view provides deep real-time inspection of all binary UDP data packets streamed by the game:

### Available Packet Channels (`1`–`0`, `i`, `p` shortcuts)
- **🏎️ Vehicle Dynamics (TelemInfo - 1888 bytes)**: Speed, Gear, RPM, Throttle, Brake, Steering, 4-wheel temperatures/pressures/wear, tire surface grip, G-forces, and hybrid battery/MGU status.
- **🏁 Live Grid Scoring (FullScoring)**: Multi-vehicle leaderboard up to 128 cars, driver names, vehicle classes, lap times, sector deltas, gaps to leader, and pit stop states.
- **🚩 Track Rules & Safety Car**: Track status, Yellow flag sectors, Full Course Yellow (FCY), Safety Car speed and position.
- **⛽ Pit Strategy Menu**: Real-time pit menu categories, active selections, and choice counts.
- **🌦️ Weather & Track Conditions**: Ambient and track temperatures, rain matrix (3x3 grid), cloudiness, path wetness, and wind vectors.
- **⚡ Force Feedback (400Hz)**: Direct-drive steering shaft torque telemetry.
- **🔧 Driving Aids & Physics**: Active ABS/TC levels, driving aids status, engine wear, and vehicle body impact damage.
- **🎥 Cameras & Graphics**: 3D camera world position, 3x3 orientation matrices, and ambient RGB lighting.

### Explorer Tools
- **Instant Search Bar (`/`)**: Type to filter fields by key name, value, or description in real time.
- **`[ 📋 Copy JSON ]` (`c` key)**: Exports the entire active data packet to your clipboard as pretty-printed JSON.
- **`[ 📑 Copy Table ]` (`t` key)**: Exports visible/filtered table rows as TSV (ready to paste into Excel or Google Sheets).

---

## 🎮 5. Interactive Inbound Commands (`[ 🎮 Commands ]` Tab - `F4`)

The Commands tab lets you test and trigger inbound UDP actions directly from your keyboard or button box:

### Pit Menu Strategy Controls
- **Up (`U`)** / **Down (`D`)**: Navigate up and down through category choices
- **Prev Category (`L`)** / **Next Category (`R`)**: Switch between pit categories (Fuel, Tires, Damage, Strategy)
- **Select (`Enter`)**: Confirm or toggle the selected pit option

### Cockpit & Vehicle Controls
- Adjust Traction Control (`TC+` / `TC-`) and ABS (`ABS+` / `ABS-`)
- Adjust Brake Balance (`Bias Front` / `Bias Rear`)
- Toggle Headlights and cycle Windshield Wipers

### Practice Session Weather Injection
- Dynamically alter rain intensity, air/track temperatures, and cloud coverage during private practice sessions.

---

## 🌐 6. Network Setup & Routing

### Scenario A — Local Dashboard / SimHub / Overlay (Same PC)
- **Target IP**: `127.0.0.1`
- **Target Port**: `5000`
- **Setup**: Zero configuration required. Telemetry is delivered locally with sub-microsecond latency.

### Scenario B — Wi-Fi Tablet or Dedicated Dashboard Device on LAN (Unicast)
- **Target IP**: `192.168.1.50` (IP address of your tablet or dashboard device)
- **Target Port**: `5000`
- **Why Unicast**: Wi-Fi hardware acknowledges unicast packets at the MAC layer, preventing packet drops over wireless networks.

### Scenario C — Multiple Devices Simultaneously (Multicast / Broadcast)
- **Target IP**: `239.255.0.1` (Multicast) or `255.255.255.255` (LAN Broadcast)
- **Target Port**: `5000`
- **Benefit**: Infinite devices can receive telemetry simultaneously without adding CPU load to the simulation.
- **Firewall**: Ensure UDP port `5000` Outbound and UDP port `5001` Inbound are permitted in Windows Firewall.

---

## 🛠️ 7. Troubleshooting & FAQ

### Telemetry is not received in the Manager or external dashboards
1. Ensure the simulation is running and an active session is loaded.
2. In the Manager **`[ 📦 Install ]`** tab, confirm that the plugin is installed and click **`[ 📦 Copy DLL ]`** to ensure `Settings.JSON` and `CustomPluginVariables.JSON` are properly configured.
3. Verify that the **Target Port** configured in the Manager matches your dashboard listening port (default `5000`).

### Steam Deck & Linux Proton Compatibility
- The plugin DLL runs natively inside the game process without any extra Wine libraries, daemons, or `WINEDLLOVERRIDES` settings required.
- Simply launch the AppImage in Desktop mode, click **`[ 📦 Copy DLL ]`**, and start your game from Steam.
