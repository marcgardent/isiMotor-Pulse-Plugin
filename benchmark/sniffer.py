#!/usr/bin/env python3
"""
isiMotor UDP Telemetry Packet Explorer & Benchmark
Built with Textual for a high-performance, responsive raw data inspector.
"""

import sys
import time
import math
import json
import struct
import socket
import select
import threading
import argparse
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple, List

# Support loading parent package
client_pkg_path = Path(__file__).resolve().parent.parent / "isimotor-rawudp-client"
if client_pkg_path.exists():
    sys.path.insert(0, str(client_pkg_path))

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Header, Footer, Static, DataTable, Label, Button, Tabs, Tab, Input
    from textual.binding import Binding
    from textual.reactive import reactive
except ImportError:
    print("\n[!] The 'textual' package is required to run the benchmark dashboard.")
    print("    Install dependencies in the benchmark environment:")
    print("      cd benchmark && uv venv && uv pip install -e ../isimotor-rawudp-client textual rich\n")
    sys.exit(1)

from isimotor_rawudp_client.models import TelemInfo, CompactScoring, SystemEvent
from isimotor_rawudp_client.decoder import decode_telemetry, decode_compact_scoring, decode_system_event


# ── Packet Stream Definitions ──────────────────────────────────────────────────
PKT_RAW_TELEMETRY   = "TelemInfoV01 (Raw Binary)"
PKT_COMPACT_SCORING = "CompactScoring (SIMP v2)"
PKT_SYSTEM_EVENT    = "SystemEvent (SIMP v3)"
PKT_FOREIGN         = "Foreign / Unknown"

TAB_TELEM   = "tab-telem"
TAB_SCORING = "tab-scoring"
TAB_EVENT   = "tab-event"
TAB_STATS   = "tab-stats"


@dataclass
class PacketStats:
    name: str
    format_type: str
    expected_size: str
    count: int = 0
    bytes_total: int = 0
    timestamps: deque = field(default_factory=lambda: deque(maxlen=300))
    intervals: deque = field(default_factory=lambda: deque(maxlen=150))
    last_timestamp: float = 0.0
    last_size: int = 0

    def record(self, size: int, now: float):
        if self.last_timestamp > 0:
            dt = (now - self.last_timestamp) * 1000.0
            self.intervals.append(dt)
        self.last_timestamp = now
        self.timestamps.append(now)
        self.count += 1
        self.bytes_total += size
        self.last_size = size

    @property
    def current_freq(self) -> float:
        now = time.time()
        recent = [t for t in self.timestamps if (now - t) <= 1.0]
        if len(recent) < 2:
            return 1.0 if len(recent) == 1 and (now - self.last_timestamp) < 1.0 else 0.0
        dt = recent[-1] - recent[0]
        return (len(recent) - 1) / dt if dt > 0 else 0.0

    @property
    def avg_interval_ms(self) -> float:
        return (sum(self.intervals) / len(self.intervals)) if self.intervals else 0.0

    @property
    def jitter_ms(self) -> float:
        if not self.intervals:
            return 0.0
        return abs(max(self.intervals) - min(self.intervals)) / 2.0

    @property
    def bandwidth_kb_s(self) -> float:
        now = time.time()
        recent_count = len([t for t in self.timestamps if (now - t) <= 1.0])
        return (recent_count * self.last_size) / 1024.0

    def reset(self):
        self.count = 0
        self.bytes_total = 0
        self.timestamps.clear()
        self.intervals.clear()
        self.last_timestamp = 0.0
        self.last_size = 0


class TelemetryEngine:
    """Non-blocking UDP receiver & packet decoder."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        self.host = host
        self.port = port
        self.start_time = time.time()
        self.total_packets = 0
        self.total_bytes = 0
        self.running = False
        self.socket: Optional[socket.socket] = None

        self.stats: Dict[str, PacketStats] = {
            PKT_RAW_TELEMETRY: PacketStats(PKT_RAW_TELEMETRY, "Binary Struct", "1904 B"),
            PKT_COMPACT_SCORING: PacketStats(PKT_COMPACT_SCORING, "Binary SIMP", "176 B"),
            PKT_SYSTEM_EVENT: PacketStats(PKT_SYSTEM_EVENT, "Binary SIMP", "6 B"),
            PKT_FOREIGN: PacketStats(PKT_FOREIGN, "Raw/Other", "Variable"),
        }

        self.latest_telemetry: Optional[TelemInfo] = None
        self.latest_scoring: Optional[CompactScoring] = None
        self.latest_event: Optional[SystemEvent] = None
        self.latest_event_time: float = 0.0

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(False)
        self.socket.bind((self.host, self.port))
        self.running = True

    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def poll(self):
        """Drains pending packets from the socket."""
        if not self.socket or not self.running:
            return

        while True:
            r, _, _ = select.select([self.socket], [], [], 0.001)
            if not r:
                break
            try:
                data, addr = self.socket.recvfrom(65535)
                self._process_packet(data, addr)
            except (BlockingIOError, socket.error):
                break

    def _process_packet(self, data: bytes, addr: Tuple[str, int]):
        now = time.time()
        size = len(data)
        self.total_packets += 1
        self.total_bytes += size

        # 1. Native Binary Telemetry (1904 bytes)
        if size == 1904:
            pkt_type = PKT_RAW_TELEMETRY
            telem = decode_telemetry(data)
            if telem:
                self.latest_telemetry = telem

        # 2. Compact Scoring (SIMP Type 2, 176 bytes)
        elif data.startswith(b"SIMP") and len(data) >= 5 and data[4] == 2:
            pkt_type = PKT_COMPACT_SCORING
            scoring = decode_compact_scoring(data)
            if scoring:
                self.latest_scoring = scoring

        # 3. System Event (SIMP Type 3, 6 bytes)
        elif data.startswith(b"SIMP") and len(data) >= 5 and data[4] == 3:
            pkt_type = PKT_SYSTEM_EVENT
            ev = decode_system_event(data)
            if ev:
                self.latest_event = ev
                self.latest_event_time = now
        else:
            pkt_type = PKT_FOREIGN

        self.stats[pkt_type].record(size, now)

    def reset_stats(self):
        self.total_packets = 0
        self.total_bytes = 0
        self.start_time = time.time()
        for s in self.stats.values():
            s.reset()


# ── Field Extractors (Key, Value, Desc) ────────────────────────────────────────

def format_value(val: Any) -> str:
    """Formats Python values cleanly for UI table presentation."""
    if val is None:
        return "[dim]-[/dim]"
    if isinstance(val, bool):
        return f"[bold {'#3fb950' if val else '#f85149'}]{val}[/]"
    if isinstance(val, float):
        return f"[bold #e3b341]{val:.4f}[/]"
    if isinstance(val, int):
        return f"[bold #58a6ff]{val}[/]"
    if isinstance(val, str):
        return f"[#a5d6ff]\"{val}\"[/]" if val else "[dim]\"\"[/dim]"
    if isinstance(val, (list, tuple)):
        items_str = ", ".join(f"{x:.2f}" if isinstance(x, float) else str(x) for x in val)
        return f"({items_str})"
    return str(val)


def extract_telemetry_rows(t: Optional[TelemInfo]) -> List[Tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for TelemInfo packet.
    """
    if t is None:
        return [
            ("status", "Waiting for packets", "[dim]No TelemInfo packet received yet[/dim]", "Start game or enable mock simulation mode")
        ]

    rows = [
        # Session & Identity
        ("slot_id", t.slot_id, format_value(t.slot_id), "Player vehicle slot index in session / multiplayer"),
        ("delta_time", t.delta_time, f"{t.delta_time:.4f} s", "Time since last physics update (seconds)"),
        ("elapsed_time", t.elapsed_time, f"{t.elapsed_time:.3f} s", "Total game session elapsed time (seconds)"),
        ("lap_number", t.lap_number, format_value(t.lap_number), "Current lap number"),
        ("lap_start_et", t.lap_start_et, f"{t.lap_start_et:.3f} s", "Session time when current lap began (seconds)"),
        ("vehicle_name", t.vehicle_name, format_value(t.vehicle_name), "Vehicle / car model identification string"),
        ("track_name", t.track_name, format_value(t.track_name), "Track / circuit identification string"),

        # Kinematics & Position
        ("pos.x", t.pos.x, f"{t.pos.x:.3f} m", "World X position (meters, left-handed)"),
        ("pos.y", t.pos.y, f"{t.pos.y:.3f} m", "World Y position / elevation (meters, +y up)"),
        ("pos.z", t.pos.z, f"{t.pos.z:.3f} m", "World Z position (meters, +z rear)"),
        ("local_vel.x", t.local_vel.x, f"{t.local_vel.x:.3f} m/s", "Local lateral velocity (+x left, m/s)"),
        ("local_vel.y", t.local_vel.y, f"{t.local_vel.y:.3f} m/s", "Local vertical velocity (+y up, m/s)"),
        ("local_vel.z", t.local_vel.z, f"{t.local_vel.z:.3f} m/s", "Local longitudinal velocity (+z rear, m/s)"),
        ("speed_mps", t.speed_mps, f"{t.speed_mps:.3f} m/s", "Calculated 3D absolute vehicle speed (m/s)"),
        ("speed_kmh", t.speed_kmh, f"{t.speed_kmh:.2f} km/h", "Calculated 3D absolute vehicle speed (km/h)"),
        ("forward_speed_mps", t.forward_speed_mps, f"{t.forward_speed_mps:.3f} m/s", "Forward speed along vehicle axis (ISO +x = isiMotor -z, m/s)"),
        ("forward_speed_kmh", t.forward_speed_kmh, f"{t.forward_speed_kmh:.2f} km/h", "Forward speed along vehicle axis (km/h)"),
        ("local_accel.x", t.local_accel.x, f"{t.local_accel.x:.3f} m/s²", "Local lateral acceleration (m/s²)"),
        ("local_accel.y", t.local_accel.y, f"{t.local_accel.y:.3f} m/s²", "Local vertical acceleration (m/s²)"),
        ("local_accel.z", t.local_accel.z, f"{t.local_accel.z:.3f} m/s²", "Local longitudinal acceleration (m/s²)"),
        ("local_rot.x", t.local_rot.x, f"{t.local_rot.x:.4f} rad/s", "Pitch rate (+x pitch up, rad/s)"),
        ("local_rot.y", t.local_rot.y, f"{t.local_rot.y:.4f} rad/s", "Yaw rate (+y yaw right, rad/s)"),
        ("local_rot.z", t.local_rot.z, f"{t.local_rot.z:.4f} rad/s", "Roll rate (+z roll right, rad/s)"),
        ("local_rot_accel.x", t.local_rot_accel.x, f"{t.local_rot_accel.x:.4f} rad/s²", "Pitch angular acceleration (rad/s²)"),
        ("local_rot_accel.y", t.local_rot_accel.y, f"{t.local_rot_accel.x:.4f} rad/s²", "Yaw angular acceleration (rad/s²)"),
        ("local_rot_accel.z", t.local_rot_accel.z, f"{t.local_rot_accel.z:.4f} rad/s²", "Roll angular acceleration (rad/s²)"),
        ("ori[0]", t.ori[0].as_tuple(), format_value(t.ori[0].as_tuple()), "Orientation matrix row 0 (lateral axis vector)"),
        ("ori[1]", t.ori[1].as_tuple(), format_value(t.ori[1].as_tuple()), "Orientation matrix row 1 (vertical axis vector)"),
        ("ori[2]", t.ori[2].as_tuple(), format_value(t.ori[2].as_tuple()), "Orientation matrix row 2 (longitudinal axis vector)"),

        # Engine & Drivetrain
        ("gear", t.gear, format_value(t.gear), "Transmission gear index (-1=Reverse, 0=Neutral, 1+=Forward)"),
        ("gear_str", t.gear_str, f"[bold #f1e05a]{t.gear_str}[/]", "Human-readable gear label ('R', 'N', '1', '2'...)"),
        ("engine_rpm", t.engine_rpm, f"{t.engine_rpm:.1f} RPM", "Engine crankshaft rotational speed (RPM)"),
        ("engine_max_rpm", t.engine_max_rpm, f"{t.engine_max_rpm:.1f} RPM", "Engine rev limiter maximum RPM"),
        ("engine_water_temp", t.engine_water_temp, f"{t.engine_water_temp:.1f} °C", "Engine cooling water / radiator temperature (°C)"),
        ("engine_oil_temp", t.engine_oil_temp, f"{t.engine_oil_temp:.1f} °C", "Engine lubrication oil temperature (°C)"),
        ("clutch_rpm", t.clutch_rpm, f"{t.clutch_rpm:.1f} RPM", "Clutch plate rotational speed (RPM)"),
        ("engine_torque", t.engine_torque, f"{t.engine_torque:.1f} N·m", "Instantaneous engine torque output (N·m)"),

        # Driver Inputs
        ("unfiltered_throttle", t.unfiltered_throttle, f"{t.unfiltered_throttle * 100:.1f} %", "Raw driver throttle pedal position [0.0 - 1.0]"),
        ("unfiltered_brake", t.unfiltered_brake, f"{t.unfiltered_brake * 100:.1f} %", "Raw driver brake pedal position [0.0 - 1.0]"),
        ("unfiltered_steering", t.unfiltered_steering, f"{t.unfiltered_steering:+.3f}", "Raw driver steering input [-1.0 (L) to +1.0 (R)]"),
        ("unfiltered_clutch", t.unfiltered_clutch, f"{t.unfiltered_clutch * 100:.1f} %", "Raw driver clutch pedal position [0.0 - 1.0]"),
        ("filtered_throttle", t.filtered_throttle, f"{t.filtered_throttle * 100:.1f} %", "Processed throttle after TC / aids [0.0 - 1.0]"),
        ("filtered_brake", t.filtered_brake, f"{t.filtered_brake * 100:.1f} %", "Processed brake after ABS / aids [0.0 - 1.0]"),
        ("filtered_steering", t.filtered_steering, f"{t.filtered_steering:+.3f}", "Processed steering input after speed sensitivity [-1.0 to +1.0]"),
        ("filtered_clutch", t.filtered_clutch, f"{t.filtered_clutch * 100:.1f} %", "Processed clutch input after anti-stall [0.0 - 1.0]"),
        ("steering_shaft_torque", t.steering_shaft_torque, f"{t.steering_shaft_torque:.2f} N·m", "Feedback torque on steering shaft column (N·m)"),

        # Suspension & Aerodynamics
        ("front_3rd_deflection", t.front_3rd_deflection, f"{t.front_3rd_deflection * 1000:.2f} mm", "Front 3rd / heave spring suspension deflection (m)"),
        ("rear_3rd_deflection", t.rear_3rd_deflection, f"{t.rear_3rd_deflection * 1000:.2f} mm", "Rear 3rd / heave spring suspension deflection (m)"),
        ("front_wing_height", t.front_wing_height, f"{t.front_wing_height * 1000:.1f} mm", "Front aerodynamic wing ride height clearance (m)"),
        ("front_ride_height", t.front_ride_height, f"{t.front_ride_height * 1000:.1f} mm", "Front chassis underbody ride height (m)"),
        ("rear_ride_height", t.rear_ride_height, f"{t.rear_ride_height * 1000:.1f} mm", "Rear chassis underbody ride height (m)"),
        ("drag", t.drag, f"{t.drag:.1f} N", "Aerodynamic drag force (Newtons)"),
        ("front_downforce", t.front_downforce, f"{t.front_downforce:.1f} N", "Front axle aerodynamic downforce (Newtons)"),
        ("rear_downforce", t.rear_downforce, f"{t.rear_downforce:.1f} N", "Rear axle aerodynamic downforce (Newtons)"),
        ("rear_brake_bias", t.rear_brake_bias, f"{t.rear_brake_bias * 100:.1f} %", "Rear brake proportion bias fraction [0.0 - 1.0]"),

        # Fuel & System Status
        ("fuel", t.fuel, f"{t.fuel:.2f} L", "Current remaining fuel volume (liters)"),
        ("fuel_capacity", t.fuel_capacity, f"{t.fuel_capacity:.1f} L", "Maximum fuel tank capacity (liters)"),
        ("current_sector", t.current_sector, format_value(t.current_sector), "Current sector index (0-based; pitlane in sign bit)"),
        ("scheduled_stops", t.scheduled_stops, format_value(t.scheduled_stops), "Number of scheduled pitstops in strategy"),
        ("overheating", t.overheating, format_value(t.overheating), "Engine overheating warning flag"),
        ("detached", t.detached, format_value(t.detached), "Detached / missing vehicle parts flag"),
        ("headlights", t.headlights, format_value(t.headlights), "Headlights active illumination state"),
        ("speed_limiter", bool(t.speed_limiter), format_value(bool(t.speed_limiter)), "Pitlane speed limiter enabled flag"),
        ("speed_limiter_available", bool(t.speed_limiter_available), format_value(bool(t.speed_limiter_available)), "Speed limiter available on vehicle flag"),
        ("anti_stall_activated", bool(t.anti_stall_activated), format_value(bool(t.anti_stall_activated)), "Anti-stall electronic aid active flag"),
        ("ignition_starter", t.ignition_starter, format_value(t.ignition_starter), "Ignition / Starter switch state (0=off, 1=ign, 2=ign+start)"),
        ("front_flap_activated", t.front_flap_activated, format_value(t.front_flap_activated), "Front active aero flap status"),
        ("rear_flap_activated", t.rear_flap_activated, format_value(t.rear_flap_activated), "Rear DRS / active aero flap status"),
        ("rear_flap_legal_status", t.rear_flap_legal_status, format_value(t.rear_flap_legal_status), "DRS legal zone status (0=disallowed, 1=detected, 2=allowed)"),
        ("front_tire_compound_index", t.front_tire_compound_index, format_value(t.front_tire_compound_index), "Front tire compound index"),
        ("rear_tire_compound_index", t.rear_tire_compound_index, format_value(t.rear_tire_compound_index), "Rear tire compound index"),
        ("front_tire_compound_name", t.front_tire_compound_name, format_value(t.front_tire_compound_name), "Front tire compound specification name"),
        ("rear_tire_compound_name", t.rear_tire_compound_name, format_value(t.rear_tire_compound_name), "Rear tire compound specification name"),
        ("turbo_boost_pressure", t.turbo_boost_pressure, f"{t.turbo_boost_pressure:.2f} kPa", "Turbocharger forced-induction boost pressure"),
        ("visual_steering_wheel_range", t.visual_steering_wheel_range, f"{t.visual_steering_wheel_range:.1f}°", "Cockpit visual steering wheel lock angle (deg)"),
        ("physical_steering_wheel_range", t.physical_steering_wheel_range, f"{t.physical_steering_wheel_range:.1f}°", "Hardware physical FFB steering lock angle (deg)"),
        ("physics_to_graphics_offset", t.physics_to_graphics_offset, format_value(t.physics_to_graphics_offset), "Offset from physics center to graphical model (x, y, z)"),
        ("dent_severity", t.dent_severity, format_value(t.dent_severity), "Body damage dent severity across 8 zones [0..2]"),
        ("last_impact_et", t.last_impact_et, f"{t.last_impact_et:.3f} s", "Session time of last recorded collision impact (s)"),
        ("last_impact_magnitude", t.last_impact_magnitude, f"{t.last_impact_magnitude:.2f}", "Magnitude / force of last collision impact"),
        ("last_impact_pos", t.last_impact_pos.as_tuple(), format_value(t.last_impact_pos.as_tuple()), "Vehicle local coordinate of last impact"),

        # Hybrid & E-Motor
        ("battery_charge_fraction", t.battery_charge_fraction, f"{t.battery_charge_fraction * 100:.1f} %", "Hybrid battery State of Charge (SoC) [0.0 - 1.0]"),
        ("electric_boost_motor_torque", t.electric_boost_motor_torque, f"{t.electric_boost_motor_torque:.1f} N·m", "Electric hybrid MGU boost motor torque (N·m)"),
        ("electric_boost_motor_rpm", t.electric_boost_motor_rpm, f"{t.electric_boost_motor_rpm:.0f} RPM", "Electric hybrid MGU motor speed (RPM)"),
        ("electric_boost_motor_temperature", t.electric_boost_motor_temperature, f"{t.electric_boost_motor_temperature:.1f} °C", "Electric hybrid motor stator temperature (°C)"),
        ("electric_boost_water_temperature", t.electric_boost_water_temperature, f"{t.electric_boost_water_temperature:.1f} °C", "Electric hybrid cooling water loop temp (°C)"),
        ("electric_boost_motor_state", t.electric_boost_motor_state, format_value(t.electric_boost_motor_state), "MGU operating state (0=off, 1=idle, 2=propulsion, 3=regen)"),
    ]

    # 4 Wheels
    wheel_labels = [("fl", "Front-Left", 0), ("fr", "Front-Right", 1), ("rl", "Rear-Left", 2), ("rr", "Rear-Right", 3)]
    for code, lbl, idx in wheel_labels:
        w = t.wheels[idx]
        rows.extend([
            (f"wheels.{code}.suspension_deflection", w.suspension_deflection, f"{w.suspension_deflection * 1000:.2f} mm", f"{lbl} suspension spring travel deflection"),
            (f"wheels.{code}.ride_height", w.ride_height, f"{w.ride_height * 1000:.1f} mm", f"{lbl} underbody clearance at wheel corner"),
            (f"wheels.{code}.susp_force", w.susp_force, f"{w.susp_force:.1f} N", f"{lbl} pushrod suspension load force (Newtons)"),
            (f"wheels.{code}.brake_temp", w.brake_temp, f"{w.brake_temp:.1f} °C", f"{lbl} brake disc rotor temperature (°C)"),
            (f"wheels.{code}.brake_pressure", w.brake_pressure, f"{w.brake_pressure * 100:.1f} %", f"{lbl} brake caliper hydraulic line pressure"),
            (f"wheels.{code}.rotation", w.rotation, f"{w.rotation:.2f} rad/s", f"{lbl} wheel angular rotational speed (rad/s)"),
            (f"wheels.{code}.lateral_patch_vel", w.lateral_patch_vel, f"{w.lateral_patch_vel:.2f} m/s", f"{lbl} lateral velocity at tire contact patch (m/s)"),
            (f"wheels.{code}.longitudinal_patch_vel", w.longitudinal_patch_vel, f"{w.longitudinal_patch_vel:.2f} m/s", f"{lbl} longitudinal contact patch speed (m/s)"),
            (f"wheels.{code}.patch_speed_kmh", w.patch_speed_kmh, f"{w.patch_speed_kmh:.1f} km/h", f"{lbl} longitudinal contact patch speed (km/h)"),
            (f"wheels.{code}.lateral_ground_vel", w.lateral_ground_vel, f"{w.lateral_ground_vel:.2f} m/s", f"{lbl} lateral velocity of track ground surface (m/s)"),
            (f"wheels.{code}.longitudinal_ground_vel", w.longitudinal_ground_vel, f"{w.longitudinal_ground_vel:.2f} m/s", f"{lbl} longitudinal ground surface speed (m/s)"),
            (f"wheels.{code}.ground_speed_kmh", w.ground_speed_kmh, f"{w.ground_speed_kmh:.1f} km/h", f"{lbl} longitudinal ground speed under tire (km/h)"),
            (f"wheels.{code}.slip_ratio", w.slip_ratio, f"{w.slip_ratio:+.3f}", f"{lbl} longitudinal tire slip ratio ((patch - ground) / ground)"),
            (f"wheels.{code}.camber", w.camber, f"{w.camber:+.4f} rad", f"{lbl} wheel camber angle (radians)"),
            (f"wheels.{code}.toe", w.toe, f"{w.toe:+.4f} rad", f"{lbl} wheel toe alignment angle (radians)"),
            (f"wheels.{code}.lateral_force", w.lateral_force, f"{w.lateral_force:.1f} N", f"{lbl} lateral cornering grip force (Newtons)"),
            (f"wheels.{code}.longitudinal_force", w.longitudinal_force, f"{w.longitudinal_force:.1f} N", f"{lbl} longitudinal drive/braking force (Newtons)"),
            (f"wheels.{code}.tire_load", w.tire_load, f"{w.tire_load:.1f} N", f"{lbl} vertical normal downward load on tire (Newtons)"),
            (f"wheels.{code}.grip_fraction", w.grip_fraction, f"{w.grip_fraction * 100:.1f} %", f"{lbl} sliding fraction of tire contact patch [0..1]"),
            (f"wheels.{code}.pressure", w.pressure, f"{w.pressure:.1f} kPa", f"{lbl} tire internal inflation pressure (kPa)"),
            (f"wheels.{code}.temperature_celsius", w.temperature_celsius, f"({w.temperature_celsius[0]:.1f}, {w.temperature_celsius[1]:.1f}, {w.temperature_celsius[2]:.1f}) °C", f"{lbl} tire surface temperatures Left/Center/Right (°C)"),
            (f"wheels.{code}.carcass_temp_celsius", w.carcass_temp_celsius, f"{w.carcass_temp_celsius:.1f} °C", f"{lbl} tire deep carcass core temperature (°C)"),
            (f"wheels.{code}.wear", w.wear, f"{w.wear * 100:.1f} %", f"{lbl} tire tread surface wear fraction [0.0 - 1.0]"),
            (f"wheels.{code}.terrain_name", w.terrain_name, format_value(w.terrain_name), f"{lbl} track surface material code from TDF file"),
            (f"wheels.{code}.surface_type", w.surface_type, format_value(w.surface_type), f"{lbl} surface grip type (0=dry, 1=wet, 2=grass, 3=dirt...)"),
            (f"wheels.{code}.flat", w.flat, format_value(w.flat), f"{lbl} punctured flat tire state"),
            (f"wheels.{code}.detached", w.detached, format_value(w.detached), f"{lbl} detached / broken off wheel state"),
            (f"wheels.{code}.vertical_tire_deflection", w.vertical_tire_deflection, f"{w.vertical_tire_deflection * 1000:.2f} mm", f"{lbl} vertical tire carcass compression (mm)"),
        ])

    return rows


def extract_scoring_rows(s: Optional[CompactScoring]) -> List[Tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for CompactScoring packet.
    """
    if s is None:
        return [
            ("status", "Waiting for packets", "[dim]No CompactScoring packet received yet[/dim]", "Scoring packets are sent at 1-5 Hz")
        ]

    session_names = {
        0: "Test Day", 1: "Practice 1", 2: "Practice 2", 3: "Practice 3", 4: "Practice 4",
        5: "Qualifying 1", 6: "Qualifying 2", 7: "Qualifying 3", 8: "Qualifying 4",
        9: "Warmup", 10: "Race 1", 11: "Race 2", 12: "Race 3", 13: "Race 4"
    }
    session_label = session_names.get(s.session, f"Session({s.session})")

    return [
        ("track_name", s.track_name, format_value(s.track_name), "Track / circuit identification string"),
        ("session", s.session, format_value(s.session), "Session numeric code (0=test, 1-4=prac, 5-8=qual, 9=warmup, 10-13=race)"),
        ("session_type", session_label, f"[bold #58a6ff]{session_label}[/]", "Decoded human-readable session type"),
        ("current_et", s.current_et, f"{s.current_et:.3f} s", "Current session elapsed time (seconds)"),
        ("lap_dist", s.lap_dist, f"{s.lap_dist:.1f} m", "Total circuit lap distance / perimeter (meters)"),
        ("max_laps", s.max_laps, format_value(s.max_laps), "Session scheduled total lap limit (0 if timed session)"),
        ("in_realtime", s.in_realtime, format_value(s.in_realtime), "Real-time driving active state on track"),
        ("total_laps", s.total_laps, format_value(s.total_laps), "Completed lap count for player vehicle"),
        ("sector", s.sector, format_value(s.sector), "Current active sector (0=Sector 3, 1=Sector 1, 2=Sector 2)"),
        ("in_garage_stall", s.in_garage_stall, format_value(s.in_garage_stall), "Vehicle inside pit garage stall flag"),
        ("count_lap_flag", s.count_lap_flag, format_value(s.count_lap_flag), "Lap validity flag (0=invalid, 1=count only, 2=valid timing)"),
        ("cur_sector1", s.cur_sector1, f"{s.cur_sector1:.3f} s" if s.cur_sector1 > 0 else "[dim]-[/dim]", "Current in-progress lap Sector 1 split time (seconds)"),
        ("cur_sector2", s.cur_sector2, f"{s.cur_sector2:.3f} s" if s.cur_sector2 > 0 else "[dim]-[/dim]", "Current in-progress lap Sector 2 cumulative time (S1 + S2, s)"),
        ("cur_sector2_individual", s.cur_sector2_individual, f"{s.cur_sector2_individual:.3f} s" if s.cur_sector2_individual > 0 else "[dim]-[/dim]", "Current in-progress lap Sector 2 standalone split duration (s)"),
        ("last_sector1", s.last_sector1, f"{s.last_sector1:.3f} s" if s.last_sector1 > 0 else "[dim]-[/dim]", "Last completed lap Sector 1 split time (seconds)"),
        ("last_sector2", s.last_sector2, f"{s.last_sector2:.3f} s" if s.last_sector2 > 0 else "[dim]-[/dim]", "Last completed lap Sector 2 cumulative time (s)"),
        ("last_sector2_individual", s.last_sector2_individual, f"{s.last_sector2_individual:.3f} s" if s.last_sector2_individual > 0 else "[dim]-[/dim]", "Last completed lap Sector 2 standalone split duration (s)"),
        ("last_sector3_individual", s.last_sector3_individual, f"{s.last_sector3_individual:.3f} s" if s.last_sector3_individual > 0 else "[dim]-[/dim]", "Last completed lap Sector 3 standalone split duration (s)"),
        ("last_lap_time", s.last_lap_time, f"[bold #3fb950]{s.last_lap_time:.3f} s[/]" if s.last_lap_time > 0 else "[dim]-[/dim]", "Last completed lap total lap time (seconds)"),
        ("best_sector1", s.best_sector1, f"{s.best_sector1:.3f} s" if s.best_sector1 > 0 else "[dim]-[/dim]", "Personal best Sector 1 split time (seconds)"),
        ("best_sector2", s.best_sector2, f"{s.best_sector2:.3f} s" if s.best_sector2 > 0 else "[dim]-[/dim]", "Personal best Sector 2 cumulative time (s)"),
        ("best_lap_time", s.best_lap_time, f"[bold #bc8cff]{s.best_lap_time:.3f} s[/]" if s.best_lap_time > 0 else "[dim]-[/dim]", "Personal best total lap time (seconds)"),
    ]


def extract_event_rows(ev: Optional[SystemEvent], event_time: float) -> List[Tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for SystemEvent packet.
    """
    if ev is None:
        return [
            ("status", "Waiting for events", "[dim]No SystemEvent packet received yet[/dim]", "System events are triggered on state transitions (Enter/Exit Realtime, Session start/end)")
        ]

    ev_time_str = time.strftime("%H:%M:%S", time.localtime(event_time)) if event_time > 0 else "-"

    return [
        ("event_id", ev.event_id, format_value(ev.event_id), "System event numeric code (1=EnterRealtime, 2=ExitRealtime, 3=StartSession, 4=EndSession)"),
        ("name", ev.name, f"[bold #58a6ff]{ev.name}[/]", "Decoded human-readable event name"),
        ("in_realtime", ev.in_realtime, format_value(ev.in_realtime), "Whether event switches driving state to active real-time"),
        ("timestamp", event_time, format_value(ev_time_str), "Local system receipt timestamp of the event"),
    ]


def extract_stats_rows(engine: TelemetryEngine) -> List[Tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for overall stream statistics and network bandwidth.
    """
    elapsed = time.time() - engine.start_time
    total_mb = engine.total_bytes / (1024.0 * 1024.0)

    rows = [
        ("connection.endpoint", f"{engine.host}:{engine.port}", f"[bold #58a6ff]{engine.host}:{engine.port}[/]", "UDP socket listening endpoint"),
        ("connection.elapsed_time", elapsed, f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d} s", "Total benchmark session elapsed time"),
        ("connection.total_packets", engine.total_packets, f"{engine.total_packets:,}", "Total packets received across all streams"),
        ("connection.total_bytes", engine.total_bytes, f"{total_mb:.2f} MB ({engine.total_bytes:,} bytes)", "Total payload volume received"),
    ]

    for st_name, st in engine.stats.items():
        prefix = st_name.split()[0].lower()
        rows.extend([
            (f"{prefix}.packets_count", st.count, f"{st.count:,}", f"{st.name} total packets received"),
            (f"{prefix}.frequency_hz", st.current_freq, f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]", f"{st.name} live packet frequency (1s window)"),
            (f"{prefix}.avg_delay_ms", st.avg_interval_ms, f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-", f"{st.name} average inter-packet arrival delay"),
            (f"{prefix}.jitter_ms", st.jitter_ms, f"±{st.jitter_ms:3.1f} ms" if st.intervals else "-", f"{st.name} packet jitter variation"),
            (f"{prefix}.bandwidth_kb_s", st.bandwidth_kb_s, f"{st.bandwidth_kb_s:5.1f} KB/s", f"{st.name} throughput bandwidth"),
        ])

    return rows


def model_to_clean_dict(obj: Any) -> Dict[str, Any]:
    """Recursively converts dataclasses/models to clean JSON-serializable dictionaries."""
    if obj is None:
        return {}
    if hasattr(obj, "__dataclass_fields__"):
        res = {}
        for f in obj.__dataclass_fields__:
            val = getattr(obj, f)
            if hasattr(val, "__dataclass_fields__"):
                res[f] = model_to_clean_dict(val)
            elif isinstance(val, (list, tuple)):
                res[f] = [model_to_clean_dict(x) if hasattr(x, "__dataclass_fields__") else x for x in val]
            else:
                res[f] = val
        return res
    return dict(obj)


# ── Mock Data Generator ────────────────────────────────────────────────────────

def mock_transmitter_loop(port: int, stop_flag: threading.Event):
    """Generates complete, realistic telemetry packets for simulation mode."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = ("127.0.0.1", port)

    buf_telemetry = bytearray(1904)
    buf_scoring = bytearray(176)
    buf_event = bytearray(6)

    # Initial scoring header
    buf_scoring[0:4] = b"SIMP"
    buf_scoring[4] = 2
    track_b = b"Circuit de Spa-Francorchamps\x00"
    buf_scoring[5:5+len(track_b)] = track_b
    struct.pack_into("<i", buf_scoring, 72, 11)   # Race session
    struct.pack_into("<d", buf_scoring, 88, 7004.0) # Lap dist
    struct.pack_into("<i", buf_scoring, 96, 25)    # Max laps
    buf_scoring[104] = 1                           # in_realtime
    struct.pack_into("<h", buf_scoring, 106, 6)    # Total laps
    struct.pack_into("<b", buf_scoring, 108, 2)    # Sector 2
    buf_scoring[110] = 2                           # Valid lap
    struct.pack_into("<d", buf_scoring, 112, 38.420)
    struct.pack_into("<d", buf_scoring, 120, 94.850)
    struct.pack_into("<d", buf_scoring, 128, 38.512)
    struct.pack_into("<d", buf_scoring, 136, 94.901)
    struct.pack_into("<d", buf_scoring, 144, 138.452)
    struct.pack_into("<d", buf_scoring, 152, 38.310)
    struct.pack_into("<d", buf_scoring, 160, 94.400)
    struct.pack_into("<d", buf_scoring, 168, 137.910)

    # Telemetry static strings
    veh_b = b"Ferrari 499P Hypercar #51\x00"
    buf_telemetry[40:40+len(veh_b)] = veh_b
    buf_telemetry[104:104+len(track_b)] = track_b
    f_comp = b"Michelin Medium Wet\x00"
    r_comp = b"Michelin Medium Wet\x00"
    buf_telemetry[636:636+len(f_comp)] = f_comp
    buf_telemetry[654:654+len(r_comp)] = r_comp

    t = 0.0
    while not stop_flag.is_set():
        t += 0.01

        # Session & timing
        struct.pack_into("<i", buf_telemetry, 0, 1)          # slot_id
        struct.pack_into("<d", buf_telemetry, 8, 0.010)      # delta_time
        struct.pack_into("<d", buf_telemetry, 16, t)         # elapsed_time
        struct.pack_into("<i", buf_telemetry, 24, 6)         # lap_number
        struct.pack_into("<d", buf_telemetry, 32, 120.0)     # lap_start_et

        # Physics
        spd = 65.0 + 25.0 * math.sin(t * 0.5)
        rpm = 5200.0 + 2400.0 * math.sin(t * 1.5)
        struct.pack_into("<ddd", buf_telemetry, 168, 1420.5, 320.1, -450.2) # pos
        struct.pack_into("<ddd", buf_telemetry, 192, 0.2 * math.sin(t), 0.0, -spd) # local_vel
        struct.pack_into("<ddd", buf_telemetry, 216, 2.5 * math.sin(t), 0.0, -1.2) # local_accel

        # Orientation
        struct.pack_into("<ddd", buf_telemetry, 240, 1.0, 0.0, 0.0)
        struct.pack_into("<ddd", buf_telemetry, 264, 0.0, 1.0, 0.0)
        struct.pack_into("<ddd", buf_telemetry, 288, 0.0, 0.0, 1.0)
        struct.pack_into("<ddd", buf_telemetry, 312, 0.02 * math.sin(t), 0.05 * math.cos(t), 0.01)

        # Engine & controls
        gear_num = 4 if spd < 75 else 5
        struct.pack_into("<i", buf_telemetry, 360, gear_num)
        struct.pack_into("<d", buf_telemetry, 368, rpm)
        struct.pack_into("<d", buf_telemetry, 376, 88.5)     # water_temp
        struct.pack_into("<d", buf_telemetry, 384, 96.2)     # oil_temp
        struct.pack_into("<d", buf_telemetry, 392, rpm)      # clutch_rpm
        struct.pack_into("<d", buf_telemetry, 544, 8600.0)   # max_rpm
        struct.pack_into("<d", buf_telemetry, 608, 560.0)    # torque

        thr = 0.5 + 0.5 * math.sin(t * 2)
        brk = max(0.0, -math.sin(t * 2))
        steer = 0.25 * math.sin(t * 0.8)
        struct.pack_into("<d", buf_telemetry, 400, thr)      # unf_thr
        struct.pack_into("<d", buf_telemetry, 408, brk)      # unf_brk
        struct.pack_into("<d", buf_telemetry, 416, steer)    # unf_str
        struct.pack_into("<d", buf_telemetry, 424, 0.0)      # unf_clutch
        struct.pack_into("<d", buf_telemetry, 432, thr * 0.98) # fil_thr
        struct.pack_into("<d", buf_telemetry, 440, brk * 0.95) # fil_brk
        struct.pack_into("<d", buf_telemetry, 448, steer)
        struct.pack_into("<d", buf_telemetry, 464, steer * 15.0) # shaft torque

        # Aero & chassis
        struct.pack_into("<d", buf_telemetry, 472, 0.015 + 0.003 * math.sin(t)) # f_3rd
        struct.pack_into("<d", buf_telemetry, 480, 0.018 + 0.004 * math.cos(t)) # r_3rd
        struct.pack_into("<d", buf_telemetry, 488, 0.045)     # f_wing
        struct.pack_into("<d", buf_telemetry, 496, 0.038)     # f_ride
        struct.pack_into("<d", buf_telemetry, 504, 0.052)     # r_ride
        struct.pack_into("<d", buf_telemetry, 512, 850.0)     # drag
        struct.pack_into("<d", buf_telemetry, 520, 1450.0)    # f_df
        struct.pack_into("<d", buf_telemetry, 528, 2100.0)    # r_df
        struct.pack_into("<d", buf_telemetry, 536, max(1.0, 50.0 - t * 0.05)) # fuel
        struct.pack_into("<d", buf_telemetry, 624, 105.0)     # fuel_capacity
        struct.pack_into("<d", buf_telemetry, 680, 0.46)      # rear_brake_bias
        struct.pack_into("<d", buf_telemetry, 688, 142.5)     # turbo_boost
        struct.pack_into("<f", buf_telemetry, 676, 450.0)     # visual_steer_range
        struct.pack_into("<f", buf_telemetry, 708, 450.0)     # physical_steer_range
        buf_telemetry[555] = 1                                # headlights
        struct.pack_into("<i", buf_telemetry, 616, 2)         # sector 2

        # Hybrid
        struct.pack_into("<d", buf_telemetry, 712, 0.76)      # battery SoC
        struct.pack_into("<d", buf_telemetry, 720, 180.0)     # eb_torque
        struct.pack_into("<d", buf_telemetry, 728, rpm * 1.3) # eb_rpm
        struct.pack_into("<d", buf_telemetry, 736, 68.5)      # eb_temp
        struct.pack_into("<d", buf_telemetry, 744, 46.2)      # eb_water_temp
        buf_telemetry[752] = 2                                # propulsion

        # 4 Wheels
        for i in range(4):
            base = 864 + i * 260
            struct.pack_into("<d", buf_telemetry, base + 0, 0.022 + 0.005 * math.sin(t * 4 + i)) # defl
            struct.pack_into("<d", buf_telemetry, base + 8, 0.045) # ride_h
            struct.pack_into("<d", buf_telemetry, base + 16, 4800.0 + 500.0 * math.sin(t + i)) # force
            struct.pack_into("<d", buf_telemetry, base + 24, 420.0 + 30.0 * i) # brake_temp
            struct.pack_into("<d", buf_telemetry, base + 32, brk) # brake_press
            struct.pack_into("<d", buf_telemetry, base + 40, spd / 0.33) # rot
            struct.pack_into("<d", buf_telemetry, base + 56, spd + 1.2 * math.sin(t * 6 + i)) # patch_spd
            struct.pack_into("<d", buf_telemetry, base + 72, spd) # ground_spd
            struct.pack_into("<d", buf_telemetry, base + 80, -0.045 if i % 2 == 0 else 0.045) # camber
            struct.pack_into("<d", buf_telemetry, base + 104, 5200.0) # tire_load
            struct.pack_into("<d", buf_telemetry, base + 112, 0.08) # grip_frac
            struct.pack_into("<d", buf_telemetry, base + 120, 168.0) # pressure (kPa)
            # Temps L/C/R in Kelvin (85°C, 92°C, 88°C)
            struct.pack_into("<ddd", buf_telemetry, base + 128, 358.15 + i*2, 365.15 + i*2, 361.15 + i*2)
            struct.pack_into("<d", buf_telemetry, base + 152, 0.94) # wear
            buf_telemetry[base + 160:base + 164] = b"ASPH"
            struct.pack_into("<d", buf_telemetry, base + 204, 362.15 + i*2) # carcass

        sock.sendto(buf_telemetry, dest)

        # Scoring @ 2 Hz
        if int(t * 100) % 50 == 0:
            struct.pack_into("<d", buf_scoring, 80, t) # current_et
            sock.sendto(buf_scoring, dest)

        # Event occasionally (on session start or when t modulo 20s == 0)
        if int(t * 100) == 10:
            buf_event[0:4] = b"SIMP"
            buf_event[4] = 3
            buf_event[5] = 1 # EnterRealtime
            sock.sendto(buf_event, dest)

        time.sleep(0.01)


# ── Textual TUI Application ───────────────────────────────────────────────────

class IsiMotorBenchmarkApp(App):
    """Raw UDP Telemetry Explorer & Benchmark for isiMotor."""

    CSS = """
    Screen {
        background: #0d1117;
        color: #c9d1d9;
    }

    #metrics-bar {
        layout: horizontal;
        height: 3;
        margin: 1 1 0 1;
        background: #161b22;
        border: tall #30363d;
    }

    .metric-box {
        width: 1fr;
        content-align: center middle;
        text-align: center;
        padding: 0 1;
    }

    #controls-container {
        layout: horizontal;
        height: 3;
        margin: 0 1;
        background: #161b22;
        border-top: solid #30363d;
        border-bottom: solid #30363d;
        align: left middle;
    }

    Tabs {
        width: auto;
        height: 100%;
        background: transparent;
    }

    #search-box {
        width: 1fr;
        height: 100%;
        margin: 0 1;
        background: #0d1117;
        border: none;
        color: #c9d1d9;
    }

    #actions-box {
        layout: horizontal;
        width: auto;
        height: 100%;
        align: right middle;
    }

    .btn-action {
        margin: 0 1;
        min-width: 13;
        height: 100%;
    }

    #table-container {
        height: 1fr;
        margin: 1 1 0 1;
        background: #161b22;
        border: round #58a6ff;
    }

    DataTable {
        height: 100%;
        width: 100%;
        background: #161b22;
    }

    DataTable > .datatable--header {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #1f6feb;
        color: #ffffff;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("m", "toggle_mock", "Toggle Mock Sim", show=True),
        Binding("c", "copy_json", "Copy JSON", show=True),
        Binding("t", "copy_table", "Copy Table", show=True),
        Binding("r", "reset_stats", "Reset Stats", show=True),
        Binding("slash", "focus_search", "Search Filter", show=True),
        Binding("1", "select_tab_telem", "Telem", show=False),
        Binding("2", "select_tab_scoring", "Scoring", show=False),
        Binding("3", "select_tab_event", "Event", show=False),
        Binding("4", "select_tab_stats", "Stats", show=False),
    ]

    active_tab = reactive(TAB_TELEM)
    search_query = reactive("")

    def __init__(self, host: str = "0.0.0.0", port: int = 5000, mock: bool = False):
        super().__init__()
        self.host = host
        self.port = port
        self.mock_enabled = mock
        self.mock_stop_event = threading.Event()
        self.mock_thread: Optional[threading.Thread] = None

        self.engine = TelemetryEngine(host=host, port=port)

        # Widget handles
        self.lbl_elapsed = Static("⏱️ Elapsed: [bold green]00:00s[/]", classes="metric-box")
        self.lbl_packets = Static("📦 Packets: [bold yellow]0[/]", classes="metric-box")
        self.lbl_rate = Static("⚡ Rate: [bold magenta]0.0 KB/s (0.0 Hz)[/]", classes="metric-box")
        self.lbl_visible_rows = Static("🔍 Fields: [bold cyan]0 / 0[/]", classes="metric-box")

        self.tabs = Tabs(
            Tab("🏎️ TelemInfo (1904 B)", id=TAB_TELEM),
            Tab("⏱️ CompactScoring (176 B)", id=TAB_SCORING),
            Tab("🔔 SystemEvent (6 B)", id=TAB_EVENT),
            Tab("📊 Stream Rates", id=TAB_STATS),
            id="packet-tabs"
        )
        self.search_input = Input(placeholder="🔍 Filter fields by name or description... (Press '/' to focus)", id="search-box")
        self.btn_copy_json = Button("📋 Copy JSON", id="btn-copy-json", variant="primary", classes="btn-action")
        self.btn_copy_table = Button("📑 Copy Table", id="btn-copy-table", variant="default", classes="btn-action")
        self.btn_mock = Button("🧪 Mock Sim", id="btn-mock", variant="success" if mock else "default", classes="btn-action")
        self.table = DataTable(cursor_type="row")

        # Cache of rows currently displayed in the table to allow fast cell updates
        self._current_table_keys: List[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="metrics-bar"):
            yield Static("🏁 [bold cyan]isiMotor UDP Explorer[/]", classes="metric-box")
            yield self.lbl_elapsed
            yield self.lbl_packets
            yield self.lbl_rate
            yield self.lbl_visible_rows
            yield Static(f"🌐 [bold cyan]{self.host}:{self.port}[/]", classes="metric-box")

        with Horizontal(id="controls-container"):
            yield self.tabs
            yield self.search_input
            with Horizontal(id="actions-box"):
                yield self.btn_copy_json
                yield self.btn_copy_table
                yield self.btn_mock

        with Container(id="table-container"):
            yield self.table

        yield Footer()

    def on_mount(self) -> None:
        self.title = "isiMotor UDP Raw Telemetry Explorer"
        self.sub_title = "Zero-Overhead Binary Struct Inspector"

        # Initialize DataTable columns
        self.table.add_column("Field Key", key="col_key", width=34)
        self.table.add_column("Current Value", key="col_val", width=32)
        self.table.add_column("Field Description & Units", key="col_desc")

        # Start UDP receiver engine
        self.engine.start()

        # Start mock simulation if requested
        if self.mock_enabled:
            self._start_mock_sim()

        # Populate initial table
        self._rebuild_table_rows()

        # High-frequency UI tick (30 FPS)
        self.timer = self.set_interval(0.033, self._update_ui)

    def _start_mock_sim(self):
        self.mock_stop_event.clear()
        self.mock_thread = threading.Thread(
            target=mock_transmitter_loop,
            args=(self.port, self.mock_stop_event),
            daemon=True
        )
        self.mock_thread.start()
        self.btn_mock.variant = "success"

    def _stop_mock_sim(self):
        if self.mock_thread and self.mock_thread.is_alive():
            self.mock_stop_event.set()
            self.mock_thread = None
        self.btn_mock.variant = "default"

    # ── Tab & Search Handlers ──────────────────────────────────────────────────

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        if event.tab and event.tab.id:
            self.active_tab = event.tab.id
            self._rebuild_table_rows()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-box":
            self.search_query = event.value.strip().lower()
            self._rebuild_table_rows()

    def action_focus_search(self) -> None:
        self.search_input.focus()

    def action_select_tab_telem(self) -> None:
        self.tabs.active = TAB_TELEM

    def action_select_tab_scoring(self) -> None:
        self.tabs.active = TAB_SCORING

    def action_select_tab_event(self) -> None:
        self.tabs.active = TAB_EVENT

    def action_select_tab_stats(self) -> None:
        self.tabs.active = TAB_STATS

    def action_toggle_mock(self) -> None:
        self.mock_enabled = not self.mock_enabled
        if self.mock_enabled:
            self._start_mock_sim()
            self.notify("Mock Telemetry Transmitter Started (@ 100Hz)", title="Simulation Active")
        else:
            self._stop_mock_sim()
            self.notify("Mock Telemetry Transmitter Stopped", title="Simulation Inactive")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-copy-json":
            self.action_copy_json()
        elif event.button.id == "btn-copy-table":
            self.action_copy_table()
        elif event.button.id == "btn-mock":
            self.action_toggle_mock()

    # ── Data Extraction Helpers ────────────────────────────────────────────────

    def _get_active_rows(self) -> List[Tuple[str, Any, str, str]]:
        """Returns the raw rows for the currently selected tab."""
        if self.active_tab == TAB_TELEM:
            return extract_telemetry_rows(self.engine.latest_telemetry)
        elif self.active_tab == TAB_SCORING:
            return extract_scoring_rows(self.engine.latest_scoring)
        elif self.active_tab == TAB_EVENT:
            return extract_event_rows(self.engine.latest_event, self.engine.latest_event_time)
        elif self.active_tab == TAB_STATS:
            return extract_stats_rows(self.engine)
        return []

    def _get_active_model_dict(self) -> Dict[str, Any]:
        """Returns clean dictionary for JSON export."""
        if self.active_tab == TAB_TELEM:
            if self.engine.latest_telemetry:
                d = model_to_clean_dict(self.engine.latest_telemetry)
                d["_computed"] = {
                    "speed_kmh": self.engine.latest_telemetry.speed_kmh,
                    "forward_speed_kmh": self.engine.latest_telemetry.forward_speed_kmh,
                    "gear_str": self.engine.latest_telemetry.gear_str,
                }
                return d
            return {"status": "No TelemInfo packet received yet"}
        elif self.active_tab == TAB_SCORING:
            if self.engine.latest_scoring:
                d = model_to_clean_dict(self.engine.latest_scoring)
                d["_computed"] = {
                    "cur_sector2_individual": self.engine.latest_scoring.cur_sector2_individual,
                    "last_sector2_individual": self.engine.latest_scoring.last_sector2_individual,
                    "last_sector3_individual": self.engine.latest_scoring.last_sector3_individual,
                }
                return d
            return {"status": "No CompactScoring packet received yet"}
        elif self.active_tab == TAB_EVENT:
            if self.engine.latest_event:
                d = model_to_clean_dict(self.engine.latest_event)
                d["name"] = self.engine.latest_event.name
                d["timestamp"] = self.engine.latest_event_time
                return d
            return {"status": "No SystemEvent packet received yet"}
        elif self.active_tab == TAB_STATS:
            rows = extract_stats_rows(self.engine)
            return {k: raw for k, raw, _, _ in rows}
        return {}

    # ── Clipboard Export Actions ───────────────────────────────────────────────

    def action_copy_json(self) -> None:
        """Copies JSON representation of currently active packet to clipboard."""
        data_dict = self._get_active_model_dict()
        json_text = json.dumps(data_dict, indent=2)
        try:
            self.copy_to_clipboard(json_text)
            self.notify(f"Copied {len(data_dict)} items from {self.active_tab} to clipboard (JSON)!", title="📋 JSON Copied")
        except Exception as e:
            self.notify(f"Could not copy to clipboard: {e}", title="Copy Error", severity="error")

    def action_copy_table(self) -> None:
        """Copies formatted table (Key, Value, Description) to clipboard."""
        rows = self._get_active_rows()
        lines = ["Key\tValue\tDescription"]
        for key, raw_val, fmt_val, desc in rows:
            # Strip rich color tags for plain text table
            clean_fmt = fmt_val.replace("[bold]", "").replace("[/bold]", "")
            clean_fmt = clean_fmt.replace("[bold #58a6ff]", "").replace("[bold #3fb950]", "").replace("[bold #f85149]", "")
            clean_fmt = clean_fmt.replace("[bold #e3b341]", "").replace("[bold #f1e05a]", "").replace("[bold #bc8cff]", "")
            clean_fmt = clean_fmt.replace("[#a5d6ff]", "").replace("[dim]", "").replace("[/dim]", "").replace("[/]", "")
            lines.append(f"{key}\t{clean_fmt}\t{desc}")

        table_text = "\n".join(lines)
        try:
            self.copy_to_clipboard(table_text)
            self.notify(f"Copied {len(rows)} table rows to clipboard (TSV)!", title="📑 Table Copied")
        except Exception as e:
            self.notify(f"Could not copy to clipboard: {e}", title="Copy Error", severity="error")

    def action_reset_stats(self) -> None:
        self.engine.reset_stats()
        self._rebuild_table_rows()
        self.notify("Statistics & packet counters reset.", title="Reset Complete")

    # ── Table Rendering & Updating ─────────────────────────────────────────────

    def _rebuild_table_rows(self) -> None:
        """Rebuilds the table rows (called on tab switch or search filter change)."""
        all_rows = self._get_active_rows()
        query = self.search_query.lower()

        if query:
            filtered_rows = [
                r for r in all_rows
                if query in r[0].lower() or query in r[3].lower() or query in str(r[1]).lower()
            ]
        else:
            filtered_rows = all_rows

        self.table.clear()
        self._current_table_keys = []

        for key, raw_val, fmt_val, desc in filtered_rows:
            self.table.add_row(f"[bold #58a6ff]{key}[/]", fmt_val, desc, key=key)
            self._current_table_keys.append(key)

        self.lbl_visible_rows.update(f"🔍 Fields: [bold cyan]{len(filtered_rows)} / {len(all_rows)}[/]")

    def _update_ui(self) -> None:
        """Periodic UI update: polls UDP socket and refreshes table cells in place."""
        if not self.is_mounted:
            return

        self.engine.poll()

        now = time.time()
        elapsed = now - self.engine.start_time
        total_mb = self.engine.total_bytes / (1024.0 * 1024.0)
        current_kb_s = sum(s.bandwidth_kb_s for s in self.engine.stats.values())
        current_total_freq = sum(s.current_freq for s in self.engine.stats.values())

        # Update Top Status Bar
        self.lbl_elapsed.update(
            f"⏱️ Elapsed: [bold green]{int(elapsed // 60):02d}:{int(elapsed % 60):02d}s[/]"
        )
        self.lbl_packets.update(
            f"📦 Packets: [bold yellow]{self.engine.total_packets:,}[/]"
        )
        self.lbl_rate.update(
            f"⚡ Rate: [bold magenta]{current_kb_s:5.1f} KB/s ({current_total_freq:4.1f} Hz)[/]"
        )

        # In-place table cell updates for smooth 30 FPS rendering
        rows = self._get_active_rows()
        row_map = {r[0]: r[2] for r in rows}

        for key in self._current_table_keys:
            if key in row_map:
                try:
                    self.table.update_cell(key, "col_val", row_map[key])
                except Exception:
                    pass

    def on_unmount(self) -> None:
        self._stop_mock_sim()
        self.engine.stop()


def main():
    parser = argparse.ArgumentParser(description="isiMotor UDP Raw Telemetry Explorer & Benchmark (Textual)")
    parser.add_argument("--host", default="0.0.0.0", help="UDP listening host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="UDP listening port (default: 5000)")
    parser.add_argument("--mock", action="store_true", help="Start with simulated mock telemetry stream enabled")
    args = parser.parse_args()

    app = IsiMotorBenchmarkApp(host=args.host, port=args.port, mock=args.mock)
    app.run()


if __name__ == "__main__":
    main()
