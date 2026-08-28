# Feature Request: FR-08 — Python Client Ecosystem & Multi-Panel TUI Visualizer

- **Status**: 📝 Planned
- **Priority**: High (Ecosystem & Usability)
- **Target Standard**: [rF2SharedMemoryMapPlugin v3.7.x](TARGET.md) (`rF2SMMonitor` Visualizer & C# Reference Marshaling)

---

## 1. Context & Motivation

`rF2SharedMemoryMapPlugin` includes the `rF2SMMonitor` C# application to inspect all shared memory buffers, monitor race control flags, and demonstrate API consumption.

In the `isiMotor-RawUDP-Plugin` ecosystem:
1. **Python Client (`isimotor-rawudp-client`)**: Provides clean, typed dataclasses, high-speed binary `struct.unpack` decoders, and event-driven async callbacks.
2. **Terminal Visualizer (`benchmark/sniffer.py`)**: A modern, interactive TUI built with **Textual** providing live stream inspection, frequency metrics, and interactive hardware control testing.
3. **End-to-End Validation Harness (`tests/`)**: Continuous testing between native C++ structs and client decoders.

---

## 2. Python Client Roadmap (`isimotor-rawudp-client`)

### 2.1 Unified Event-Driven API
The client will support dedicated decorators and background listeners for all stream types:

```python
from isimotor_rawudp_client import IsiMotorClient, TelemInfo, FullScoringSession, TrackRules, PitMenuState, WeatherState, ExtendedInfo

client = IsiMotorClient(host="0.0.0.0", port=5000)

@client.on_telemetry
def on_telemetry(t: TelemInfo): ...

@client.on_full_scoring
def on_scoring(session: FullScoringSession, grid: list): ...

@client.on_rules
def on_rules(rules: TrackRules): ...

@client.on_pit_menu
def on_pit_menu(menu: PitMenuState): ...

@client.on_weather
def on_weather(weather: WeatherState): ...

@client.on_extended
def on_extended(ext: ExtendedInfo): ...

client.start()
```

### 2.2 Interactive Command APIs
```python
# Hardware & Pit Menu controls
client.send_pit_menu_up()
client.send_pit_menu_select()
client.send_hw_control("HeadlightsToggle", value=1.0)

# Weather injection
client.send_weather_override(ambient_temp=28.0, rain_intensity=0.5)
```

---

## 3. Terminal Visualizer & Benchmark TUI Evolution (`benchmark/sniffer.py`)

The TUI will be upgraded into a full multi-tab dashboard:

```
┌── isiMotor-RawUDP Monitor & Explorer ──────────────────────────────────────────┐
│ [1] Telemetry │ [2] Grid Scoring │ [3] Flags & Rules │ [4] Pit Menu │ [5] Weather│
├────────────────────────────────────────────────────────────────────────────────┤
│ LEADERBOARD (18 Cars Active) - Circuit de la Sarthe (Lap 14 / 24h)             │
│ Pos  #   Driver               Class       Gap       S1      S2      LastLap Pit│
│ -----------------------------------------------------------------------------  │
│ P01  50  A. Fuoco             Hypercar  LEADER   32.145  48.210  3:24.512  -   │
│ P02  83  R. Kubica            Hypercar  +1.42s   32.201  48.190  3:24.890  -   │
│ P03   6  K. Estre             Hypercar  +3.18s   32.310  48.402  3:25.101  PIT │
│ P04  22  O. Jarvis            LMP2      +1 Lap   34.110  51.200  3:32.400  -   │
│ P05  92  M. Christensen       LMGT3     +2 Laps  38.210  56.310  3:54.120  -   │
│                                                                                │
│ RACE CONTROL: 🟢 GREEN FLAG | SC Inactive | Track Temp: 28.4°C | Rain: 0%      │
│ PIT MENU: [Front Tires] -> Hard Compound (2/4) [Use UP/DOWN/ENTER to navigate] │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Integration Test Suite & Golden Reference Validation

The `tests/cpp_mock/isi_mock_host.cpp` mock server will be extended to:
1. Generate realistic multi-vehicle scoring grids, caution flags, pit menu navigation states, and weather transitions.
2. Dump binary golden files (`*.bin`) and JSON expected structures (`*.json`).
3. Run automated assertions verifying bit-exact unpacking in `test_golden_truth.py`.

---

## 5. Acceptance Criteria & Definition of Done

- [ ] All 10 binary stream packet types decoded with zero type/field mismatch.
- [ ] Textual TUI supports multi-tab switching and live interactive pit menu control via keyboard.
- [ ] `make test` runs comprehensive end-to-end tests validating the complete data pipeline.
