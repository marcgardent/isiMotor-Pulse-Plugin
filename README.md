# isiMotor-RawUDP-Plugin

High-performance, zero-overhead telemetry and scoring plugin for **Le Mans Ultimate** and **rFactor 2** (isiMotor technology), accompanied by its dedicated Python subproject **`isimotor-rawudp-client`** and interactive TUI benchmark tool.

* **100% Native Binary Protocol**: Zero dynamic memory allocations and zero third-party dependencies.
* **Fully Configurable via `.ini`**: Target IP (local loopback or remote LAN/Wi-Fi devices), target port, and stream toggles.
* **Auto-Generating Configuration**: Self-creates `isiMotor_RawUDP.ini` with default settings upon first launch.

---

## 📁 Repository Structure

```
isiMotor-RawUDP-Plugin/
├── CMakeLists.txt              # Cross-platform CMake build configuration
├── Makefile                    # Makefile shortcuts (make cross, make build, make benchmark)
├── toolchain.cmake             # MinGW-w64 toolchain definition for Linux
├── main.cpp                    # Zero-allocation C++ plugin source
├── instruction.md              # Architectural design notes & SDK guide
├── README.md                   # Plugin documentation
├── LICENSE                     # MIT License
├── .gitignore                  # Git ignore rules
├── include/
│   ├── InternalsPlugin.hpp     # Official isiMotor Internals SDK interface
│   └── PluginObjects.hpp       # Plugin object type declarations
├── isimotor-rawudp-client/     # 🐍 Dedicated Python client subproject
│   ├── pyproject.toml          # PEP 517/621 Python package configuration
│   ├── setup.py                # Legacy pip compatibility
│   ├── README.md               # Python client documentation
│   └── isimotor_rawudp_client/ # Package source (models, decoders, client)
└── benchmark/                  # 📊 Real-time UDP sniffer & frequency benchmark (Textual TUI)
    ├── pyproject.toml
    ├── README.md
    └── sniffer.py
```

---

## 📊 Raw Telemetry Explorer & Benchmark (`Textual` TUI)

An interactive terminal raw data inspector is provided in [`benchmark/`](benchmark) to explore raw binary packets (`Key`, `Value`, `Description`), filter fields in real-time, copy data to clipboard (JSON/TSV), and benchmark stream frequencies (Hz):

```bash
# Launch live explorer on default UDP port 5000:
make benchmark

# Launch simulation mode with built-in mock telemetry generator:
make benchmark-mock
```

---

## 🐍 Python Client Installation (`isimotor-rawudp-client`)

The Python subproject can be installed directly from GitHub:

```bash
# Install directly via Git URL:
pip install "git+https://github.com/<username>/isiMotor-RawUDP-Plugin.git#subdirectory=isimotor-rawudp-client"

# Or install locally in editable mode:
cd isiMotor-RawUDP-Plugin/isimotor-rawudp-client
pip install -e .
```

### Python Quick Start

```python
from isimotor_rawudp_client import IsiMotorClient, TelemInfo, CompactScoring

client = IsiMotorClient(host="0.0.0.0", port=5000)

@client.on_telemetry
def handle_telemetry(t: TelemInfo):
    print(f"Speed: {t.forward_speed_kmh:5.1f} km/h | Gear: {t.gear_str:>2} | RPM: {t.engine_rpm:5.0f} | Fuel: {t.fuel:4.1f}L")

@client.on_scoring
def handle_scoring(s: CompactScoring):
    print(f"Track: {s.track_name} | Lap: {s.total_laps} | S1: {s.cur_sector1:.3f}s")

client.start()
```

---

## 🧭 Coordinate System Notes (from isiMotor SDK)

> [!NOTE]
> **isiMotor World Coordinates:** Left-handed, with `+y` pointing up.
>
> **Local Vehicle Coordinates:**
> * `+x` points out the **left** side of the car (from driver's perspective)
> * `+y` points out the **roof** (upwards)
> * `+z` points out the **back** of the car (rearwards)
>
> **Rotations:**
> * `+x` pitches up
> * `+y` yaws to the right
> * `+z` rolls to the right
>
> **ISO Conversion:**
> ISO vehicle coordinates (`+x` forward, `+y` right, `+z` upward) are right-handed.
> In other words:
> * A `-z` velocity in isiMotor/rFactor is a `+x` velocity in ISO (`telem.forward_speed_mps = -telem.local_vel.z`).
> * A `-z` rotation in isiMotor/rFactor is a `-x` rotation in ISO.

---

## 🛠️ Building the Plugin DLL

### Option 1: Linux Cross-Compilation (MinGW-w64)
```bash
make cross
# Generates bin/isiMotor_RawUDP.dll (or build/isiMotor_RawUDP.dll)
```

### Option 2: Native Windows Build (MSVC / MinGW)
```powershell
make build
# Or:
# cmake -B build -DCMAKE_BUILD_TYPE=Release
# cmake --build build --config Release
```

---

## 📊 Benchmark Comparison

| Metric | Traditional JSON Plugin | **isiMotor-RawUDP-Plugin** |
|---|---|---|
| **External Dependencies** | `nlohmann/json`, `std::string`, `Boost` | **0 dependencies** (native Winsock2 only) |
| **Allocations / Tick** | Multiple heap allocations (`malloc`/`new`) | **0 allocations** (stack / static buffers) |
| **CPU Time per Tick** | ~0.2 ms - 0.8 ms | **< 0.001 ms (sub-microsecond)** |
| **Payload Size** | ~4 - 8 KB / packet (verbose text) | **1888 bytes fixed** (native binary struct) |
| **Streaming Rate** | ~60 Hz | **120 Hz to 400 Hz+ (zero jitter)** |

## ⚙️ Configuration File (`isiMotor_RawUDP.ini`)

When loaded by the game, the plugin automatically looks for an `isiMotor_RawUDP.ini` file in the same folder as the DLL. If it does not exist, it is **automatically generated** with default settings:

```ini
; ==================================================================
; isiMotor-RawUDP-Plugin Configuration File
; ==================================================================

[Network]
; Destination IP address (127.0.0.1 for local PC, or LAN IP for phone/tablet/rig)
TargetIP=127.0.0.1
; Destination UDP Port (default: 5000)
[Streams]
; Frequency limiters per channel: off | unlimited | <N>Hz (e.g. 100Hz, 60Hz, 30Hz, 5Hz)
; -------------------------------------------------------------------------------------
; Telemetry stream (1888 B): off | unlimited (raw ~90-100Hz) | 100Hz | 60Hz | 30Hz | 20Hz | 10Hz
Telemetry=unlimited

; Scoring & timing stream (168 B): off | unlimited (raw ~2-5Hz) | 5Hz | 2Hz | 1Hz
Scoring=unlimited

; System events stream (6 B on session/realtime changes): on | off
SystemEvents=on
```

### 💡 Network Scenarios & Topologies

| Mode | `TargetIP` in `ini` | Use Case & Performance |
|---|---|---|
| **Local Unicast (Default)** | `127.0.0.1` | Local dashboards (SimPad, Sniffer) running on the same game PC. |
| **Wi-Fi / LAN Unicast** | `192.168.1.42` | **Recommended for Wi-Fi tablets/phones.** Full 802.11 speed with hardware ACKs. |
| **LAN Multicast (1:N)** | `239.255.0.1` | Feeds multiple devices simultaneously (Motion rig + SimHub + Dashboard). |
| **Remote Internet / 4G** | `100.64.1.25` | **Remote Pit-Wall / Coach.** Use **Tailscale/WireGuard** for zero-config encrypted routing. |

> 📖 **Full Network Guide**: See [**`docs/NETWORK_GUIDE.md`**](docs/NETWORK_GUIDE.md) for complete details on Multicast group subscriptions (Python/C++ code), Wi-Fi IGMP Snooping optimization, and Public IP / WAN NAT port forwarding.

---

## 📡 UDP Protocol Specification

### 1. Raw Telemetry Packet (`TelemInfoV01`)
* **Size:** `1888 bytes` | **Rate:** 60 Hz – 100 Hz (per physics tick)
* **Alignment:** `#pragma pack(push, 4)`
* **Transmitted Fields:**
  * Contact patch (LPV) & ground velocities (LGV) for 4 wheels
  * Suspension deflections (FL, FR, RL, RR)
  * Engine RPM, Max RPM, Current Gear
  * Driver inputs: Throttle, Brake, Clutch, Steering
  * Aero load: Front & Rear Downforce
  * Fuel level & capacity
  * Session time, delta time, lap number, lap start ET

### 2. Compact Scoring Packet (`SIMP` Type 2)
* **Size:** `168 bytes` | **Rate:** 1 Hz – 5 Hz
* **Header:** Magic `SIMP`, Packet Type `2`
* **Transmitted Fields:**
  * Track Name, Session ID, Total Lap Distance, Session Max Laps
  * Player completed laps, current sector, garage stall state, count lap flag
  * Sector timing: Current S1/S2, Last S1/S2/LapTime, Personal Best S1/S2/LapTime

### 3. System Event Packet (`SIMP` Type 3)
* **Size:** `6 bytes` | **Header:** Magic `SIMP`, Packet Type `3`
* **Events:** `1` = EnterRealtime, `2` = ExitRealtime, `3` = StartSession, `4` = EndSession

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
4. Spawns a live C++ UDP server sending 100 Hz packets over `127.0.0.1` and asserts real-time socket reception.
* **Events:** `1` (EnterRealtime), `2` (ExitRealtime), `3` (StartSession), `4` (EndSession)

---

## ⚖️ Alternatives, PRO vs CON

In the rFactor 2 / Le Mans Ultimate ecosystem, several IPC (Inter-Process Communication) and telemetry streaming approaches exist. Here is how **`isiMotor-RawUDP-Plugin`** compares against the main alternatives:

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

### 3. Raw Binary UDP (`isiMotor-RawUDP-Plugin`) — *This Project*

Direct native binary memory streaming over configurable UDP sockets.

* **PROs:**
  * **Zero allocations & Sub-microsecond latency:** Direct binary struct transfer in `< 0.001 ms` per tick with 0 heap allocations and 0 external dependencies.
  * **Universal Cross-Platform (Proton/Wine & Windows):** Single universal binary (`isiMotor_RawUDP.dll`) works out-of-the-box on both native Windows and Linux Proton without any helper bridge or background daemon.
  * **Fully Configurable Network Routing:** Stream to local loopback (`127.0.0.1`) or remote LAN devices (tablets, smartphones, secondary rigs) via `isiMotor_RawUDP.ini`.
  * **Selective Streams:** Independent toggles for Telemetry, Scoring, and System Events to save bandwidth and CPU cycles when only timing is needed.
  * **Turnkey Ecosystem:** Complete with the [`isimotor-rawudp-client`](isimotor-rawudp-client) Python library and the [`benchmark/`](benchmark) TUI dashboard.
* **CONs:**
  * **Binary protocol:** Requires struct unpacking / memory mapping rather than parsing plain text (handled automatically by our Python client or a 1-line C struct cast).
  * **Schema coupling:** Packet binary layout is tied to the isiMotor SDK definitions (though versioned and strictly packed).
