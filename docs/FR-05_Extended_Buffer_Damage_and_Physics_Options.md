# Feature Request: FR-05 — Extended Damage, Physics Options & Session Transitions

- **Status**: 📝 Planned
- **Priority**: High
- **Target Standard**: [rF2SharedMemoryMapPlugin v3.7.x](TARGET.md) (`rF2Extended` buffer @ 5 FPS & session transitions)

---

## 1. Context & Motivation

`rF2Extended` in `rF2SharedMemoryMapPlugin` is a critical derived buffer used heavily by **Crew Chief** and **SimHub** to fill in API gaps not directly provided by raw telemetry ticks:
1. **Accumulated Vehicle Damage**: Tracking body panel loss, front/rear wing aero degradation, suspension bent rods, and radiator/engine wear.
2. **Physics Aids & Realism Settings (`PhysicsOptionsV01`)**: Assisting external overlays to know whether Traction Control, ABS, Auto-Clutch, or Steering Assist are active in the vehicle.
3. **Session Lifecycle & Transition Tracking**: Reliable timestamps for session start (`mSessionStarted`, `mTicksSessionStarted`), distinguishing realtime mode between Scoring Updates and Enter/Exit callbacks (`mInRealTimeFC` vs `mInRealTimeSU`).
4. **Pit Lane Speed Limit & Direct Status**: Exposing track pit lane speed limits and race control notifications.

---

## 2. Technical Specification & SDK Hooks

### 2.1 isiMotor SDK Hooks (`InternalsPluginV02`)

```cpp
class IsiMotorRawUdpPlugin : public InternalsPluginV07 {
public:
    void SetPhysicsOptions(PhysicsOptionsV01 &options) override;
    void StartSession() override;
    void EndSession() override;
    void EnterRealtime() override;
    void ExitRealtime() override;
};
```

### 2.2 Binary Struct Layout (`ExtendedPacket`, SIMP Type 8)

```cpp
#pragma pack(push, 4)

struct PhysicsAids {
    unsigned char autoClutch;            // 0=off, 1=on
    unsigned char steeringHelp;          // 0=off, 1=low, 2=med, 3=high
    unsigned char tractionControl;       // 0=off, 1=low, 2=med, 3=high
    unsigned char antiLockBrakes;        // 0=off, 1=low, 2=med, 3=high
    unsigned char stabilityControl;      // 0=off, 1=low, 2=med, 3=high
    unsigned char autoShifting;          // 0=off, 1=upshifts, 2=downshifts, 3=all
    unsigned char oppositeLock;          // 0=off, 1=on
    unsigned char pitLaneSpeedLimiter;   // 0=off, 1=on
};

struct AccumulatedDamage {
    double        frontWingDamage;       // 0.0 (intact) to 1.0 (destroyed)
    double        rearWingDamage;        // 0.0 (intact) to 1.0 (destroyed)
    double        engineDamage;          // Accumulated engine wear/overheating
    double        radiatorDamage;        // Radiator blockage / puncture
    double        suspensionDamage[4];   // FL, FR, RL, RR suspension health
    bool          detachedWheels[4];     // Wheel detachment flags
};

/**
 * Extended Telemetry & Session Packet (SIMP Type 8)
 * Dispatched at 5 Hz and upon physics/session updates.
 */
struct ExtendedPacket {
    // Session Timestamps & Transitions
    bool          sessionStarted;        // True if active session running
    long long     ticksSessionStarted;   // High-resolution clock tick at session start
    bool          inRealTimeFC;          // In realtime reported by physics frame
    bool          inRealTimeSU;          // In realtime reported by scoring frame
    
    // Pit Lane Properties
    float         pitLaneSpeedLimitMps;  // Pit lane speed limit in m/s
    
    // Derived Damage Info
    AccumulatedDamage damage;
    
    // Active Physics Options & Driver Aids
    PhysicsAids       physicsAids;
    
    // Version & Synchronization Validation
    unsigned char pluginVersionMajor;
    unsigned char pluginVersionMinor;
    unsigned char unsubscribedBuffersMask;
};

#pragma pack(pop)
```

---

## 3. Damage Derivation Algorithm

Since raw telemetry resets some damage values upon pit stop or vehicle re-spawn, the plugin maintains an internal damage accumulator:
- **Aero & Wings**: Monitors aerodynamic drag/downforce offsets against expected baseline speeds.
- **Suspension**: Detects permanent suspension offset differences and wheel detachment events (`TelemWheelV01.mDetached`).
- **Engine**: Accumulates overheating exposure when oil/water temperatures exceed critical thresholds.

---

## 4. INI Configuration

```ini
[Streams]
; Extended state & damage stream (~5Hz): off | unlimited | 10Hz | 5Hz | 1Hz
Extended=5Hz
```

---

## 5. Python Client Support (`isimotor-rawudp-client`)

```python
from isimotor_rawudp_client import IsiMotorClient, ExtendedInfo

client = IsiMotorClient()

@client.on_extended
def handle_extended(ext: ExtendedInfo):
    print(f"Pit Speed Limit: {ext.pit_speed_limit_kmh:.0f} km/h | TC Aid: {ext.physics_aids.traction_control}")
    if ext.damage.front_wing_damage > 0.3:
        print(f"⚠️ Front Aero Damage: {ext.damage.front_wing_damage * 100:.0f}%")
```

---

## 6. Acceptance Criteria & Definition of Done

- [ ] Implement `SetPhysicsOptions` to capture active driver assists.
- [ ] Implement damage accumulation across sessions.
- [ ] Correctly capture session transition timestamps and pit lane speed limits.
- [ ] Unit test validating binary layout and decoding of `ExtendedPacket`.
