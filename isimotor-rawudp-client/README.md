# isimotor-rawudp-client

Official Python client and high-performance binary decoder for **isiMotor-RawUDP-Plugin** (compatible with **Le Mans Ultimate** and **rFactor 2**).

## 🚀 Installation

### Via GitHub URL:
```bash
pip install "git+https://github.com/<username>/isiMotor-RawUDP-Plugin.git#subdirectory=isimotor-rawudp-client"
```

### Local Editable Install:
```bash
cd isiMotor-RawUDP-Plugin/isimotor-rawudp-client
pip install -e .
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

## 🐍 Quick Start

### 1. Callback-Based Event Handling
```python
from isimotor_rawudp_client import IsiMotorClient, TelemInfo, CompactScoring

client = IsiMotorClient(host="0.0.0.0", port=5000)

@client.on_telemetry
def on_telemetry(t: TelemInfo):
    print(f"Speed: {t.forward_speed_kmh:5.1f} km/h | Gear: {t.gear_str:>2} | RPM: {t.engine_rpm:5.0f} | Fuel: {t.fuel:4.1f}L")
    fl = t.fl_wheel
    print(f"FL Temp: {fl.temperature_celsius[1]:.1f}°C | Slip: {fl.slip_ratio:.2f}")

@client.on_scoring
def on_scoring(s: CompactScoring):
    print(f"Track: {s.track_name} | Lap: {s.total_laps} | S1: {s.cur_sector1:.3f}s")

client.start()
```

### 2. Polling / Context Manager
```python
from isimotor_rawudp_client import IsiMotorClient
import time

with IsiMotorClient(port=5000) as client:
    while True:
        telem = client.get_latest_telemetry()
        if telem:
            print(f"Speed: {telem.speed_kmh:.1f} km/h")
        time.sleep(0.01)
```
