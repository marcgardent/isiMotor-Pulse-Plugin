# Feature Request: FR-07 — Bi-Directional UDP Input & Hardware Control

- **Status**: 📝 Planned
- **Priority**: High
- **Target Standard**: [rF2SharedMemoryMapPlugin v3.7.x](TARGET.md) (`rF2HWControl`, `rF2WeatherControl`, and `rF2PluginControl` input buffers)

---

## 1. Context & Motivation

`rF2SharedMemoryMapPlugin` allows external tools to send control commands back into rFactor 2 / Le Mans Ultimate:
1. **Pit Menu Interaction**: Allowing external button boxes, Stream Decks, or tablet dashboards to navigate the pit menu (Up, Down, Previous choice, Next choice, Select) without binding keyboard strokes or joystick emulators.
2. **Hardware & Car Controls**: Triggering in-game functions (Ignition, Starter, Headlights, Wipers, TC Up/Down, ABS Up/Down, Brake Bias Forward/Rearward, LCD Mode).
3. **Dynamic Weather Injection**: Allowing dedicated external race directors / weather apps to push dynamic weather scenarios (rain showers, track drying) into the live session.

> **Multicast Architecture Note**: Stream enablement and rate limits are strictly managed by the server-side `isiMotor_RawUDP.ini` configuration file. Inbound UDP commands are dedicated exclusively to game interactions (Pit Menu, HW controls, weather injection) to prevent any client from disrupting Multicast streams for other network consumers.

---

## 2. Technical Specification & SDK Hooks

### 2.1 isiMotor SDK Hooks (`InternalsPluginV07`)

```cpp
class IsiMotorRawUdpPlugin : public InternalsPluginV07 {
public:
    bool HasHardwareInputs() override { return true; }
    void UpdateHardware(const double fDT) override;
    bool CheckHWControl(const char* const controlName, double &fRetVal) override;
    bool AccessWeather(double trackNodeSize, WeatherControlInfoV01 &info) override;
};
```

---

## 3. Binary Inbound Command Packets

All incoming control packets use the unified `RawUdpHeader` (FR-01) with packet types >= 100.

### 3.1 Hardware & Pit Control Packet (`HWControlCommandPacket`, Type 100)

```cpp
#pragma pack(push, 4)

struct HWControlCommandPacket {
    char          controlName[32];       // Name of control (e.g. "PitMenuUp", "PitMenuSelect", "TractionControl")
    double        controlValue;          // Value (1.0 = press / activate, 0.0 = release)
    unsigned short durationMs;           // Auto-release pulse duration in ms (e.g., 50ms pulse)
};

/**
 * Weather Injection Packet (WeatherControlCommandPacket, Type 101)
 */
struct WeatherControlCommandPacket {
    double        ambientTemp;           // Air temp °C
    double        trackTemp;             // Track temp °C
    double        darkCloud;             // 0.0 to 1.0
    double        raining;               // 0.0 to 1.0
    double        windSpeed;             // m/s
    double        windDirection;         // radians
    double        minPathWetness;        // 0.0 to 1.0
    double        maxPathWetness;        // 0.0 to 1.0
};

#pragma pack(pop)
```

### 3.2 Supported Hardware Control Names (`CheckHWControl`)

| Control Name String | Purpose / Action |
|---|---|
| `"PitMenuUp"` | Move up one category in the pit menu |
| `"PitMenuDown"` | Move down one category in the pit menu |
| `"PitMenuPrev"` / `"PitMenuLeft"` | Select previous choice for active pit category |
| `"PitMenuNext"` / `"PitMenuRight"` | Select next choice for active pit category |
| `"PitMenuSelect"` | Toggle / confirm current selection |
| `"TCIncrease"` / `"TCDecrease"` | Adjust vehicle Traction Control setting |
| `"ABSIncrease"` / `"ABSDecrease"` | Adjust vehicle ABS setting |
| `"BrakeBiasForward"` / `"BrakeBiasRearward"` | Shift brake bias balance |
| `"HeadlightsToggle"` | Toggle vehicle headlights |
| `"WipersToggle"` | Cycle wiper speed / state |
| `"IgnitionToggle"` / `"Starter"` | Engine ignition switch and electric starter |
| `"LCDModeToggle"` | Cycle steering wheel / dashboard display page |

---

## 4. Inbound Socket Architecture & Concurrency

- The plugin binds an inbound UDP receiver socket on `config.targetPort` (or dedicated input port `TargetPort + 1`).
- Incoming datagrams are queued in a thread-safe, lock-free ring buffer (zero heap allocations).
- `CheckHWControl()` and `AccessWeather()` consume the queued commands synchronously on the engine's physics tick.

---

## 5. Python Client Support (`isimotor-rawudp-client`)

```python
from isimotor_rawudp_client import IsiMotorClient, PitAction

client = IsiMotorClient()

# Trigger pit menu actions
client.send_pit_action(PitAction.NEXT_CHOICE)
client.send_pit_action(PitAction.MENU_DOWN)

# Adjust in-car setup
client.send_hw_control("TCIncrease", value=1.0, duration_ms=50)

# Inject custom weather
client.send_weather_override(ambient_temp=24.5, rain_intensity=0.8)
```

---

## 6. Acceptance Criteria & Definition of Done

- [ ] Non-blocking UDP receiver thread running safely without crashing or hanging the game.
- [ ] `CheckHWControl` responds to pit menu navigation commands seamlessly.
- [ ] Inbound control commands execute with low latency (< 10 ms).
- [ ] Python client methods for sending commands tested with mock and live tests.
