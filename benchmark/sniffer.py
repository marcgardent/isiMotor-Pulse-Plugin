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

from isimotor_rawudp_client.models import (
    TelemInfo,
    CompactScoring,
    FullScoringSession,
    VehicleScoring,
    TrackRulesParticipant,
    TrackRulesSession,
    PitMenu,
    WeatherControl,
    SystemEvent,
)
from isimotor_rawudp_client.decoder import (
    decode_telemetry,
    decode_compact_scoring,
    decode_full_scoring,
    decode_track_rules,
    decode_pit_menu,
    decode_weather,
    decode_system_event,
    decode_header,
    HEADER_SIZE,
)


# ── Packet Stream Definitions ──────────────────────────────────────────────────
PKT_RAW_TELEMETRY   = "TelemInfoV01 (Raw Binary)"
PKT_COMPACT_SCORING = "CompactScoring (SIMP v2)"
PKT_FULL_SCORING    = "FullScoring (SIMP v4 Sliced)"
PKT_TRACK_RULES     = "TrackRules (SIMP v5 Sliced)"
PKT_PIT_MENU        = "PitMenu (SIMP v6)"
PKT_WEATHER         = "Weather (SIMP v7)"
PKT_SYSTEM_EVENT    = "SystemEvent (SIMP v3)"
PKT_FOREIGN         = "Foreign / Unknown"

TAB_TELEM   = "tab-telem"
TAB_SCORING = "tab-scoring"
TAB_RULES   = "tab-rules"
TAB_PIT     = "tab-pit"
TAB_WEATHER = "tab-weather"
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
        if not self.timestamps or (now - self.last_timestamp) > 2.0:
            return 0.0
        recent = [t for t in self.timestamps if (now - t) <= 1.5]
        if len(recent) >= 2:
            dt = recent[-1] - recent[0]
            if dt > 0:
                return (len(recent) - 1) / dt
        if self.intervals:
            avg_ms = sum(list(self.intervals)[-10:]) / min(len(self.intervals), 10)
            if avg_ms > 0:
                return 1000.0 / avg_ms
        return 0.0

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
            PKT_RAW_TELEMETRY: PacketStats(PKT_RAW_TELEMETRY, "Binary Struct", "1888/1904 B"),
            PKT_COMPACT_SCORING: PacketStats(PKT_COMPACT_SCORING, "Binary SIMP", "168 B"),
            PKT_FULL_SCORING: PacketStats(PKT_FULL_SCORING, "Sliced SIMP", "Multi-KB"),
            PKT_TRACK_RULES: PacketStats(PKT_TRACK_RULES, "Sliced SIMP", "Multi-KB"),
            PKT_PIT_MENU: PacketStats(PKT_PIT_MENU, "Binary SIMP", "76 B"),
            PKT_WEATHER: PacketStats(PKT_WEATHER, "Binary SIMP", "108 B"),
            PKT_SYSTEM_EVENT: PacketStats(PKT_SYSTEM_EVENT, "Binary SIMP", "6 B"),
            PKT_FOREIGN: PacketStats(PKT_FOREIGN, "Raw/Other", "Variable"),
        }

        self.latest_telemetry: Optional[TelemInfo] = None
        self.latest_scoring: Optional[CompactScoring] = None
        self.latest_full_scoring: Optional[FullScoringSession] = None
        self.latest_track_rules: Optional[TrackRulesSession] = None
        self.latest_pit_menu: Optional[PitMenu] = None
        self.latest_weather: Optional[WeatherControl] = None
        self.latest_event: Optional[SystemEvent] = None
        self.latest_event_time: float = 0.0
        self.reassembly_buffers: Dict[tuple, dict] = {}
        self.last_cleanup_time: float = 0.0

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

        # Cleanup stale multipart frame fragments
        if now - self.last_cleanup_time > 1.0:
            self.last_cleanup_time = now
            stale = [k for k, v in self.reassembly_buffers.items() if now - v.get("timestamp", 0) > 1.0]
            for k in stale:
                del self.reassembly_buffers[k]

        pkt_type = PKT_FOREIGN

        # 1. Standardized 24-byte Header
        if data.startswith(b"SIMP") and size >= HEADER_SIZE and data[4] == 1:
            hdr = decode_header(data)
            if hdr:
                payload = data[HEADER_SIZE : HEADER_SIZE + hdr.payload_size]
                if hdr.packet_type == 1:
                    pkt_type = PKT_RAW_TELEMETRY
                    telem = decode_telemetry(payload)
                    if telem:
                        self.latest_telemetry = telem
                elif hdr.packet_type == 2:
                    pkt_type = PKT_COMPACT_SCORING
                    scoring = decode_compact_scoring(payload)
                    if scoring:
                        self.latest_scoring = scoring
                elif hdr.packet_type == 3:
                    pkt_type = PKT_SYSTEM_EVENT
                    ev = decode_system_event(payload)
                    if ev:
                        self.latest_event = ev
                        self.latest_event_time = now
                elif hdr.packet_type == 4:
                    pkt_type = PKT_FULL_SCORING
                    if hdr.total_chunks == 1:
                        fs = decode_full_scoring(payload)
                        if fs:
                            self.latest_full_scoring = fs
                    else:
                        key = (hdr.packet_type, hdr.sequence_number)
                        if key not in self.reassembly_buffers:
                            self.reassembly_buffers[key] = {
                                "total_chunks": hdr.total_chunks,
                                "chunks": {},
                                "timestamp": now,
                            }
                        buf = self.reassembly_buffers[key]
                        buf["chunks"][hdr.chunk_index] = payload
                        if len(buf["chunks"]) == buf["total_chunks"]:
                            ordered = [buf["chunks"][i] for i in range(buf["total_chunks"]) if i in buf["chunks"]]
                            del self.reassembly_buffers[key]
                            fs = decode_full_scoring(b"".join(ordered))
                            if fs:
                                self.latest_full_scoring = fs
                elif hdr.packet_type == 5:
                    pkt_type = PKT_TRACK_RULES
                    if hdr.total_chunks == 1:
                        tr = decode_track_rules(payload)
                        if tr:
                            self.latest_track_rules = tr
                    else:
                        key = (hdr.packet_type, hdr.sequence_number)
                        if key not in self.reassembly_buffers:
                            self.reassembly_buffers[key] = {
                                "total_chunks": hdr.total_chunks,
                                "chunks": {},
                                "timestamp": now,
                            }
                        buf = self.reassembly_buffers[key]
                        buf["chunks"][hdr.chunk_index] = payload
                        if len(buf["chunks"]) == buf["total_chunks"]:
                            ordered = [buf["chunks"][i] for i in range(buf["total_chunks"]) if i in buf["chunks"]]
                            del self.reassembly_buffers[key]
                            tr = decode_track_rules(b"".join(ordered))
                            if tr:
                                self.latest_track_rules = tr
                elif hdr.packet_type == 6:
                    pkt_type = PKT_PIT_MENU
                    pm = decode_pit_menu(payload)
                    if pm:
                        self.latest_pit_menu = pm
                elif hdr.packet_type == 7:
                    pkt_type = PKT_WEATHER
                    w = decode_weather(payload)
                    if w:
                        self.latest_weather = w

        # 2. Legacy Raw Telemetry
        elif size >= 1888:
            pkt_type = PKT_RAW_TELEMETRY
            telem = decode_telemetry(data)
            if telem:
                self.latest_telemetry = telem

        # 3. Legacy Compact Scoring (168/176 bytes)
        elif data.startswith(b"SIMP") and size >= 5 and data[4] == 2:
            pkt_type = PKT_COMPACT_SCORING
            scoring = decode_compact_scoring(data)
            if scoring:
                self.latest_scoring = scoring

        # 4. Legacy System Event (6 bytes)
        elif data.startswith(b"SIMP") and size >= 5 and data[4] == 3:
            pkt_type = PKT_SYSTEM_EVENT
            ev = decode_system_event(data)
            if ev:
                self.latest_event = ev
                self.latest_event_time = now

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


def extract_telemetry_rows(t: Optional[TelemInfo], st: Optional[PacketStats] = None) -> List[Tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for TelemInfo packet.
    """
    rows = []

    # Channel / Stream Diagnostics
    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        jitter_str = f"±{st.jitter_ms:3.1f} ms" if st.intervals else "-"
        rows.extend([
            ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of TelemInfo packet stream"),
            ("_channel.packets_count", st.count, f"{st.count:,}", "Total TelemInfo packets received on this channel"),
            ("_channel.avg_delay_ms", st.avg_interval_ms, delay_str, "Average arrival delay between consecutive TelemInfo packets"),
            ("_channel.jitter_ms", st.jitter_ms, jitter_str, "TelemInfo packet arrival jitter variation"),
            ("_channel.bandwidth_kb_s", st.bandwidth_kb_s, f"{st.bandwidth_kb_s:5.1f} KB/s", "Instantaneous bandwidth for TelemInfo stream"),
        ])

    if t is None:
        rows.append(
            ("status", "Waiting for packets", "[dim]No TelemInfo packet received yet[/dim]", "Start game or enable mock simulation mode")
        )
        return rows

    rows.extend([
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
    ])

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


def extract_scoring_rows(
    s: Optional[CompactScoring],
    fs: Optional[FullScoringSession] = None,
    st: Optional[PacketStats] = None,
) -> List[Tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for CompactScoring and FullScoringSession streams.
    """
    rows = []

    # Channel / Stream Diagnostics
    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend([
            ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of Scoring stream"),
            ("_channel.packets_count", st.count, f"{st.count:,}", "Total Scoring packets received on this channel"),
            ("_channel.avg_delay_ms", st.avg_interval_ms, delay_str, "Average arrival delay between consecutive Scoring packets"),
            ("_channel.bandwidth_kb_s", st.bandwidth_kb_s, f"{st.bandwidth_kb_s:5.1f} KB/s", "Instantaneous bandwidth for Scoring stream"),
        ])

    session_names = {
        0: "Test Day", 1: "Practice 1", 2: "Practice 2", 3: "Practice 3", 4: "Practice 4",
        5: "Qualifying 1", 6: "Qualifying 2", 7: "Qualifying 3", 8: "Qualifying 4",
        9: "Warmup", 10: "Race 1", 11: "Race 2", 12: "Race 3", 13: "Race 4"
    }

    # 1. Full Multi-Car Grid Scoring (SIMP Type 4)
    if fs is not None:
        session_label = session_names.get(fs.session, f"Session({fs.session})")
        rows.extend([
            ("grid.track_name", fs.track_name, format_value(fs.track_name), "Track / circuit identification string"),
            ("grid.session_type", session_label, f"[bold #58a6ff]{session_label}[/]", "Current session type"),
            ("grid.game_phase", fs.game_phase_str, f"[bold #3fb950]{fs.game_phase_str}[/]", "Session game phase (Garage, Warmup, GreenFlag, FCY...)"),
            ("grid.current_et", fs.current_et, f"{fs.current_et:.3f} s", "Session elapsed time"),
            ("grid.end_et", fs.end_et, f"{fs.end_et:.1f} s", "Session end elapsed time"),
            ("grid.num_vehicles", fs.num_vehicles, f"[bold #f1e05a]{fs.num_vehicles}[/]", "Active vehicles in session / grid"),
            ("grid.ambient_temp", fs.ambient_temp, f"{fs.ambient_temp:.1f} °C", "Ambient air temperature"),
            ("grid.track_temp", fs.track_temp, f"{fs.track_temp:.1f} °C", "Track surface temperature"),
            ("grid.raining", fs.raining, f"{fs.raining * 100:.1f} %", "Rain intensity"),
            ("grid.dark_cloud", fs.dark_cloud, f"{fs.dark_cloud * 100:.1f} %", "Cloud cover darkness"),
        ])

        # Leaderboard entries
        for rank, v in enumerate(fs.leaderboard, start=1):
            tag = f"car[{rank:02d}]"
            player_marker = " [bold #3fb950](PLAYER)[/]" if v.is_player else ""
            pit_str = f" [bold #f85149][PIT - {v.pit_state_str}][/]" if v.in_pits else ""
            gap_str = f"+{v.time_behind_leader:.3f} s" if (v.time_behind_leader > 0 and rank > 1) else ("LEADER" if rank == 1 else "-")
            best_lap_str = f"{v.best_lap_time:.3f} s" if v.best_lap_time > 0 else "-"
            last_lap_str = f"{v.last_lap_time:.3f} s" if v.last_lap_time > 0 else "-"

            rows.extend([
                (f"{tag}.driver", v.driver_name, f"[bold]{v.driver_name}[/]{player_marker}{pit_str}", f"P{v.place} | {v.vehicle_name} ({v.vehicle_class})"),
                (f"{tag}.position", v.place, f"P{v.place}", f"Current race position"),
                (f"{tag}.laps", v.total_laps, format_value(v.total_laps), f"Completed laps | Sector {v.sector}"),
                (f"{tag}.gap_leader", v.time_behind_leader, gap_str, "Gap to session leader (seconds)"),
                (f"{tag}.best_lap", v.best_lap_time, best_lap_str, "Personal best lap time"),
                (f"{tag}.last_lap", v.last_lap_time, last_lap_str, "Last completed lap time"),
            ])
        return rows

    # 2. Compact Scoring Fallback (SIMP Type 2)
    if s is not None:
        session_label = session_names.get(s.session, f"Session({s.session})")
        rows.extend([
            ("track_name", s.track_name, format_value(s.track_name), "Track / circuit identification string"),
            ("session", s.session, format_value(s.session), "Session numeric code"),
            ("session_type", session_label, f"[bold #58a6ff]{session_label}[/]", "Decoded session type"),
            ("current_et", s.current_et, f"{s.current_et:.3f} s", "Current session elapsed time (seconds)"),
            ("lap_dist", s.lap_dist, f"{s.lap_dist:.1f} m", "Total circuit lap distance (meters)"),
            ("max_laps", s.max_laps, format_value(s.max_laps), "Session scheduled lap limit"),
            ("in_realtime", s.in_realtime, format_value(s.in_realtime), "Real-time driving active state on track"),
            ("total_laps", s.total_laps, format_value(s.total_laps), "Completed lap count for player vehicle"),
            ("sector", s.sector, format_value(s.sector), "Current active sector"),
            ("in_garage_stall", s.in_garage_stall, format_value(s.in_garage_stall), "Vehicle inside pit garage stall flag"),
            ("count_lap_flag", s.count_lap_flag, format_value(s.count_lap_flag), "Lap validity flag"),
            ("cur_sector1", s.cur_sector1, f"{s.cur_sector1:.3f} s" if s.cur_sector1 > 0 else "[dim]-[/dim]", "Current lap S1 split time"),
            ("cur_sector2", s.cur_sector2, f"{s.cur_sector2:.3f} s" if s.cur_sector2 > 0 else "[dim]-[/dim]", "Current lap S2 split time"),
            ("last_lap_time", s.last_lap_time, f"[bold #3fb950]{s.last_lap_time:.3f} s[/]" if s.last_lap_time > 0 else "[dim]-[/dim]", "Last lap total time"),
            ("best_lap_time", s.best_lap_time, f"[bold #bc8cff]{s.best_lap_time:.3f} s[/]" if s.best_lap_time > 0 else "[dim]-[/dim]", "Personal best lap time"),
        ])
        return rows

    rows.append(
        ("status", "Waiting for packets", "[dim]No Scoring packet received yet[/dim]", "Scoring packets are streamed at 1-5 Hz")
    )
    return rows


def extract_event_rows(ev: Optional[SystemEvent], st: Optional[PacketStats] = None, event_time: float = 0.0) -> List[Tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for SystemEvent packet.
    """
    rows = []

    if st is not None:
        rows.extend([
            ("_channel.packets_count", st.count, f"{st.count:,}", "Total SystemEvent packets received on this channel"),
            ("_channel.bandwidth_kb_s", st.bandwidth_kb_s, f"{st.bandwidth_kb_s:5.1f} KB/s", "Instantaneous bandwidth for SystemEvent stream"),
        ])

    if ev is None:
        rows.append(
            ("status", "Waiting for events", "[dim]No SystemEvent packet received yet[/dim]", "System events are triggered on state transitions (Enter/Exit Realtime, Session start/end)")
        )
        return rows

    ev_time_str = time.strftime("%H:%M:%S", time.localtime(event_time)) if event_time > 0 else "-"

    rows.extend([
        ("event_id", ev.event_id, format_value(ev.event_id), "System event numeric code (1=EnterRealtime, 2=ExitRealtime, 3=StartSession, 4=EndSession)"),
        ("name", ev.name, f"[bold #58a6ff]{ev.name}[/]", "Decoded human-readable event name"),
        ("in_realtime", ev.in_realtime, format_value(ev.in_realtime), "Whether event switches driving state to active real-time"),
        ("timestamp", event_time, format_value(ev_time_str), "Local system receipt timestamp of the event"),
    ])

    return rows


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


def extract_track_rules_rows(
    rules: Optional[TrackRulesSession], st: Optional[PacketStats] = None
) -> List[Tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for TrackRulesSession packet."""
    rows = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend([
            ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of TrackRules stream"),
            ("_channel.packets_count", st.count, f"{st.count:,}", "Total TrackRules packets received"),
            ("_channel.avg_delay_ms", st.avg_interval_ms, delay_str, "Average arrival delay between TrackRules packets"),
            ("_channel.bandwidth_kb_s", st.bandwidth_kb_s, f"{st.bandwidth_kb_s:5.1f} KB/s", "Instantaneous bandwidth for TrackRules stream"),
        ])

    if rules is None:
        rows.append(
            ("status", "Waiting for packets", "[dim]No TrackRules packet received yet[/dim]", "Active during caution / safety car / formation laps")
        )
        return rows

    rows.extend([
        ("session.stage", rules.stage_str, f"[bold #58a6ff]{rules.stage_str}[/]", "Current race stage (Formation, Normal, Caution)"),
        ("session.pole_column", rules.pole_column_str, format_value(rules.pole_column_str), "Pole position lane/column"),
        ("session.num_participants", rules.num_participants, format_value(rules.num_participants), "Total active participant cars in track order"),
        ("session.yellow_flag_detected", rules.yellow_flag_detected, format_value(rules.yellow_flag_detected), "Yellow flag / caution condition detected"),
        ("session.is_caution_active", rules.is_caution_active, format_value(rules.is_caution_active), "Full Course Yellow / Caution active"),
        ("session.is_safety_car_active", rules.is_safety_car_active, format_value(rules.is_safety_car_active), "Safety car deployed on track"),
        ("safety_car.laps", rules.safety_car_laps, format_value(rules.safety_car_laps), "Safety car caution laps completed"),
        ("safety_car.lap_dist", rules.safety_car_lap_dist, f"{rules.safety_car_lap_dist:.1f} m", "Safety car track distance position (m)"),
        ("safety_car.speed_kmh", rules.safety_car_speed * 3.6, f"{rules.safety_car_speed * 3.6:.1f} km/h", "Safety car target speed"),
        ("session.message", rules.message, format_value(rules.message), "Global race control message"),
    ])

    for i, p in enumerate(rules.participants):
        pfx = f"participant[{i}]."
        rows.extend([
            (f"{pfx}id", p.id, format_value(p.id), f"Car slot ID (Place P{p.place})"),
            (f"{pfx}place", p.place, f"P{p.place}", f"1-based track position"),
            (f"{pfx}frozen_order", p.frozen_order, format_value(p.frozen_order), f"0-based order when caution was called"),
            (f"{pfx}column", p.column_str, format_value(p.column_str), f"Assigned column/lane"),
            (f"{pfx}pits_open", p.pits_open_bool, format_value(p.pits_open_bool), f"Pits open for this vehicle"),
            (f"{pfx}up_to_speed", p.up_to_speed, format_value(p.up_to_speed), f"Vehicle can be followed safely"),
            (f"{pfx}message", p.message, format_value(p.message), f"Individual driver instruction"),
        ])

    return rows


def extract_pit_menu_rows(
    pit: Optional[PitMenu], st: Optional[PacketStats] = None
) -> List[Tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for PitMenu packet."""
    rows = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend([
            ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of PitMenu stream"),
            ("_channel.packets_count", st.count, f"{st.count:,}", "Total PitMenu packets received"),
            ("_channel.avg_delay_ms", st.avg_interval_ms, delay_str, "Average arrival delay between PitMenu packets"),
            ("_channel.bandwidth_kb_s", st.bandwidth_kb_s, f"{st.bandwidth_kb_s:5.1f} KB/s", "Instantaneous bandwidth for PitMenu stream"),
        ])

    if pit is None:
        rows.append(
            ("status", "Waiting for packets", "[dim]No PitMenu packet received yet[/dim]", "Pit menu state streamed @ 100Hz")
        )
        return rows

    rows.extend([
        ("pit_menu.category_index", pit.category_index, format_value(pit.category_index), "Current category index"),
        ("pit_menu.category_name", pit.category_name, f"[bold #58a6ff]{pit.category_name}[/]", "Current pit menu category name (e.g. Tires, Fuel, Aero)"),
        ("pit_menu.choice_index", pit.choice_index, format_value(pit.choice_index), "Current choice index within category"),
        ("pit_menu.choice_string", pit.choice_string, f"[bold #3fb950]{pit.choice_string}[/]", "Selected choice / setting value"),
        ("pit_menu.num_choices", pit.num_choices, format_value(pit.num_choices), "Total available options in category"),
        ("pit_menu.is_available", pit.is_available, format_value(pit.is_available), "Pit menu active / accessible"),
    ])

    return rows


def extract_weather_rows(
    w: Optional[WeatherControl], st: Optional[PacketStats] = None
) -> List[Tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for WeatherControl packet."""
    rows = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend([
            ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of Weather stream"),
            ("_channel.packets_count", st.count, f"{st.count:,}", "Total Weather packets received"),
            ("_channel.avg_delay_ms", st.avg_interval_ms, delay_str, "Average arrival delay between Weather packets"),
            ("_channel.bandwidth_kb_s", st.bandwidth_kb_s, f"{st.bandwidth_kb_s:5.1f} KB/s", "Instantaneous bandwidth for Weather stream"),
        ])

    if w is None:
        rows.append(
            ("status", "Waiting for packets", "[dim]No Weather packet received yet[/dim]", "Environmental conditions streamed @ 1Hz")
        )
        return rows

    rows.extend([
        ("weather.et", w.et, f"{w.et:.3f} s", "Session time when weather takes effect"),
        ("weather.cloudiness", w.cloudiness, f"{w.cloudiness * 100:.1f} %", "General cloud cover (0% clear, 100% dark overcast)"),
        ("weather.ambient_temp_c", w.ambient_temp_c, f"[bold #e3b341]{w.ambient_temp_c:.1f} °C[/]", "Ambient air temperature (Celsius)"),
        ("weather.ambient_temp_k", w.ambient_temp_k, f"{w.ambient_temp_k:.2f} K", "Ambient air temperature (Kelvin)"),
        ("weather.wind_max_speed", w.wind_max_speed, f"{w.wind_max_speed:.1f} m/s ({w.wind_max_speed * 3.6:.1f} km/h)", "Maximum ground wind speed"),
        ("weather.origin_raining", w.origin_raining, f"[bold #58a6ff]{w.origin_raining * 100:.1f} %[/]", "Rain intensity at track origin [1][1] (0.0 to 1.0)"),
        ("weather.apply_cloudiness_instantly", w.apply_cloudiness_instantly, format_value(w.apply_cloudiness_instantly), "Instantaneous cloud change flag"),
    ])

    for r in range(3):
        for c in range(3):
            val = w.raining[r][c]
            rows.append((f"weather.raining[{r}][{c}]", val, f"{val * 100:.1f} %", f"Rain intensity at track node grid position ({r}, {c})"))

    return rows


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


# ── Mock Data Generator ────────────────────────────────────────────────────────

def mock_transmitter_loop(port: int, stop_flag: threading.Event):
    """Generates complete, realistic telemetry packets for simulation mode."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = ("127.0.0.1", port)

    buf_telemetry = bytearray(1888)
    buf_scoring = bytearray(168)
    buf_event = bytearray(6)

    # Initial scoring header
    buf_scoring[0:4] = b"SIMP"
    buf_scoring[4] = 2
    track_b = b"Circuit de Spa-Francorchamps\x00"
    buf_scoring[5:5+len(track_b)] = track_b
    struct.pack_into("<i", buf_scoring, 72, 11)   # Race session
    struct.pack_into("<d", buf_scoring, 76, 120.0) # currentET
    struct.pack_into("<d", buf_scoring, 84, 7004.0) # Lap dist
    struct.pack_into("<i", buf_scoring, 92, 25)    # Max laps
    buf_scoring[96] = 1                            # in_realtime
    struct.pack_into("<h", buf_scoring, 98, 6)     # Total laps
    struct.pack_into("<b", buf_scoring, 100, 2)    # Sector 2
    buf_scoring[101] = 0                           # inGarageStall
    buf_scoring[102] = 2                           # Valid lap
    struct.pack_into("<d", buf_scoring, 104, 38.420)
    struct.pack_into("<d", buf_scoring, 112, 94.850)
    struct.pack_into("<d", buf_scoring, 120, 38.512)
    struct.pack_into("<d", buf_scoring, 128, 94.901)
    struct.pack_into("<d", buf_scoring, 136, 138.452)
    struct.pack_into("<d", buf_scoring, 144, 38.310)
    struct.pack_into("<d", buf_scoring, 152, 94.400)
    struct.pack_into("<d", buf_scoring, 160, 137.910)

    # Telemetry static strings
    veh_b = b"Ferrari 499P Hypercar #51\x00"
    buf_telemetry[32:32+len(veh_b)] = veh_b
    buf_telemetry[96:96+len(track_b)] = track_b
    f_comp = b"Michelin Medium Wet\x00"
    r_comp = b"Michelin Medium Wet\x00"
    buf_telemetry[620:620+len(f_comp)] = f_comp
    buf_telemetry[638:638+len(r_comp)] = r_comp

    t = 0.0
    while not stop_flag.is_set():
        t += 0.01

        # Session & timing
        struct.pack_into("<i", buf_telemetry, 0, 1)          # slot_id
        struct.pack_into("<d", buf_telemetry, 4, 0.010)      # delta_time
        struct.pack_into("<d", buf_telemetry, 12, t)         # elapsed_time
        struct.pack_into("<i", buf_telemetry, 20, 6)         # lap_number
        struct.pack_into("<d", buf_telemetry, 24, 120.0)     # lap_start_et

        # Physics
        spd = 65.0 + 25.0 * math.sin(t * 0.5)
        rpm = 5200.0 + 2400.0 * math.sin(t * 1.5)
        struct.pack_into("<ddd", buf_telemetry, 160, 1420.5, 320.1, -450.2) # pos
        struct.pack_into("<ddd", buf_telemetry, 184, 0.2 * math.sin(t), 0.0, -spd) # local_vel
        struct.pack_into("<ddd", buf_telemetry, 208, 2.5 * math.sin(t), 0.0, -1.2) # local_accel

        # Orientation
        struct.pack_into("<ddd", buf_telemetry, 232, 1.0, 0.0, 0.0)
        struct.pack_into("<ddd", buf_telemetry, 256, 0.0, 1.0, 0.0)
        struct.pack_into("<ddd", buf_telemetry, 280, 0.0, 0.0, 1.0)
        struct.pack_into("<ddd", buf_telemetry, 304, 0.02 * math.sin(t), 0.05 * math.cos(t), 0.01)
        struct.pack_into("<ddd", buf_telemetry, 328, 0.0, 0.0, 0.0)

        # Engine & controls
        gear_num = 4 if spd < 75 else 5
        struct.pack_into("<i", buf_telemetry, 352, gear_num)
        struct.pack_into("<d", buf_telemetry, 356, rpm)
        struct.pack_into("<d", buf_telemetry, 364, 88.5)     # water_temp
        struct.pack_into("<d", buf_telemetry, 372, 96.2)     # oil_temp
        struct.pack_into("<d", buf_telemetry, 380, rpm)      # clutch_rpm

        thr = 0.5 + 0.5 * math.sin(t * 2)
        brk = max(0.0, -math.sin(t * 2))
        steer = 0.25 * math.sin(t * 0.8)
        struct.pack_into("<d", buf_telemetry, 388, thr)      # unf_thr
        struct.pack_into("<d", buf_telemetry, 396, brk)      # unf_brk
        struct.pack_into("<d", buf_telemetry, 404, steer)    # unf_str
        struct.pack_into("<d", buf_telemetry, 412, 0.0)      # unf_clutch
        struct.pack_into("<d", buf_telemetry, 420, thr * 0.98) # fil_thr
        struct.pack_into("<d", buf_telemetry, 428, brk * 0.95) # fil_brk
        struct.pack_into("<d", buf_telemetry, 436, steer)
        struct.pack_into("<d", buf_telemetry, 444, 0.0)
        struct.pack_into("<d", buf_telemetry, 452, steer * 15.0) # shaft torque

        # Aero & chassis
        struct.pack_into("<d", buf_telemetry, 460, 0.015 + 0.003 * math.sin(t)) # f_3rd
        struct.pack_into("<d", buf_telemetry, 468, 0.018 + 0.004 * math.cos(t)) # r_3rd
        struct.pack_into("<d", buf_telemetry, 476, 0.045)     # f_wing
        struct.pack_into("<d", buf_telemetry, 484, 0.038)     # f_ride
        struct.pack_into("<d", buf_telemetry, 492, 0.052)     # r_ride
        struct.pack_into("<d", buf_telemetry, 500, 850.0)     # drag
        struct.pack_into("<d", buf_telemetry, 508, 1450.0)    # f_df
        struct.pack_into("<d", buf_telemetry, 516, 2100.0)    # r_df
        struct.pack_into("<d", buf_telemetry, 524, max(1.0, 50.0 - t * 0.05)) # fuel
        struct.pack_into("<d", buf_telemetry, 532, 8600.0)   # max_rpm
        buf_telemetry[543] = 1                                # headlights
        struct.pack_into("<d", buf_telemetry, 592, 560.0)    # torque
        struct.pack_into("<i", buf_telemetry, 600, 2)         # sector 2
        struct.pack_into("<d", buf_telemetry, 608, 105.0)     # fuel_capacity
        struct.pack_into("<f", buf_telemetry, 660, 450.0)     # visual_steer_range
        struct.pack_into("<d", buf_telemetry, 664, 0.46)      # rear_brake_bias
        struct.pack_into("<d", buf_telemetry, 672, 142.5)     # turbo_boost
        struct.pack_into("<f", buf_telemetry, 692, 450.0)     # physical_steer_range

        # Hybrid
        struct.pack_into("<d", buf_telemetry, 696, 0.76)      # battery SoC
        struct.pack_into("<d", buf_telemetry, 704, 180.0)     # eb_torque
        struct.pack_into("<d", buf_telemetry, 712, rpm * 1.3) # eb_rpm
        struct.pack_into("<d", buf_telemetry, 720, 68.5)      # eb_temp
        struct.pack_into("<d", buf_telemetry, 728, 46.2)      # eb_water_temp
        buf_telemetry[736] = 2                                # propulsion

        # 4 Wheels
        for i in range(4):
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
        Binding("3", "select_tab_rules", "Rules", show=False),
        Binding("4", "select_tab_pit", "Pit", show=False),
        Binding("5", "select_tab_weather", "Weather", show=False),
        Binding("6", "select_tab_event", "Event", show=False),
        Binding("7", "select_tab_stats", "Stats", show=False),
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
        self.lbl_channel_freq = Static("📶 Stream: [bold yellow]0.0 Hz[/]", classes="metric-box")
        self.lbl_rate = Static("⚡ Total: [bold magenta]0.0 KB/s[/]", classes="metric-box")
        self.lbl_visible_rows = Static("🔍 Fields: [bold cyan]0 / 0[/]", classes="metric-box")

        self.tabs = Tabs(
            Tab("🏎️ TelemInfo (1888 B)", id=TAB_TELEM),
            Tab("🏁 Grid Scoring", id=TAB_SCORING),
            Tab("🚩 Track Rules & SC", id=TAB_RULES),
            Tab("⛽ Pit Menu", id=TAB_PIT),
            Tab("🌦️ Weather", id=TAB_WEATHER),
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
            yield self.lbl_channel_freq
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

    def action_select_tab_rules(self) -> None:
        self.tabs.active = TAB_RULES

    def action_select_tab_pit(self) -> None:
        self.tabs.active = TAB_PIT

    def action_select_tab_weather(self) -> None:
        self.tabs.active = TAB_WEATHER

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
            return extract_telemetry_rows(self.engine.latest_telemetry, self.engine.stats[PKT_RAW_TELEMETRY])
        elif self.active_tab == TAB_SCORING:
            st = self.engine.stats.get(PKT_FULL_SCORING) if self.engine.latest_full_scoring else self.engine.stats[PKT_COMPACT_SCORING]
            return extract_scoring_rows(self.engine.latest_scoring, self.engine.latest_full_scoring, st)
        elif self.active_tab == TAB_RULES:
            return extract_track_rules_rows(self.engine.latest_track_rules, self.engine.stats[PKT_TRACK_RULES])
        elif self.active_tab == TAB_PIT:
            return extract_pit_menu_rows(self.engine.latest_pit_menu, self.engine.stats[PKT_PIT_MENU])
        elif self.active_tab == TAB_WEATHER:
            return extract_weather_rows(self.engine.latest_weather, self.engine.stats[PKT_WEATHER])
        elif self.active_tab == TAB_EVENT:
            return extract_event_rows(self.engine.latest_event, self.engine.stats[PKT_SYSTEM_EVENT], self.engine.latest_event_time)
        elif self.active_tab == TAB_STATS:
            return extract_stats_rows(self.engine)
        return []

    def _get_active_model_dict(self) -> Dict[str, Any]:
        """Returns clean dictionary for JSON export."""
        if self.active_tab == TAB_TELEM:
            st = self.engine.stats[PKT_RAW_TELEMETRY]
            if self.engine.latest_telemetry:
                d = model_to_clean_dict(self.engine.latest_telemetry)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "jitter_ms": round(st.jitter_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                d["_computed"] = {
                    "speed_kmh": self.engine.latest_telemetry.speed_kmh,
                    "forward_speed_kmh": self.engine.latest_telemetry.forward_speed_kmh,
                    "gear_str": self.engine.latest_telemetry.gear_str,
                }
                return d
            return {"status": "No TelemInfo packet received yet"}
        elif self.active_tab == TAB_SCORING:
            if self.engine.latest_full_scoring:
                st = self.engine.stats[PKT_FULL_SCORING]
                d = model_to_clean_dict(self.engine.latest_full_scoring)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            elif self.engine.latest_scoring:
                st = self.engine.stats[PKT_COMPACT_SCORING]
                d = model_to_clean_dict(self.engine.latest_scoring)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No Scoring packet received yet"}
        elif self.active_tab == TAB_RULES:
            st = self.engine.stats[PKT_TRACK_RULES]
            if self.engine.latest_track_rules:
                d = model_to_clean_dict(self.engine.latest_track_rules)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No TrackRules packet received yet"}
        elif self.active_tab == TAB_PIT:
            st = self.engine.stats[PKT_PIT_MENU]
            if self.engine.latest_pit_menu:
                d = model_to_clean_dict(self.engine.latest_pit_menu)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No PitMenu packet received yet"}
        elif self.active_tab == TAB_WEATHER:
            st = self.engine.stats[PKT_WEATHER]
            if self.engine.latest_weather:
                d = model_to_clean_dict(self.engine.latest_weather)
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
        elif self.active_tab == TAB_EVENT:
            st = self.engine.stats[PKT_SYSTEM_EVENT]
            if self.engine.latest_event:
                d = model_to_clean_dict(self.engine.latest_event)
                d["name"] = self.engine.latest_event.name
                d["timestamp"] = self.engine.latest_event_time
                d["_channel_diagnostics"] = {
                    "packets_count": st.count,
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
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
            f"⚡ Total: [bold magenta]{current_kb_s:5.1f} KB/s[/]"
        )

        # Update Selected Channel Real Reception Frequency
        if self.active_tab == TAB_TELEM:
            st = self.engine.stats[PKT_RAW_TELEMETRY]
            self.lbl_channel_freq.update(
                f"📶 [bold cyan]TelemInfo:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
            )
        elif self.active_tab == TAB_SCORING:
            st = self.engine.stats[PKT_FULL_SCORING] if self.engine.latest_full_scoring else self.engine.stats[PKT_COMPACT_SCORING]
            self.lbl_channel_freq.update(
                f"📶 [bold cyan]Scoring:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
            )
        elif self.active_tab == TAB_RULES:
            st = self.engine.stats[PKT_TRACK_RULES]
            self.lbl_channel_freq.update(
                f"📶 [bold cyan]TrackRules:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
            )
        elif self.active_tab == TAB_PIT:
            st = self.engine.stats[PKT_PIT_MENU]
            self.lbl_channel_freq.update(
                f"📶 [bold cyan]PitMenu:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
            )
        elif self.active_tab == TAB_WEATHER:
            st = self.engine.stats[PKT_WEATHER]
            self.lbl_channel_freq.update(
                f"📶 [bold cyan]Weather:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
            )
        elif self.active_tab == TAB_EVENT:
            st = self.engine.stats[PKT_SYSTEM_EVENT]
            self.lbl_channel_freq.update(
                f"📶 [bold cyan]Events:[/] [bold yellow]{st.count}[/] [dim]pkts[/dim]"
            )
        elif self.active_tab == TAB_STATS:
            self.lbl_channel_freq.update(
                f"📶 [bold cyan]All Streams:[/] [bold yellow]{current_total_freq:5.1f} Hz[/]"
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
