# Feature Request: FR-03 — Track Rules, Race Flags & Safety Car State

- **Status**: 📝 Planned
- **Priority**: High
- **Target Standard**: [rF2SharedMemoryMapPlugin v3.7.x](TARGET.md) (`rF2Rules` buffer @ 3 FPS + `rF2MultiRules` buffer on session callback)

---

## 1. Context & Motivation

In competitive endurance (LMU) and circuit racing (rFactor 2), race rule enforcement is vital. `rF2SharedMemoryMapPlugin` provides rich race control telemetry including:
- **Flag States**: Full Course Yellow (FCY), Sector Local Yellows, Green flag, Red flag, Blue flags, and White flag (slow vehicle / last lap).
- **Safety Car / Full Course Caution**: Safety Car deployment state, SC 3D position, distance to Safety Car, maximum/minimum delta pace during caution.
- **Pit Lane Regulations**: Pit lane open / closed state during SC periods, wave-by / lucky dog instructions, pit exit lights.
- **Frozen Order & Grid Procedures**: Starting grid ordering (Rolling Start / Standing Start), assigned formation line (Inside/Outside row), and Frozen Order sub-phases during caution laps.

`isiMotor-RawUDP-Plugin` must implement `InternalsPluginV07` callbacks to stream these critical race control events.

---

## 2. Technical Specification & SDK Hooks

### 2.1 isiMotor SDK Hooks (`InternalsPluginV07`)

```cpp
class IsiMotorRawUdpPlugin : public InternalsPluginV07 {
public:
    bool WantsTrackRulesAccess() override { return true; }
    bool AccessTrackRules(TrackRulesV01 &info) override;

    bool WantsMultiSessionRulesAccess() override { return true; }
    bool AccessMultiSessionRules(MultiSessionRulesV01 &info) override;
};
```

### 2.2 Binary Structures (`TrackRulesPacket`)

```cpp
#pragma pack(push, 4)

/**
 * Track Rules & Safety Car State Packet (SIMP Type 5)
 * Dispatched at 3 Hz and immediately upon flag transition.
 */
struct TrackRulesPacket {
    double        currentET;             // Current session elapsed time
    long          stage;                 // 0=None, 1=Formation, 2=Starting, 3=Green, 4=FullCourseYellow, 5=Red
    long          poleColumn;            // 0=left, 1=right
    long          numActions;            // Number of active race control actions
    
    // Safety Car / Pace Car Status
    bool          safetyCarExists;       // SC is present on track
    bool          safetyCarPresent;      // SC is currently deployed in front of field
    long          safetyCarLeader;       // Vehicle ID trailing behind the SC
    double        safetyCarPos[3];       // Safety Car world coordinates
    float         safetyCarSpeed;        // Safety Car velocity (m/s)
    float         minimumSpeed;          // Minimum speed for caution delta (-1 if none)
    float         maximumSpeed;          // Maximum speed for caution delta (-1 if none)
    
    // Pit Lane State
    bool          pitLaneOpen;           // True if pit lane entry is open under caution
    
    // Flags by sector (0=Sector 3, 1=Sector 1, 2=Sector 2)
    unsigned char sectorFlags[3];        // 0=Green, 1=Yellow, 2=Double Yellow
    
    // Message Center instruction string
    char          message[96];           // Translated message / instruction from game director
};

/**
 * Multi-Session Rules State Packet (SIMP Type 11)
 * Dispatched on session initialization.
 */
struct MultiSessionRulesPacket {
    long          session;               // Session identifier
    long          gridOrder;             // 0=as entered, 1=qualifying results, 2=reverse grid, etc.
    bool          fullCourseYellows;     // FCY enabled for this session
    bool          luckyDog;              // Lucky Dog / Pass-around enabled
    bool          blueFlags;             // Blue flags enabled (0=off, 1=warn, 2=penalty)
    long          leadLapsUnderYellow;   // Yellow laps count
};

#pragma pack(pop)
```

---

## 3. Frozen Order & Caution Phase Tracking

During Rolling Starts and Full Course Yellows, the plugin extracts participant target positioning:
- `mOrder`: Assigned position in line.
- `mColumn`: 0 (Inside line) or 1 (Outside line).
- `mPacePenalty`: Number of penalty positions.

This enables external apps like **Crew Chief** and spotters to give audio callouts (*"Line up on the inside behind car #42"*).

---

## 4. INI Configuration

```ini
[Streams]
; Track rules and flag events stream (~3Hz): off | unlimited | 5Hz | 3Hz | 1Hz
TrackRules=3Hz
```

---

## 5. Python Client Support (`isimotor-rawudp-client`)

```python
from isimotor_rawudp_client import IsiMotorClient, TrackRules

client = IsiMotorClient()

@client.on_rules
def handle_rules(rules: TrackRules):
    if rules.is_fcy:
        print(f"⚠️ FULL COURSE YELLOW! Max Speed: {rules.max_speed_kmh:.1f} km/h | SC Present: {rules.safety_car_present}")
    if rules.sector_flags[1] > 0:
        print("🟡 Yellow Flag in Sector 1!")
```

---

## 6. Acceptance Criteria & Definition of Done

- [ ] Upgrade plugin base class to `InternalsPluginV07`.
- [ ] Ingest and broadcast `TrackRulesV01` at ~3 Hz.
- [ ] Correctly capture Safety Car position, speed, and deployment status.
- [ ] Accurately transmit sector yellow flags and pit lane status.
- [ ] Golden unit test asserting decoding of `TrackRulesPacket` and `MultiSessionRulesPacket`.
