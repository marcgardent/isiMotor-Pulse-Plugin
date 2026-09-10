
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

### 1. Callback-Based Multi-Stream Event Handling
```python
from isimotor_rawudp_client import (
    IsiMotorClient,
    TelemInfo,
    FullScoringSession,
    TrackRulesSession,
    PitMenu,
    WeatherControl,
    ExtendedState,
    ForceFeedback,
    Graphics,
    PitAction,
)

client = IsiMotorClient(host="0.0.0.0", port=5000, inbound_port=5001)

# High-Rate 60-100Hz Vehicle Telemetry
client.on_telemetry = lambda t: print(
    f"Speed: {t.forward_speed_kmh:5.1f} km/h | Gear: {t.gear_str:>2} | RPM: {t.engine_rpm:5.0f} | Fuel: {t.fuel:4.1f}L"
)

# 128-Car Grid Scoring & Leaderboard (5Hz)
client.on_full_scoring = lambda fs: print(
    f"Leader: {fs.leaderboard[0].driver_name} | Track: {fs.track_name} | Grid Size: {fs.num_vehicles}"
)

# FCY, Safety Car & Flags (3Hz)
client.on_track_rules = lambda r: print(
    f"Safety Car: {r.is_safety_car_active} | Caution: {r.is_caution_active} | Stage: {r.stage_str}"
)

# Pit Menu Navigation (100Hz)
client.on_pit_menu = lambda p: print(
    f"Pit Menu: {p.category_name} -> {p.choice_string} ({p.choice_index + 1}/{p.num_choices})"
)

# Ambient Weather & Rain Grid (1Hz)
client.on_weather = lambda w: print(
    f"Air: {w.ambient_temp_c:.1f}°C | Rain: {w.origin_raining * 100:.0f}% | Wind: {w.wind_max_speed:.1f} m/s"
)

# Driving Aids, Damage & Penalties (5Hz)
client.on_extended_state = lambda e: print(
    f"TC: {e.physics.traction_control_str} | ABS: {e.physics.anti_lock_brakes_str} | Damage: {e.accumulated_impact_magnitude:,.0f} N·s"
)

# Ultra-High-Rate FFB (400Hz)
client.on_force_feedback = lambda f: print(f"FFB Torque: {f.percentage:.1f}% ({f.force_value:+.3f})")

client.start()
```

### 2. Le Mans Ultimate (LMU) & WEC Hypercar Native Extensions
```python
@client.on_telemetry
def on_lmu_telemetry(t: TelemInfo):
    # Base isiMotor Dynamics
    print(f"Speed: {t.speed_kmh:.1f} km/h | Throttle: {t.unfiltered_throttle * 100:.0f}%")

    # WEC Hypercar Virtual Energy & Live Regen
    if t.lmu.has_hypercar_energy:
        print(f"Hypercar: {t.lmu.vehicle_model}")
        print(f"Virtual Energy: {t.lmu.virtual_energy * 100:.1f}% | Regen: {t.lmu.regen_kw:.1f} kW")

    # Onboard ECU & Electronic Aids (LMU native)
    if t.ecu.has_tc:
        print(
            f"TC: {t.ecu.tc_level}/{t.ecu.tc_max} | Cut: {t.ecu.tc_cut} | Slip: {t.ecu.tc_slip} | Active: {t.ecu.tc_active}"
        )
    if t.ecu.has_abs:
        print(f"ABS: {t.ecu.abs_level}/{t.ecu.abs_max} | Active: {t.ecu.abs_active}")
    if t.ecu.has_motor_map:
        print(f"Engine Map: {t.ecu.motor_map}/{t.ecu.motor_map_max} | Migration: {t.ecu.brake_migration}")

    # Tire Compound Enums & Brake Disc Wear
    print(
        f"Front-Left Compound: {t.fl_wheel.lmu.compound_type} | Brake Thickness: {t.fl_wheel.lmu.brake_wear_meters * 1000:.1f} mm"
    )


@client.on_full_scoring
def on_lmu_scoring(s: FullScoringSession):
    # Dynamic Track Rubbering & Solar Time of Day
    print(
        f"Track Time: {s.lmu.time_of_day_str} | Grip Level: {s.lmu.grip_fraction * 100:.0f}% ({s.lmu.track_grip_level})"
    )

    # Live Opponent Fuel Fraction & Track Limits Penalties
    for car in s.leaderboard:
        print(
            f"P{car.place} {car.driver_name} — Fuel: {car.lmu.fuel_fraction * 100:.1f}% | Cuts: {car.lmu.track_limits_steps}"
        )
```

### 3. Bi-Directional Hardware & Weather Control (Inbound)
```python
# Navigate In-Game Pit Menu
client.send_pit_action(PitAction.MENU_DOWN)
client.send_pit_action(PitAction.MENU_NEXT)
client.send_pit_action(PitAction.MENU_SELECT)

# Trigger Hardware Car Inputs
client.send_hw_control("TCIncrease", control_value=1.0, duration_ms=50)
client.send_hw_control("ABSDecrease", control_value=1.0, duration_ms=50)
client.send_hw_control("HeadlightsToggle", control_value=1.0, duration_ms=50)

# Inject Dynamic Weather Scenarios
client.send_weather_override(ambient_temp=30.0, raining=0.75, min_path_wetness=0.6)
```

### 4. Synchronous Polling / Context Manager
```python
with IsiMotorClient(port=5000) as client:
    while True:
        telem = client.get_latest_telemetry()
        rules = client.get_latest_track_rules()
        if telem:
            print(f"RPM: {telem.engine_rpm} | Speed: {telem.speed_kmh:.1f} km/h")
            if telem.lmu.has_hypercar_energy:
                print(f"Virtual Energy: {telem.lmu.virtual_energy * 100:.1f}%")
        time.sleep(0.01)
```

---

## 📦 Installer API (`isimotor_rawudp_client.install`)

The package also bundles the compiled `isiMotor_RawUDP.dll` and exposes a public API to detect Steam installations of Le Mans Ultimate / rFactor 2, install or remove the plugin DLL, and read/write its `CustomPluginVariables.JSON` / `Settings.JSON` configuration — no need for the Manager TUI to automate a setup flow.

```python
from isimotor_rawudp_client.install import (
    detect_game_installations,  # -> {"LMU": [Path, ...], "rF2": [Path, ...]}
    copy_and_install_dll,  # -> (success, message, installed_paths)
    uninstall_plugin,  # -> bool
    get_configuration_overview,  # -> structured dict (DLL status, per-game JSON status)
    read_plugin_json_variables,  # -> dict of current plugin variables
    write_plugin_json_variables,  # -> (success, message)
    save_configuration_to_all_games,  # -> (success, message, saved_paths)
    DEFAULT_PLUGIN_VARIABLES,  # default CustomPluginVariables.JSON values
    SUPPORTED_GAMES,  # {"LMU": {...}, "rF2": {...}}
)

# Detect installed games via Steam's libraryfolders.vdf
games = detect_game_installations()

# Install the bundled DLL + configure JSON into every detected game
success, message, installed_paths = copy_and_install_dll()
```

A CLI is also available, installed as `isi-install` / `isi-installer` (or `python -m isimotor_rawudp_client.install.cli`):

```bash
isi-install --status      # List detected games and installation status
isi-install               # Install the DLL + configure JSON on all detected games
isi-install --uninstall   # Remove the DLL from all detected games
isi-install --target-dir "/path/to/game"   # Install into a manual/custom path
```
