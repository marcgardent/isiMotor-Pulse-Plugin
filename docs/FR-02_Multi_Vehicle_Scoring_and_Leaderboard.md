# Feature Request: FR-02 — Multi-Vehicle Scoring & Grid Leaderboard

- **Status**: 📝 Planned
- **Priority**: High
- **Target Standard**: [rF2SharedMemoryMapPlugin v3.7.x](TARGET.md) (`rF2Scoring` buffer with up to 128 `VehicleScoringInfoV01` records at 5 FPS)

---

## 1. Context & Motivation

In rFactor 2 and Le Mans Ultimate, `ScoringInfoV01` provides global session state along with an array of up to 128 vehicles (`mVehicle[128]`). 

Currently, `isiMotor-RawUDP-Plugin` only extracts the player vehicle's timing into a 168-byte `CompactScoringPacket` (Type 2). To achieve full parity with `rF2SharedMemoryMapPlugin`, external tools (SimHub, Crew Chief, timing towers, broadcast overlays, spotters, and radar maps) require complete telemetry for all active cars on track:
- **Leaderboards & Class Rankings**: Overall position, class position, laps completed, finish status.
- **Gaps & Deltas**: Interval to car ahead, interval to leader, lap deltas.
- **Sector & Lap Timings**: Best S1/S2/Lap, Last S1/S2/Lap, Current S1/S2 for every driver.
- **Track Map & Spotter Data**: 3D world position (`mPos`), speed, heading, sector location, pit lane / garage status.
- **Driver & Car Metadata**: Driver name, team/vehicle name, class name, vehicle ID.

---

## 2. Technical Specification & Memory Structures

### 2.1 isiMotor SDK References (`include/InternalsPlugin.hpp`)

The plugin will ingest `ScoringInfoV01` from the engine callback:
```cpp
virtual bool WantsScoringUpdates() { return true; }
virtual void UpdateScoring(const ScoringInfoV01 &info);
```

### 2.2 Binary Struct Layout

#### 1. Session Metadata Header (`FullScoringSessionHeader`)
```cpp
#pragma pack(push, 4)

struct FullScoringSessionHeader {
    char          trackName[64];       // Track/circuit name
    long          session;             // 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race
    double        currentET;           // Current session elapsed time (seconds)
    double        endET;               // Ending session elapsed time (if time-limited)
    long          maxLaps;             // Max laps (if lap-limited)
    double        lapDist;             // Track lap distance in meters
    long          numVehicles;         // Number of vehicles currently active (0..128)
    unsigned char sectorFlag[3];       // Sector flags (0=green, 1=yellow, etc.)
    bool          inRealtime;          // Session in real-time mode
    char          darkCloud;           // Rain cloud factor (0..100)
    char          raining;             // Rain intensity (0..100)
    double        ambientTemp;         // Ambient temperature (°C)
    double        trackTemp;           // Track temperature (°C)
    double        windSpeed;           // Wind speed (m/s)
    double        windDirection;       // Wind direction (radians)
    double        minPathWetness;      // Track minimum wetness
    double        maxPathWetness;      // Track maximum wetness
};
```

#### 2. Individual Vehicle Record (`VehicleScoringPacketV01`)
```cpp
struct VehicleScoringPacketV01 {
    char          driverName[32];      // Driver name
    char          vehicleName[64];     // Vehicle / livery name
    char          vehicleClass[32];    // Car class (e.g. "Hypercar", "LMP2", "GT3")
    short         id;                  // Vehicle session ID (mID)
    short         totalLaps;           // Laps completed
    signed char   sector;              // Current sector (0=S3, 1=S1, 2=S2)
    signed char   finishStatus;        // 0=none, 1=finished, 2=dnf, 3=dq
    double        lapDist;             // Distance around lap in meters
    double        pathLateral;         // Distance from center of track (+left, -right)
    double        trackEdge;           // Distance from track edge
    
    double        bestSector1;         // Personal best S1
    double        bestSector2;         // Personal best S2
    double        bestLapTime;         // Personal best Lap
    double        lastSector1;         // Last lap S1
    double        lastSector2;         // Last lap S2
    double        lastLapTime;         // Last lap time
    double        curSector1;          // Current lap S1
    double        curSector2;          // Current lap S2
    
    short         numPitstops;         // Number of pit stops completed
    short         numPenalties;        // Outstanding penalties
    bool          isPlayer;            // 1 if local player car, 0 otherwise
    bool          inGarageStall;       // 1 if in garage
    bool          pitState;            // 1=pitting / in pit lane
    unsigned char place;               // Overall position (1-based)
    unsigned char classPlace;          // Class position (1-based)
    
    double        worldPosX;           // World coordinate X (for 2D radar/track map)
    double        worldPosY;           // World coordinate Y
    double        worldPosZ;           // World coordinate Z
    double        speedMps;            // Forward velocity in m/s
    
    double        timeBehindNext;      // Gap to car ahead (seconds)
    long          lapsBehindNext;      // Lap gap to car ahead
    double        timeBehindLeader;    // Gap to leader (seconds)
    long          lapsBehindLeader;    // Lap gap to leader
};

#pragma pack(pop)
```

---

## 3. Zero-Allocation UDP Slicing & Serialization

A full 128-vehicle payload is approximately:
`sizeof(FullScoringSessionHeader) + 128 * sizeof(VehicleScoringPacketV01) ≈ 160 + (128 * 280) ≈ 36 KB`.

To prevent network buffer overflow and MTU fragmentation:
1. The C++ plugin pre-allocates a static working buffer:
   `static char g_scoringBuffer[sizeof(FullScoringSessionHeader) + 128 * sizeof(VehicleScoringPacketV01)];`
2. Packets are sliced using the FR-01 framing protocol into chunks of **~1200 bytes** (containing ~4 vehicle records per slice).
3. Slices are dispatched at 5 Hz with monotonic sequence numbering.

---

## 4. Coexistence with Compact Scoring

- Both **`CompactScoring` (Type 2)** and **`FullScoring` (Type 4)** can be toggled independently in `isiMotor_RawUDP.ini`:
  ```ini
  [Streams]
  CompactScoring=off      ; Lightweight 168B single-player timing
  FullScoring=5Hz         ; Full 128-vehicle grid streaming (5Hz)
  ```

---

## 5. Python Client Implementation (`isimotor-rawudp-client`)

```python
from isimotor_rawudp_client import IsiMotorClient, ScoringSession, VehicleScoring

client = IsiMotorClient()

@client.on_full_scoring
def handle_full_scoring(session: ScoringSession, grid: list[VehicleScoring]):
    print(f"[{session.track_name}] {len(grid)} Cars on track | Leader: {grid[0].driver_name} (Class {grid[0].vehicle_class})")
    for car in grid[:5]: # Top 5
        print(f" P{car.place:2d} ({car.class_place:2d}) | {car.driver_name:20s} | Gap: {car.time_behind_leader:5.2f}s | Lap: {car.total_laps:2d}")
```

---

## 6. Acceptance Criteria & Definition of Done

- [ ] Support up to 128 vehicles streamed in real-time at 5 Hz without dropping frames.
- [ ] Correct calculation/mapping of overall positions, class positions, gaps to leader/car ahead.
- [ ] World positions (`worldPosX`, `worldPosZ`) accurate for 2D track radar rendering.
- [ ] Zero dynamic memory allocations during scoring updates.
- [ ] Unit & golden test asserting decoding of full multi-car grids in `tests/`.
