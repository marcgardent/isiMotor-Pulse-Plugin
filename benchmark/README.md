# isiMotor Telemetry Raw Packet Explorer & Benchmark (Textual TUI)

Modern, interactive terminal raw data inspector built with **[Textual](https://textual.textualize.io/)** for **Le Mans Ultimate** and **rFactor 2** binary telemetry streams.

---

## 🚀 Key Features

* **Raw Data Explorer (`Key`, `Value`, `Description`):**
  * Live inspection of all 100+ native struct fields with high-contrast formatting and units.
  * Real-time cell updates at 30 FPS without table flickering or selection jumping.
* **Packet Type Selector Menu (Tabs):**
  * `🏎️ TelemInfo (1888 B)` : Full physical vehicle telemetry (kinematics, engine, driver inputs, 4 wheels matrix, hybrid battery/MGU, aero).
  * `🏁 Grid Scoring` : Up to 128 vehicles on grid (`FullScoringSession`), driver names, classes, lap times, gaps, pit states.
  * `🚩 Track Rules & SC` : Full course yellow, yellow flag sectors, Safety Car speed and position.
  * `⛽ Pit Menu` : Interactive pit menu categories, selections, and total choices.
  * `🌦️ Weather` : Ambient temperatures, rain matrix 3x3, wind speed, path wetness.
  * `⚡ FFB (400Hz)` : Ultra-high-rate steering torque telemetry.
  * `🎥 Graphics` : 3D camera world position, 3x3 orientation, RGB lighting.
  * `🔧 Physics & Aids` : 22 driving aids, session damage tracking, pit limiter.
  * `🔔 Events (6 B)` : System state transitions (Enter/Exit Realtime, Start/End Session).
  * `🎮 Inbound Tester` : Interactive keyboard commands (`U`/`D`/`L`/`R`/`Enter`/`W`) for pit navigation and weather overrides.
  * `📊 Stream Rates` : Real-time reception frequency (Hz), average delay (ms), jitter (±ms), and bandwidth (KB/s).
* **Search & Filter Bar:**
  * Real-time instant filtering by field key, value, or description (press `/` to focus).
* **One-Click Clipboard Export:**
  * `📋 Copy JSON` (`c` key) : Exports full active packet dictionary to clipboard in pretty-printed JSON.
  * `📑 Copy Table` (`t` key) : Exports visible/filtered key-value-desc rows in TSV table format.
* **Keyboard Shortcuts:**
  * `1` - `0`, `i` : Switch packet explorer tabs.
  * `/` : Focus search filter bar.
  * `c` : Copy active packet as JSON.
  * `t` : Copy active table as TSV.
  * `r` : Reset packet counters and statistics.
  * `q` : Quit application cleanly.

---

## 🛠️ Usage

```bash
# Listen to live game telemetry on default port 5000:
python sniffer.py

# Listen on custom host/port:
python sniffer.py --host 0.0.0.0 --port 5000
```


