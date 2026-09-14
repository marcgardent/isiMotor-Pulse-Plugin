# isiMotor-Pulse-Plugin

High-performance, zero-overhead telemetry and scoring plugin for **Le Mans Ultimate** and **rFactor 2** (isiMotor technology), accompanied by its dedicated Python subproject **`isimotor-pulse-client`** and interactive TUI benchmark tool.

* **100% Native Binary Protocol over ZeroMQ**: Zero dynamic memory allocations; a single pinned dependency (libzmq, statically linked) replaces raw sockets with a proper PUB/SUB transport.
* **Le Mans Ultimate (LMU) & WEC Native Extensions**: Full support for WEC Hypercar Virtual Energy, Live Regeneration (kW), Onboard ECU driver aids (TC, TC Cut/Slip, ABS, Engine Maps, ARBs, active TC/ABS interventions), Tire Compound Enums, Dynamic Track Grip, and Opponent Fuel Fraction.
* **Live Hot-Reload**: Edit `CustomPluginVariables.JSON` while driving — rates, network target, logging and all flags apply instantly without restarting the simulator (event-based Win32 file watcher, zero polling).
* **ZeroMQ PUB/SUB over TCP**: The plugin binds a telemetry PUB and an inbound commands SUB socket; any number of local or remote consumers connect to them (local `127.0.0.1`, LAN, or remote via Tailscale/WireGuard).
* **Python Client Library**: `isimotor-pulse-client` — ready to use out-of-the-box for custom dashboards, data loggers, and hardware integrations.
* **Linux / Steam Deck / Proton**: Zero-config — the DLL loads natively, no Wine overrides or launch options required.

---

## 📁 Repository Structure

```
isiMotor-Pulse-Plugin/
├── Makefile                    # Makefile shortcuts (make cross, make build, make benchmark)
├── README.md                   # Plugin documentation
├── LICENSE                     # Apache License 2.0
├── .gitignore                  # Git ignore rules
├── isimotor-pulse-plugin/     # 🏎️ C++ Native Plugin subproject
│   ├── CMakeLists.txt          # Standalone C++ build definitions
│   ├── toolchain.cmake         # MinGW-w64 toolchain definition for Linux
│   ├── src/                    # C++ Plugin source (main.cpp)
│   │   └── main.cpp
│   └── include/                # isiMotor Internals SDK headers (V07) + LMU Extensions
│       ├── InternalsPlugin.hpp
│       └── PluginObjects.hpp
├── binding/python/isimotor-pulse-client/     # 🐍 Dedicated Python client subproject
│   ├── pyproject.toml          # PEP 517/621 Python package configuration
│   ├── README.md               # Python client documentation
│   └── isimotor_pulse_client/ # Package source (models, decoders, client)
│       ├── models/             # Domain dataclasses (base isiMotor + .lmu models)
│       ├── decoder/            # Binary decoders (telemetry, scoring, LMU extensions)
│       ├── install/            # Public installer API: Steam discovery, DLL install, JSON config
│       ├── resources/          # Bundled isiMotor_Pulse.dll shipped with the pip package
│       └── client.py           # High-level client facade
└── binding/python/isimotor-pulse-manager/    # 📊 Manager & Telemetry Diagnostics (Textual TUI / Briefcase)
    ├── pyproject.toml          # Package and Briefcase configuration
    ├── README.md
    └── isimotor_pulse_manager/
        ├── ui/                 # Textual modern UI views & widgets (consumes isimotor_pulse_client.install)
        ├── engine/             # Realtime statistics & telemetry engine
        └── extractors/         # SOLID data extractors & table renderers
```

---

## 📊 Raw Telemetry Explorer & Manager (`Textual` TUI)

An interactive terminal raw data inspector & management app is provided in [`isimotor-pulse-manager/`](binding/python/isimotor-pulse-manager) to explore raw binary packets (`Key`, `Value`, `Description`), filter fields in real-time, copy data to clipboard (JSON/TSV), install DLLs in 1-click, and benchmark stream frequencies (Hz):

```bash
# Launch live manager / telemetry explorer on default UDP port 5000:
make manager
# Or:
make benchmark
```

---

## 🐍 Python Client Installation (`isimotor-pulse-client`)

The Python subproject can be installed directly from GitHub:

```bash
# Install directly via Git URL:
pip install "git+https://github.com/<username>/isiMotor-Pulse-Plugin.git#subdirectory=binding/python/isimotor-pulse-client"

# Or install locally in editable mode:
cd isiMotor-Pulse-Plugin/binding/python/isimotor-pulse-client
pip install -e .
```

### Python Quick Start

```python
from isimotor_pulse_client import IsiMotorClient, TelemInfo, FullScoringSession

client = IsiMotorClient(host="127.0.0.1", base_port=5000)


@client.on_telemetry
def handle_telemetry(t: TelemInfo):
    # Base isiMotor physics
    print(
        f"Speed: {t.forward_speed_kmh:5.1f} km/h | Gear: {t.gear_str:>2} | RPM: {t.engine_rpm:5.0f} | Fuel: {t.fuel:4.1f}L"
    )

    # LMU & WEC Hypercar extensions
    if t.lmu.has_hypercar_energy:
        print(
            f"Hypercar {t.lmu.vehicle_model} — Virtual Energy: {t.lmu.virtual_energy * 100:.1f}% | Regen: {t.lmu.regen_kw:.1f} kW"
        )

    # LMU Onboard ECU & Active Driver Aids
    if t.ecu.has_tc:
        print(f"TC Level: {t.ecu.tc_level}/{t.ecu.tc_max} (Active: {t.ecu.tc_active})")
    if t.ecu.has_abs:
        print(f"ABS Level: {t.ecu.abs_level}/{t.ecu.abs_max} (Active: {t.ecu.abs_active})")


@client.on_full_scoring
def handle_scoring(s: FullScoringSession):
    print(f"Track: {s.track_name} | Time: {s.lmu.time_of_day_str} | Grip: {s.lmu.grip_fraction * 100:.0f}%")
    for car in s.leaderboard[:3]:
        print(f"  P{car.place} {car.driver_name} — Opponent Fuel: {car.lmu.fuel_fraction * 100:.1f}%")


client.start()
```

---

## 🛠️ Building the Plugin DLL

The project standardizes on **MinGW-w64 cross-compilation**, producing a single universal standalone binary (`isiMotor_Pulse.dll`) compatible with both native Windows and Linux Proton / Steam Deck:

```bash
# Standard build (MinGW-w64 cross-compilation):
make cross
# Or alias:
make build
# Generates build/isiMotor_Pulse.dll
```

---

## ⚡ Automated Game Installation & Configuration

### Option A — Standalone Manager AppImage / Exe (Recommended)
Download the standalone executable from [GitHub Releases](https://github.com/marcgardent/isiMotor-Pulse-Plugin/releases) (no Python environment required):
- **Windows**: Double-click `isiMotor_Pulse_Manager.exe` -> Open the **`[ 📦 Install ]`** tab and click **`[ 📦 Copy DLL ]`**.
- **Linux / Steam Deck**: Double-click `isiMotor-Pulse-Manager-x86_64.AppImage` -> Open the **`[ 📦 Install ]`** tab and click **`[ 📦 Copy DLL ]`**.

### Option B — Developer Makefile
If working within the cloned repository:

```bash
# Check detected games and installation status:
make status

# Install plugin into all detected game installations:
make install

# Uninstall / remove plugin:
make uninstall
```

### Option C — `isimotor-pulse-client` Installer API / CLI
Steam discovery, DLL install/uninstall and JSON configuration are a public API of the **`isimotor-pulse-client`** pip package (which also bundles the compiled DLL) — no need to clone the repository:

```bash
pip install "git+https://github.com/marcgardent/isiMotor-Pulse-Plugin.git#subdirectory=binding/python/isimotor-pulse-client"

isi-install --status      # List detected games and installation status
isi-install               # Install the DLL + configure JSON on all detected games
isi-install --uninstall   # Remove the DLL from all detected games
```

Or programmatically:

```python
from isimotor_pulse_client.install import detect_game_installations, copy_and_install_dll

games = detect_game_installations()
success, message, installed_paths = copy_and_install_dll()
```

> 📖 See [`isimotor-pulse-client/README.md`](binding/python/isimotor-pulse-client/README.md#-installer-api-isimotor_pulse_clientinstall) for the full Installer API reference.

---

## ⚙️ Configuration (`CustomPluginVariables.JSON`)

The plugin uses the standard isiMotor plugin configuration system via `UserData/player/CustomPluginVariables.JSON`. It is automatically configured upon install or generated by the game engine upon first launch:

```json
{
  "isiMotor_Pulse": {
    " Enabled": 1,
    "EnableLogging": "Disabled",
    "TcpHost": "127.0.0.1",
    "TcpBasePort": "5000",
    "InboundControl": "Enabled",
    "InboundTcpPort": "5101",
    "PlayerTelemetryRate": "unlimited",
    "OpponentTelemetryRate": "off",
    "CompactScoringRate": "10Hz",
    "FullScoringRate": "5Hz",
    "WeatherRate": "1Hz",
    "ExtendedStateRate": "5Hz",
    "ForceFeedbackRate": "unlimited",
    "GraphicsRate": "60Hz",
    "SystemEvents": "Enabled",
    "UnsubscribedBuffersMask": "0"
  }
}
```

### 🔌 One TCP Port per Packet Type

Each outbound packet type is published on its **own** ZeroMQ PUB socket, bound on `TcpBasePort + packetType`, so a consumer can subscribe to only the stream(s) it needs (e.g. a HUD subscribing to `ForceFeedback` @ 400Hz without also receiving full telemetry). Ports are hardcoded arithmetically for now, pending a future service registry that will allocate them dynamically:

| Type | Packet | Port (`TcpBasePort + type`) |
|---|---|---|
| 1 | `TelemInfo` | 5001 |
| 2 | `CompactScoring` | 5002 |
| 3 | `SystemEvent` | 5003 |
| 4 | `FullScoringSession` | 5004 |
| 7 | `WeatherControl` | 5007 |
| 8 | `ExtendedState` | 5008 |
| 9 | `ForceFeedback` | 5009 |
| 10 | `Graphics` | 5010 |

The inbound commands channel (hardware controls, weather overrides) stays grouped on a single port, `InboundTcpPort` (default `5101`).

### 🔄 Live Hot-Reload

The plugin automatically detects changes to `CustomPluginVariables.JSON` while the simulator is running — **no restart required**. An event-based Win32 file watcher (`FindFirstChangeNotification`) monitors the config directory with zero polling overhead.

**Hot-reloadable parameters** (apply instantly):
- All streaming rates (`PlayerTelemetryRate`, `OpponentTelemetryRate`, `CompactScoringRate`, `FullScoringRate`, `WeatherRate`, `ExtendedStateRate`, `ForceFeedbackRate`, `GraphicsRate`)
- `EnableLogging`, `SystemEvents`, `UnsubscribedBuffersMask`
- `TcpHost` and `TcpBasePort` (every per-type telemetry PUB endpoint rebound in-place, no reconnect needed by clients already connected once they retry)

**Restart required**:
- `InboundTcpPort` — changing the inbound listening port requires a simulator restart (a log warning is emitted).

> 📖 **Full User Notice & Options Guide**: See [**`USER_NOTICE.md`**](USER_NOTICE.md) for the complete index table and configuration documentation.

### 💡 Network Scenarios & Topologies

The plugin is a ZeroMQ **PUB/SUB** endpoint over **TCP only**: the plugin always binds; every consumer (dashboard, overlay, Manager) connects to it as a SUB client. Any number of consumers can connect to the same PUB endpoint at once — no separate multicast/broadcast setup needed.

| Mode | `TcpHost` in config | Use Case & Performance |
|---|---|---|
| **Local (Default)** | `127.0.0.1` | Local dashboards (SimPad, Sniffer) running on the same game PC. |
| **Wi-Fi / LAN** | `0.0.0.0` (bind all interfaces) | **Recommended for Wi-Fi tablets/phones.** Clients connect to the sim PC's LAN IP. |
| **Multiple LAN Devices** | `0.0.0.0` | Feeds multiple devices simultaneously (Motion rig + SimHub + Dashboard) — each just opens its own SUB connection. |
| **Remote Internet / 4G** | `0.0.0.0` (behind a `100.64.x.x` Tailscale IP) | **Remote Pit-Wall / Coach.** Use **Tailscale/WireGuard** for zero-config encrypted routing. |

> 📖 **Full Network Guide**: See [**`docs/NETWORK_GUIDE.md`**](docs/NETWORK_GUIDE.md) for complete details on connecting multiple ZeroMQ SUB consumers and Public IP / WAN NAT port forwarding.

---

## 📡 Wire Protocol Specification (ZeroMQ Payload Format)

Every outbound packet type is a **FlatBuffer** (`schemas/*.fbs`): since each is delivered on its own ZeroMQ port (or, for the grouped inbound channel, disambiguated by a FlatBuffers union), there is no header and no chunking — the ZeroMQ message boundary IS the FlatBuffer. The full fork off the legacy `RawUdpHeader`/chunk-slicing wire format is complete; Types 1 and 4 (the largest, with nested arrays and LMU extensions) were the last to migrate.

| Packet Type | Name | Wire Format | Rate | Description |
|---|---|---|---|---|
| **Type 1** | `TelemInfo` | FlatBuffer (`telemetry.fbs`) | 60–100Hz | 4-wheel dynamics, tire temps/pressures/wear, engine RPM, inputs, hybrid SoC. |
| **Type 2** | `CompactScoring` | FlatBuffer (`compact_scoring.fbs`) | 1–5Hz | Player sector timing (S1/S2/Lap), sector indices, session time. |
| **Type 3** | `SystemEvent` | FlatBuffer (`system_event.fbs`) | Event-driven | Session start/end, realtime cockpit enter/exit events. |
| **Type 4** | `FullScoringSession` | FlatBuffer (`full_scoring.fbs`) | 5Hz | Up to 128 vehicles on grid, classes, driver names, gaps, pit states. |
| **Type 5** | `TrackRulesSession` | Legacy struct, sliced (332+ B) | 3Hz | FCY, yellow flag zones, Safety Car position/speed, frozen order. |
| **Type 6** | `PitMenu` | Legacy struct, 76 bytes | 100Hz | Interactive pit menu category, current choice, total choices. |
| **Type 7** | `WeatherControl` | FlatBuffer (`weather.fbs`) | 1Hz | 3x3 rain matrix, cloudiness, ambient temp Kelvin/Celsius, wind vector. |
| **Type 8** | `ExtendedState` | FlatBuffer (`extended_state.fbs`) | 5Hz | 22 driving aids (`PhysicsOptions`), max/accumulated impact damage, pit limiter. |
| **Type 9** | `ForceFeedback` | FlatBuffer (`force_feedback.fbs`) | 400Hz | Ultra-high-rate steering column shaft torque value & percentage. |
| **Type 10** | `Graphics` | FlatBuffer (`graphics.fbs`) | 60Hz | 3D camera position, 3x3 orientation matrix, ambient RGB lighting, camera view. |
| **Type 100** | `HWControlCommand` | FlatBuffer (`inbound_command.fbs`, `HWControlCommand` union member) | Inbound (On demand) | Hardware button emulation & pit menu navigation (`PitMenuUp/Down/Select`, `TCIncrease`). |
| **Type 101** | `WeatherControlCommand`| FlatBuffer (`inbound_command.fbs`, `WeatherControlCommand` union member) | Inbound (On demand) | Dynamic ambient temperature, rain intensity, wind, and path wetness injection. |

> **Note**: Types 5 (`TrackRulesSession`) and 6 (`PitMenu`) are exercised by the test mock host for coverage but are not currently emitted by the real plugin.

Schemas live in [`schemas/`](schemas); regenerate the checked-in C++/Python bindings after editing one with `make generate-schemas` (requires the `flatc` compiler).

---

## 🧪 Integration Testing & Ground-Truth Validation

The project includes an end-to-end testing harness that cross-validates Python decoders against native C++ ground truth:

```bash
make test
```

This command automatically:
1. Compiles the native C++ test mock host ([`tests/cpp_mock/isi_mock_host.cpp`](tests/cpp_mock/isi_mock_host.cpp)).
2. Dumps raw memory binary files and JSON truth references from C++.
3. Runs unit tests verifying byte-for-byte decoding accuracy across all 199+ fields.
4. Spawns a live C++ ZeroMQ PUB server sending 100 Hz packets over `127.0.0.1` and asserts real-time socket reception.
* **Events:** `1` (EnterRealtime), `2` (ExitRealtime), `3` (StartSession), `4` (EndSession)

---

## ⚖️ Alternatives, PRO vs CON

In the rFactor 2 / Le Mans Ultimate ecosystem, several IPC (Inter-Process Communication) and telemetry streaming approaches exist. Here is how **`isiMotor-Pulse-Plugin`** compares against the main alternatives:

---

### 1. Windows Shared Memory (`rF2SharedMemoryMapPlugin`)

Traditional plugins such as [TheIronWolf's rF2SharedMemoryMapPlugin](https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin) use Windows Memory-Mapped Files (`CreateFileMappingW` / `MapViewOfFile`).

* **PROs:**
  * **Zero-copy IPC:** Ultra-fast direct memory reads on native Windows.
  * **Widespread adoption:** Standard in the legacy Windows rFactor 2 ecosystem and broadly supported by tools like SimHub.
* **CONs:**
  * **Proton / Linux Complexity:** Windows named shared memory blocks are isolated inside the Wine prefix. To bridge telemetry to Linux host apps, you must use a bridge like [schlegp/rF2SharedMemoryMapPlugin_Wine](https://github.com/schlegp/rF2SharedMemoryMapPlugin_Wine), which requires a Wine-specific DLL build and a continuous background daemon copying memory to `/dev/shm`.
  * **Local-only:** Cannot transmit data over LAN/Wi-Fi to external dashboards, smartphones, or secondary PCs without an extra network forwarder.

---

### 2. JSON over UDP (`lmu-socket`)

If you prefer human-readable textual payloads, check out [shin0bi's lmu-socket](https://gitlab.com/shin0bi/lmu-socket) on GitLab for JSON-over-UDP streaming.

* **PROs:**
  * **Human-readable & Self-documenting:** Easy to inspect packets and build quick web prototypes.
  * **Language-agnostic:** Any language with a standard JSON parser can ingest telemetry directly.
  * **Network capability:** Streams over UDP across local and remote networks.
* **CONs:**
  * **High CPU overhead:** Dynamic JSON serialization and heap allocations (`malloc`/`new`) on every physics tick (~0.2 ms – 0.8 ms per frame vs < 0.001 ms).
  * **Large payload size:** Verbose text keys yield 4 KB – 8 KB per packet (vs 1.9 KB binary).
  * **Linux / Proton note:** By default broadcasts to `255.255.255.255`; under Wine/Proton, receiver sockets must bind to `0.0.0.0` (`INADDR_ANY`) or configure loopback unicast `127.0.0.1`.

---

### 3. Raw Binary over ZeroMQ (`isiMotor-Pulse-Plugin`) — *This Project*

Direct native binary memory streaming over a ZeroMQ PUB/SUB transport (TCP).

* **PROs:**
  * **Zero allocations & Sub-microsecond latency:** Direct binary struct transfer in `< 0.001 ms` per tick with 0 heap allocations, and a single pinned, statically-linked dependency (libzmq).
  * **Universal Cross-Platform (Proton/Wine & Windows):** Single universal binary (`isiMotor_Pulse.dll`) works out-of-the-box on both native Windows and Linux Proton without any helper bridge or background daemon.
  * **Multi-Consumer by Design:** PUB/SUB lets any number of local or remote consumers (tablets, smartphones, secondary rigs) connect to the same telemetry endpoint — no multicast/broadcast configuration to manage.
  * **Frequency Limiters & Selective Streams:** Independent frequency rate limiters (`off`, `unlimited`, `100Hz`, `60Hz`, `30Hz`, `5Hz`) per channel via `isiMotor_Pulse.ini` to save Wi-Fi airtime and CPU cycles.
  * **Turnkey Ecosystem:** Complete with the [`isimotor-pulse-client`](binding/python/isimotor-pulse-client) Python library (`pyzmq`-based) and the [`benchmark/`](benchmark) TUI dashboard.
* **CONs:**
  * **Binary protocol:** Requires struct unpacking / memory mapping rather than parsing plain text (handled automatically by our Python client or a 1-line C struct cast).
  * **Schema coupling:** Packet binary layout is tied to the isiMotor SDK definitions (though versioned and strictly packed).
  * **TCP-only:** No UDP/multicast fallback — every consumer opens its own TCP connection (negligible overhead in practice, but a design constraint to be aware of).
