# isiMotor RawUDP Manager & Telemetry Diagnostics (Textual TUI)

Modern, interactive terminal telemetry diagnostics, stream inspector, and automated plugin installer for **Le Mans Ultimate** and **rFactor 2**.

Packaged and distributed as a standalone application using **[Briefcase](https://briefcase.readthedocs.io/)** / **[Textual](https://textual.textualize.io/)**.

> ℹ️ Steam detection, DLL install/uninstall and JSON configuration are implemented in the **[`isimotor-rawudp-client`](../isimotor-rawudp-client#-installer-api-isimotor_rawudp_clientinstall)** package (`isimotor_rawudp_client.install`) — the Manager UI is just one consumer of that public API. Use the client package directly if you want to automate installation without the TUI.

---

## 🚀 Key Features

* **Raw Data Explorer (`Key`, `Value`, `Description`):**
  * Live inspection of all 100+ native struct fields with high-contrast formatting and units.
  * Real-time cell updates at 30 FPS without table flickering or selection jumping.
* **Packet Type Selector Menu (Tabs):**
  * `🏎️ TelemInfo (1888 B)` : Full physical vehicle telemetry (kinematics, engine, driver inputs, 4 wheels matrix, hybrid battery/MGU, aero) + **LMU Extensions** (WEC Hypercar Virtual Energy, Live Regen kW, Onboard TC/ABS levels & active flags, Engine Maps, ARBs, Tire Compound enums, Brake Disc wear).
  * `🏁 Grid Scoring` : Up to 128 vehicles on grid (`FullScoringSession`), driver names, classes, lap times, gaps, pit states + **LMU Extensions** (Dynamic Track Grip %, Solar Time of Day, Opponent Fuel %, Cut counters).
  * `🚩 Track Rules & SC` : Full course yellow, yellow flag sectors, Safety Car speed and position.
  * `⛽ Pit Menu` : Interactive pit menu categories, selections, and total choices.
  * `🌦️ Weather` : Ambient temperatures, rain matrix 3x3, wind speed, path wetness.
  * `⚡ FFB (400Hz)` : Ultra-high-rate steering torque telemetry.
  * `🎥 Graphics` : 3D camera world position, 3x3 orientation, RGB lighting.
  * `🔧 Physics & Aids` : 22 driving aids, session damage tracking, pit limiter.
  * `🔔 Events (6 B)` : System state transitions (Enter/Exit Realtime, Start/End Session).
  * `🎮 Inbound Tester` : Interactive keyboard commands (`U`/`D`/`L`/`R`/`Enter`/`W`) for pit navigation and weather overrides.
  * `⚙️ Config JSON` : Auto-detected Steam game paths (LMU / rF2), DLL status, active `CustomPluginVariables.JSON` & `Settings.JSON`.
  * `📊 Stream Rates` : Real-time reception frequency (Hz), average delay (ms), jitter (±ms), and bandwidth (KB/s).
* **Search & Filter Bar:**
  * Real-time instant filtering by field key, value, or description (press `/` to focus).
* **One-Click Actions & Clipboard Export:**
  * `📦 Copy DLL` (`k` key) : Automatically copies `isiMotor_RawUDP.dll` to detected game folders and configures default JSON profiles.
  * `📋 Copy JSON` (`c` key) : Exports full active packet dictionary to clipboard in pretty-printed JSON.
  * `📑 Copy Table` (`t` key) : Exports visible/filtered key-value-desc rows in TSV table format.
* **Keyboard Shortcuts:**
  * `1` - `0`, `i`, `p` : Switch packet explorer and config tabs.
  * `k` : Copy and install compiled DLL into detected games.
  * `/` : Focus search filter bar.
  * `c` : Copy active packet as JSON.
  * `t` : Copy active table as TSV.
  * `r` : Reset packet counters and statistics.
  * `q` : Quit application cleanly.

---

## 🛠️ Usage

```bash
# Launch interactive TUI manager & diagnostics:
isi-manager
# or:
python -m isimotor_rawudp_manager

# Run game detector & plugin installer (provided by isimotor-rawudp-client):
isi-install --status
# or:
python -m isimotor_rawudp_client.install.cli
```


