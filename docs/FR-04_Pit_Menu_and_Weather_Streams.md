# Feature Request: FR-04 — Pit Menu State & Dynamic Weather Streams

- **Status**: 📝 Planned
- **Priority**: Medium-High
- **Target Standard**: [rF2SharedMemoryMapPlugin v3.7.x](TARGET.md) (`rF2PitInfo` buffer @ 100 FPS & `rF2Weather` buffer @ 1 FPS)

---

## 1. Context & Motivation

### 1.1 Pit Menu State (`PitMenuV01`)
In endurance racing (Le Mans Ultimate / rFactor 2), managing pit stops (driver change, tire compound selection, fuel amount, repairs, tire pressure adjustments) via external button boxes, Stream Decks, or mobile touch dashboards requires knowing the exact current state of the in-game pit menu.
`rF2SharedMemoryMapPlugin` streams `PitMenuV01` at 100 FPS.

### 1.2 Dynamic Weather Stream (`WeatherControlInfoV01`)
External strategy tools and spotters (e.g. Crew Chief, timing sheets) need live ambient temperature, track temperature, rain probability/intensity, and wind speed to make tactical pit call recommendations.

---

## 2. Technical Specification & SDK Hooks

### 2.1 isiMotor SDK Hooks (`InternalsPluginV07`)

```cpp
class IsiMotorRawUdpPlugin : public InternalsPluginV07 {
public:
    // Pit Menu Interface (100 Hz)
    bool WantsPitMenuAccess() override { return true; }
    bool AccessPitMenu(PitMenuV01 &info) override;

    // Weather Interface (1 Hz)
    bool WantsWeatherAccess() override { return true; }
    bool AccessWeather(double trackNodeSize, WeatherControlInfoV01 &info) override;

    // Environment Change Notification
    void SetEnvironment(const EnvironmentInfoV01 &info) override;
};
```

### 2.2 Binary Structures

#### 1. Pit Menu Packet (`PitMenuPacket`, SIMP Type 6)
```cpp
#pragma pack(push, 4)

struct PitMenuPacket {
    long          categoryIndex;         // Current menu category index (e.g., Tires, Fuel, Aero, Repair)
    char          categoryName[32];      // Name of current category (e.g., "Front Tires", "Fuel To Add")
    long          choiceIndex;           // Currently selected choice index
    char          choiceString[32];      // Choice label (e.g., "Soft Slick", "45 Liters", "Fix Damage")
    long          numChoices;            // Total choices available under this category
};
```

#### 2. Weather & Atmospheric Packet (`WeatherPacket`, SIMP Type 7)
```cpp
struct WeatherPacket {
    double        ambientTemp;           // Air temperature (°C)
    double        trackTemp;             // Track surface temperature (°C)
    double        darkCloud;             // Cloud cover density (0.0 to 1.0)
    double        raining;               // Current rain intensity (0.0 to 1.0)
    double        windSpeed;             // Wind velocity (m/s)
    double        windDirection;         // Wind direction (radians)
    double        minPathWetness;        // Minimum track groove wetness (0.0=dry, 1.0=flooded)
    double        maxPathWetness;        // Maximum track groove wetness
    double        waterDepth;            // Puddle water depth (meters)
};

#pragma pack(pop)
```

---

## 3. Rate Limiting & Transmission Strategy

- **Pit Menu**: Transmitted at up to **100 Hz** when the menu is active, throttled down to **5 Hz** or sent on-change when idle.
- **Weather**: Transmitted at **1 Hz** (weather changes gradually).

```ini
[Streams]
; Pit menu stream (~100Hz): off | unlimited | 100Hz | 50Hz | 20Hz | 5Hz
PitMenu=100Hz

; Weather and track conditions (~1Hz): off | unlimited | 2Hz | 1Hz
Weather=1Hz
```

---

## 4. Python Client Integration (`isimotor-rawudp-client`)

```python
from isimotor_rawudp_client import IsiMotorClient, PitMenuState, WeatherState

client = IsiMotorClient()

@client.on_pit_menu
def handle_pit_menu(menu: PitMenuState):
    print(f"Pit Menu: [{menu.category_name}] -> {menu.choice_string} ({menu.choice_index + 1}/{menu.num_choices})")

@client.on_weather
def handle_weather(w: WeatherState):
    print(f"Weather: Air {w.ambient_temp_c:.1f}°C | Track {w.track_temp_c:.1f}°C | Rain: {w.rain_percent:.0f}% | Track Wetness: {w.max_path_wetness:.2f}")
```

---

## 5. Acceptance Criteria & Definition of Done

- [ ] Implement `AccessPitMenu` and `AccessWeather` in `main.cpp`.
- [ ] Correctly capture menu category names, active choice strings, and index counts.
- [ ] Correctly capture track temperature, air temperature, cloudiness, and wetness.
- [ ] Unit tests for `PitMenuPacket` and `WeatherPacket` packing and parsing.
