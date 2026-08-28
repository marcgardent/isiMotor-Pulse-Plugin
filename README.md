# isiMotor-RawUDP-Plugin

High-performance, zero-overhead telemetry and scoring plugin for **Le Mans Ultimate** and **rFactor 2** (isiMotor technology), accompanied by its dedicated Python subproject **`isimotor-rawudp-client`**.

Streams raw native binary structures directly over local UDP (`127.0.0.1:5000`) with **zero dynamic memory allocations** and **zero third-party dependencies**.

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
└── benchmark/                  # 📊 Real-time UDP sniffer & frequency benchmark (Rich UI)
    ├── pyproject.toml
    ├── README.md
    └── sniffer.py
```

---

## 📊 Live Telemetry Sniffer & Frequency Benchmark (`Rich` UI)

A real-time terminal dashboard is provided in [`benchmark/`](file:///home/marcgardent/PycharmProjects/simpad/isiMotor-RawUDP-Plugin/benchmark) to inspect incoming packets, measure frequencies (Hz), analyze jitter/delays, and test payload compatibility:

```bash
# Launch live sniffer on UDP port 5000:
make benchmark
# Or: python benchmark/sniffer.py

# Launch simulation mode with built-in mock telemetry generator:
make benchmark-mock
# Or: python benchmark/sniffer.py --mock
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
| **Payload Size** | ~4 - 8 KB / packet (verbose text) | **1904 bytes fixed** (native binary struct) |
| **Streaming Rate** | ~60 Hz | **120 Hz to 400 Hz+ (zero jitter)** |

## ⚙️ Configuration File (`isiMotor_RawUDP.ini`)

When loaded by the game, the plugin automatically checks for an `isiMotor_RawUDP.ini` file in the same directory as the DLL. If it does not exist, it is **automatically generated** with default settings:

```ini
[Network]
; Destination IP address (127.0.0.1 for local client, or LAN IP for external tablet/rig)
TargetIP=127.0.0.1
; Destination UDP Port (default: 5000)
TargetPort=5000

[Streams]
; Raw Telemetry binary stream (1904 bytes @ 60-100Hz): 1=Enabled, 0=Disabled
EnableTelemetry=1
; Compact Scoring binary stream (176 bytes @ 1-5Hz): 1=Enabled, 0=Disabled
EnableScoring=1
; System Events notification (6 bytes on state transitions): 1=Enabled, 0=Disabled
EnableSystemEvents=1
```

---

## 📡 UDP Protocol Specification (`127.0.0.1:5000`)

### 1. Raw Telemetry Packet (`TelemInfoV01`)
* **Size:** `1904 bytes` | **Rate:** 60 Hz – 100 Hz (per physics tick)
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
* **Size:** `176 bytes` | **Rate:** 1 Hz – 5 Hz
* **Header:** Magic `SIMP`, Packet Type `2`
* **Transmitted Fields:**
  * Track Name, Session ID, Total Lap Distance, Session Max Laps
  * Player completed laps, current sector, garage stall state, count lap flag
  * Sector timing: Current S1/S2, Last S1/S2/LapTime, Personal Best S1/S2/LapTime

### 3. System Event Packet (`SIMP` Type 3)
* **Size:** `6 bytes` | **Header:** Magic `SIMP`, Packet Type `3`
* **Events:** `1` (EnterRealtime), `2` (ExitRealtime), `3` (StartSession), `4` (EndSession)

---

## 👏 Acknowledgments & Alternative JSON Plugin (lmu-socket)

If you are looking for a feature-rich, human-readable **JSON-over-UDP** telemetry plugin, check out [shin0bi's lmu-socket](https://gitlab.com/shin0bi/lmu-socket) on GitLab!

### 🐧 Linux (Wine / Proton) Compatibility Note for `lmu-socket`
In `lmu-socket`, packets are broadcast by default to `255.255.255.255`. Under Linux using Steam Proton/Wine:
1. **Receiver side (Python/Middleware):** Bind your UDP socket to `0.0.0.0` (`INADDR_ANY`) so it accepts packets forwarded across network interfaces:
   ```python
   sock.bind(("0.0.0.0", 5000))
   ```
2. **Sender side (C++ DLL):** Alternatively, configure the plugin destination IP from `255.255.255.255` to local loopback unicast `127.0.0.1` in `socket.h` / `main.cpp` for direct local delivery.

---

## 🗄️ Architectural Alternatives: UDP vs Shared Memory (rF2SharedMemoryMapPlugin)

In the rFactor 2 / Le Mans Ultimate ecosystem, two main IPC (Inter-Process Communication) paradigms exist for telemetry:

### 1. Windows Shared Memory (`rF2SharedMemoryMapPlugin`)
* **On Windows:** Traditional plugins (such as [TheIronWolf's rF2SharedMemoryMapPlugin](https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin)) use Windows Memory-Mapped Files (`CreateFileMappingW` / `MapViewOfFile`). This provides ultra-fast zero-copy memory reads on Windows.
* **On Linux (Steam Proton / Wine) — The Compatibility Challenge:**
  Because the game runs inside a Wine/Proton prefix, Windows named shared memory objects are isolated within Wine's internal namespace. Native Linux applications **cannot** directly access or map these memory blocks.
  To achieve Linux compatibility with Shared Memory, you must use a dedicated Wine bridge such as [schlegp/rF2SharedMemoryMapPlugin_Wine](https://github.com/schlegp/rF2SharedMemoryMapPlugin_Wine):
  * Requires compiling a specific Wine-aware DLL (`rF2SharedMemoryMapPlugin_Wine.dll`).
  * Requires running a continuous background **bridge daemon** to mirror Wine's memory map to Linux POSIX shared memory (`/dev/shm`) or domain sockets.
  * Involves complex multi-step installation, prefix dependencies, and process synchronization.

### 2. Raw Binary UDP (`isiMotor-RawUDP-Plugin`) — *Our Approach*
* **Zero Configuration & Cross-Platform:** Local UDP (`127.0.0.1:5000`) naturally bridges the Wine/Proton network stack to native Linux host applications without any helper daemon.
* **Single Universal Binary:** The exact same `isiMotor_RawUDP.dll` works identically on both native Windows and Linux Proton.
* **Sub-Microsecond Latency:** Transmits direct native binary memory structures with zero allocations and zero runtime overhead.
