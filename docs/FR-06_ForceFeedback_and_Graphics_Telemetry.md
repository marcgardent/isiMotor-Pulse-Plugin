# Feature Request: FR-06 — High-Rate Force Feedback & Graphics Telemetry

- **Status**: 📝 Planned
- **Priority**: Medium
- **Target Standard**: [rF2SharedMemoryMapPlugin v3.7.x](TARGET.md) (`rF2ForceFeedback` buffer @ 400 FPS & `rF2Graphics` buffer @ 400 FPS)

---

## 1. Context & Motivation

### 1.1 Force Feedback (FFB) Stream (`ForceFeedbackV01` @ 400 Hz)
`rF2SharedMemoryMapPlugin` exposes raw physics force feedback torque computed by isiMotor at 400 FPS. This ultra-high-rate stream is utilized by:
- **Tactile Transducers & Bass Shakers**: SimHub haptic feedback effects for curb impacts, tire scrubbing, and ABS vibration.
- **Active Pedals & Motion Platforms**: Real-time steering torque load feedback for dynamic motion cues.

### 1.2 Graphics & Camera Telemetry (`GraphicsInfoV02`)
Exposes rendering camera orientation, position, FOV, and cockpit vs external view status:
- **Broadcast & Overlay Tools**: Dynamic camera tracking and picture-in-picture director views.
- **VR & Head Tracking Integrations**: Matching external overlay positions to real-time driver head movement.

---

## 2. Technical Specification & SDK Hooks

### 2.1 isiMotor SDK Hooks (`InternalsPluginV03`)

```cpp
class IsiMotorRawUdpPlugin : public InternalsPluginV07 {
public:
    // 400 Hz Force Feedback Callback
    bool ForceFeedback(double &forceValue) override;

    // Graphics & Camera Telemetry
    bool WantsGraphicsUpdates() override { return true; }
    void UpdateGraphics(const GraphicsInfoV02 &info) override;
};
```

### 2.2 Binary Structures

#### 1. Force Feedback Packet (`ForceFeedbackPacket`, SIMP Type 9)
```cpp
#pragma pack(push, 4)

struct ForceFeedbackPacket {
    double        currentET;             // Elapsed physics time
    double        forceValue;            // Normalized steering torque output (-1.0 to +1.0)
};
```

#### 2. Graphics & Camera Packet (`GraphicsPacket`, SIMP Type 10)
```cpp
struct GraphicsPacket {
    TelemVect3    camPos;                // Camera world position
    TelemVect3    camOri[3];             // Camera 3x3 orientation matrix
    HWND          hwnd;                  // Render window handle
    double        fov;                   // Field of View in degrees
    unsigned char cameraType;            // 0=cockpit, 1=onboard/chase, 2=trackside, etc.
};

#pragma pack(pop)
```

---

## 3. Rate Limiting & High-Frequency Streaming

Because FFB is updated at 400 Hz, transmitting at full rate over Wi-Fi may saturate low-bandwidth wireless links. The rate limiter allows configuring the stream from 60 Hz to 400 Hz:

```ini
[Streams]
; Force feedback stream (16 B): off | unlimited (400Hz) | 400Hz | 200Hz | 100Hz | 60Hz
ForceFeedback=off

; Graphics & camera stream (~128 B): off | unlimited (400Hz) | 60Hz | 30Hz
Graphics=off
```

---

## 4. Python Client Support (`isimotor-rawudp-client`)

```python
from isimotor_rawudp_client import IsiMotorClient, ForceFeedbackData, GraphicsData

client = IsiMotorClient()

@client.on_force_feedback
def handle_ffb(ffb: ForceFeedbackData):
    # Process 400Hz torque for tactile transducer / shaker
    if abs(ffb.force_value) > 0.8:
        print(f"High Torque Spike: {ffb.force_value:+.2f}")

@client.on_graphics
def handle_graphics(g: GraphicsData):
    print(f"Camera FOV: {g.fov:.1f}° | Cockpit: {g.is_cockpit}")
```

---

## 5. Acceptance Criteria & Definition of Done

- [ ] Implement `ForceFeedback()` hook to capture 400 Hz torque without modifying internal steering calculation.
- [ ] Implement `UpdateGraphics(const GraphicsInfoV02 &info)` hook.
- [ ] Ensure sub-microsecond transmission latency at 400 Hz on local loopback.
- [ ] Unit tests for `ForceFeedbackPacket` and `GraphicsPacket`.
