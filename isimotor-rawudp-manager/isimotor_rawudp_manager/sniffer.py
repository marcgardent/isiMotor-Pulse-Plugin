#!/usr/bin/env python3
"""
isiMotor UDP Telemetry Packet Explorer & Benchmark
Built with Textual for a high-performance, responsive raw data inspector.
"""

import argparse
import json
import select
import socket
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Support loading parent package and scripts
manager_pkg_dir = Path(__file__).resolve().parent
manager_root = manager_pkg_dir.parent
project_root = manager_root.parent
client_pkg_path = project_root / "isimotor-rawudp-client"
if client_pkg_path.exists():
    sys.path.insert(0, str(client_pkg_path))
if str(manager_pkg_dir) not in sys.path:
    sys.path.insert(0, str(manager_pkg_dir))
if str(manager_root) not in sys.path:
    sys.path.insert(0, str(manager_root))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from .installer import (
        copy_and_install_dll,
        get_configuration_overview,
    )
except (ImportError, ValueError):
    from isimotor_rawudp_manager.installer import (
        copy_and_install_dll,
        get_configuration_overview,
    )

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Grid, Horizontal, Vertical, VerticalScroll
    from textual.reactive import reactive
    from textual.widgets import (
        Button,
        ContentSwitcher,
        DataTable,
        Footer,
        Header,
        Input,
        Label,
        Static,
        Tab,
        Tabs,
    )
except ImportError:
    print("\n[!] The 'textual' package is required to run the manager dashboard.")
    print("    Install dependencies in the manager environment:")
    print("      cd isimotor-rawudp-manager && uv venv && uv pip install -e ../isimotor-rawudp-client textual rich\n")
    print("    Or run with Makefile: make manager")
    sys.exit(1)

from isimotor_rawudp_client.decoder import (
    HEADER_SIZE,
    decode_compact_scoring,
    decode_extended_state,
    decode_force_feedback,
    decode_full_scoring,
    decode_graphics,
    decode_header,
    decode_pit_menu,
    decode_system_event,
    decode_telemetry,
    decode_track_rules,
    decode_weather,
    encode_hw_control,
    encode_weather_control,
)
from isimotor_rawudp_client.models import (
    CompactScoring,
    ExtendedState,
    ForceFeedback,
    FullScoringSession,
    Graphics,
    HWControlCommand,
    PitMenu,
    SystemEvent,
    TelemInfo,
    TrackRulesSession,
    WeatherControl,
    WeatherControlCommand,
)

# ── Packet Stream Definitions ──────────────────────────────────────────────────
PKT_RAW_TELEMETRY = "TelemInfoV01 (Raw Binary)"
PKT_COMPACT_SCORING = "CompactScoring (SIMP v2)"
PKT_FULL_SCORING = "FullScoring (SIMP v4 Sliced)"
PKT_TRACK_RULES = "TrackRules (SIMP v5 Sliced)"
PKT_PIT_MENU = "PitMenu (SIMP v6)"
PKT_WEATHER = "Weather (SIMP v7)"
PKT_EXTENDED_STATE = "ExtendedState (SIMP v8)"
PKT_FORCE_FEEDBACK = "ForceFeedback (SIMP v9 @ 400Hz)"
PKT_GRAPHICS = "Graphics (SIMP v10 @ 60Hz)"
PKT_SYSTEM_EVENT = "SystemEvent (SIMP v3)"
PKT_HW_CONTROL = "HWControl (SIMP v100)"
PKT_WEATHER_CONTROL = "WeatherControl (SIMP v101)"
PKT_FOREIGN = "Foreign / Unknown"

# ── Main Navigation Modes ──────────────────────────────────────────────────────
NAV_HOME = "nav-home"
NAV_INSTALL = "nav-install"
NAV_EXPLORER = "nav-explorer"
NAV_COMMANDS = "nav-commands"

VIEW_HOME = "view-home"
VIEW_INSTALL = "view-install"
VIEW_EXPLORER = "view-explorer"
VIEW_COMMANDS = "view-commands"

# ── Stream Explorer Tabs ───────────────────────────────────────────────────────
TAB_TELEM = "tab-telem"
TAB_SCORING = "tab-scoring"
TAB_RULES = "tab-rules"
TAB_PIT = "tab-pit"
TAB_WEATHER = "tab-weather"
TAB_FFB = "tab-ffb"
TAB_GRAPHICS = "tab-graphics"
TAB_PHYSICS = "tab-physics"
TAB_EVENT = "tab-event"
TAB_INBOUND = "tab-inbound"
TAB_CONFIG = "tab-config"
TAB_STATS = "tab-stats"


@dataclass
class PacketStats:
    name: str
    format_type: str
    expected_size: str
    count: int = 0
    bytes_total: int = 0
    timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=300))
    intervals: deque[float] = field(default_factory=lambda: deque(maxlen=150))
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
        self.socket: socket.socket | None = None

        self.stats: dict[str, PacketStats] = {
            PKT_RAW_TELEMETRY: PacketStats(PKT_RAW_TELEMETRY, "Binary Struct", "1888/1904 B"),
            PKT_COMPACT_SCORING: PacketStats(PKT_COMPACT_SCORING, "Binary SIMP", "168 B"),
            PKT_FULL_SCORING: PacketStats(PKT_FULL_SCORING, "Sliced SIMP", "Multi-KB"),
            PKT_TRACK_RULES: PacketStats(PKT_TRACK_RULES, "Sliced SIMP", "Multi-KB"),
            PKT_PIT_MENU: PacketStats(PKT_PIT_MENU, "Binary SIMP", "76 B"),
            PKT_WEATHER: PacketStats(PKT_WEATHER, "Binary SIMP", "108 B"),
            PKT_EXTENDED_STATE: PacketStats(PKT_EXTENDED_STATE, "Binary SIMP", "68 B"),
            PKT_FORCE_FEEDBACK: PacketStats(PKT_FORCE_FEEDBACK, "Binary SIMP", "8 B"),
            PKT_GRAPHICS: PacketStats(PKT_GRAPHICS, "Binary SIMP", "128 B"),
            PKT_SYSTEM_EVENT: PacketStats(PKT_SYSTEM_EVENT, "Binary SIMP", "6 B"),
            PKT_HW_CONTROL: PacketStats(PKT_HW_CONTROL, "Binary SIMP", "44 B"),
            PKT_WEATHER_CONTROL: PacketStats(PKT_WEATHER_CONTROL, "Binary SIMP", "64 B"),
            PKT_FOREIGN: PacketStats(PKT_FOREIGN, "Raw/Other", "Variable"),
        }

        self.latest_telemetry: TelemInfo | None = None
        self.latest_scoring: CompactScoring | None = None
        self.latest_full_scoring: FullScoringSession | None = None
        self.latest_track_rules: TrackRulesSession | None = None
        self.latest_pit_menu: PitMenu | None = None
        self.latest_weather: WeatherControl | None = None
        self.latest_extended_state: ExtendedState | None = None
        self.latest_force_feedback: ForceFeedback | None = None
        self.latest_graphics: Graphics | None = None
        self.latest_event: SystemEvent | None = None
        self.latest_event_time: float = 0.0
        self.latest_hw_control: HWControlCommand | None = None
        self.latest_weather_control: WeatherControlCommand | None = None
        self.inbound_target_host: str = "127.0.0.1"
        self.inbound_target_port: int = 5001
        self.last_inbound_cmd_sent: str = "None"
        self.last_inbound_cmd_time: float = 0.0
        self._inbound_seq: int = 0
        self.reassembly_buffers: dict[tuple, dict] = {}
        self.last_cleanup_time: float = 0.0

    def send_hw_control(self, control_name: str, control_value: float = 1.0, duration_ms: int = 50) -> bool:
        """Sends an inbound Type 100 control packet."""
        self._inbound_seq += 1
        pkt = encode_hw_control(
            control_name=control_name,
            control_value=control_value,
            duration_ms=duration_ms,
            with_header=True,
            sequence_number=self._inbound_seq,
        )
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(pkt, (self.inbound_target_host, self.inbound_target_port))
            self.last_inbound_cmd_sent = f"{control_name} (val={control_value}, dur={duration_ms}ms)"
            self.last_inbound_cmd_time = time.time()
            return True
        except Exception as e:
            self.last_inbound_cmd_sent = f"Error: {e}"
            return False
        finally:
            sock.close()

    def send_weather_override(self, ambient_temp: float = 20.0, raining: float = 0.0) -> bool:
        """Sends an inbound Type 101 weather control packet."""
        self._inbound_seq += 1
        pkt = encode_weather_control(
            ambient_temp=ambient_temp,
            track_temp=ambient_temp + 5.0,
            dark_cloud=min(1.0, raining * 1.2),
            raining=raining,
            wind_speed=2.5,
            wind_direction=0.0,
            min_path_wetness=raining * 0.8,
            max_path_wetness=raining,
            with_header=True,
            sequence_number=self._inbound_seq,
        )
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(pkt, (self.inbound_target_host, self.inbound_target_port))
            self.last_inbound_cmd_sent = f"WeatherOverride (Temp={ambient_temp:.1f}°C, Rain={raining * 100:.0f}%)"
            self.last_inbound_cmd_time = time.time()
            return True
        except Exception as e:
            self.last_inbound_cmd_sent = f"Error: {e}"
            return False
        finally:
            sock.close()

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
            except (OSError, BlockingIOError):
                break

    def _process_packet(self, data: bytes, addr: tuple[str, int]):
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
                elif hdr.packet_type == 8:
                    pkt_type = PKT_EXTENDED_STATE
                    ext = decode_extended_state(payload)
                    if ext:
                        self.latest_extended_state = ext
                elif hdr.packet_type == 9:
                    pkt_type = PKT_FORCE_FEEDBACK
                    ffb = decode_force_feedback(payload)
                    if ffb:
                        self.latest_force_feedback = ffb
                elif hdr.packet_type == 10:
                    pkt_type = PKT_GRAPHICS
                    gfx = decode_graphics(payload)
                    if gfx:
                        self.latest_graphics = gfx
                elif hdr.packet_type == 100:
                    pkt_type = PKT_HW_CONTROL
                elif hdr.packet_type == 101:
                    pkt_type = PKT_WEATHER_CONTROL

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
        return f'[#a5d6ff]"{val}"[/]' if val else '[dim]""[/dim]'
    if isinstance(val, (list, tuple)):
        items_str = ", ".join(f"{x:.2f}" if isinstance(x, float) else str(x) for x in val)
        return f"({items_str})"
    return str(val)


def extract_telemetry_rows(t: TelemInfo | None, st: PacketStats | None = None) -> list[tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for TelemInfo packet.
    """
    rows: list[tuple[str, Any, str, str]] = []

    # Channel / Stream Diagnostics
    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        jitter_str = f"±{st.jitter_ms:3.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                (
                    "_channel.frequency_hz",
                    st.current_freq,
                    freq_str,
                    "Real-time reception frequency of TelemInfo packet stream",
                ),
                (
                    "_channel.packets_count",
                    st.count,
                    f"{st.count:,}",
                    "Total TelemInfo packets received on this channel",
                ),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between consecutive TelemInfo packets",
                ),
                ("_channel.jitter_ms", st.jitter_ms, jitter_str, "TelemInfo packet arrival jitter variation"),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for TelemInfo stream",
                ),
            ]
        )

    if t is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No TelemInfo packet received yet[/dim]",
                "Start game or launch native isi_mock_host",
            )
        )
        return rows

    rows.extend(
        [
            # Session & Identity
            ("slot_id", t.slot_id, format_value(t.slot_id), "Player vehicle slot index in session / multiplayer"),
            ("delta_time", t.delta_time, f"{t.delta_time:.4f} s", "Time since last physics update (seconds)"),
            ("elapsed_time", t.elapsed_time, f"{t.elapsed_time:.3f} s", "Total game session elapsed time (seconds)"),
            ("lap_number", t.lap_number, format_value(t.lap_number), "Current lap number"),
            (
                "lap_start_et",
                t.lap_start_et,
                f"{t.lap_start_et:.3f} s",
                "Session time when current lap began (seconds)",
            ),
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
            (
                "forward_speed_mps",
                t.forward_speed_mps,
                f"{t.forward_speed_mps:.3f} m/s",
                "Forward speed along vehicle axis (ISO +x = isiMotor -z, m/s)",
            ),
            (
                "forward_speed_kmh",
                t.forward_speed_kmh,
                f"{t.forward_speed_kmh:.2f} km/h",
                "Forward speed along vehicle axis (km/h)",
            ),
            ("local_accel.x", t.local_accel.x, f"{t.local_accel.x:.3f} m/s²", "Local lateral acceleration (m/s²)"),
            ("local_accel.y", t.local_accel.y, f"{t.local_accel.y:.3f} m/s²", "Local vertical acceleration (m/s²)"),
            ("local_accel.z", t.local_accel.z, f"{t.local_accel.z:.3f} m/s²", "Local longitudinal acceleration (m/s²)"),
            ("local_rot.x", t.local_rot.x, f"{t.local_rot.x:.4f} rad/s", "Pitch rate (+x pitch up, rad/s)"),
            ("local_rot.y", t.local_rot.y, f"{t.local_rot.y:.4f} rad/s", "Yaw rate (+y yaw right, rad/s)"),
            ("local_rot.z", t.local_rot.z, f"{t.local_rot.z:.4f} rad/s", "Roll rate (+z roll right, rad/s)"),
            (
                "local_rot_accel.x",
                t.local_rot_accel.x,
                f"{t.local_rot_accel.x:.4f} rad/s²",
                "Pitch angular acceleration (rad/s²)",
            ),
            (
                "local_rot_accel.y",
                t.local_rot_accel.y,
                f"{t.local_rot_accel.y:.4f} rad/s²",
                "Yaw angular acceleration (rad/s²)",
            ),
            (
                "local_rot_accel.z",
                t.local_rot_accel.z,
                f"{t.local_rot_accel.z:.4f} rad/s²",
                "Roll angular acceleration (rad/s²)",
            ),
            (
                "ori[0]",
                t.ori[0].as_tuple(),
                format_value(t.ori[0].as_tuple()),
                "Orientation matrix row 0 (lateral axis vector)",
            ),
            (
                "ori[1]",
                t.ori[1].as_tuple(),
                format_value(t.ori[1].as_tuple()),
                "Orientation matrix row 1 (vertical axis vector)",
            ),
            (
                "ori[2]",
                t.ori[2].as_tuple(),
                format_value(t.ori[2].as_tuple()),
                "Orientation matrix row 2 (longitudinal axis vector)",
            ),
            # Engine & Drivetrain
            ("gear", t.gear, format_value(t.gear), "Transmission gear index (-1=Reverse, 0=Neutral, 1+=Forward)"),
            (
                "gear_str",
                t.gear_str,
                f"[bold #f1e05a]{t.gear_str}[/]",
                "Human-readable gear label ('R', 'N', '1', '2'...)",
            ),
            ("engine_rpm", t.engine_rpm, f"{t.engine_rpm:.1f} RPM", "Engine crankshaft rotational speed (RPM)"),
            ("engine_max_rpm", t.engine_max_rpm, f"{t.engine_max_rpm:.1f} RPM", "Engine rev limiter maximum RPM"),
            (
                "engine_water_temp",
                t.engine_water_temp,
                f"{t.engine_water_temp:.1f} °C",
                "Engine cooling water / radiator temperature (°C)",
            ),
            (
                "engine_oil_temp",
                t.engine_oil_temp,
                f"{t.engine_oil_temp:.1f} °C",
                "Engine lubrication oil temperature (°C)",
            ),
            ("clutch_rpm", t.clutch_rpm, f"{t.clutch_rpm:.1f} RPM", "Clutch plate rotational speed (RPM)"),
            (
                "engine_torque",
                t.engine_torque,
                f"{t.engine_torque:.1f} N·m",
                "Instantaneous engine torque output (N·m)",
            ),
            # Driver Inputs
            (
                "unfiltered_throttle",
                t.unfiltered_throttle,
                f"{t.unfiltered_throttle * 100:.1f} %",
                "Raw driver throttle pedal position [0.0 - 1.0]",
            ),
            (
                "unfiltered_brake",
                t.unfiltered_brake,
                f"{t.unfiltered_brake * 100:.1f} %",
                "Raw driver brake pedal position [0.0 - 1.0]",
            ),
            (
                "unfiltered_steering",
                t.unfiltered_steering,
                f"{t.unfiltered_steering:+.3f}",
                "Raw driver steering input [-1.0 (L) to +1.0 (R)]",
            ),
            (
                "unfiltered_clutch",
                t.unfiltered_clutch,
                f"{t.unfiltered_clutch * 100:.1f} %",
                "Raw driver clutch pedal position [0.0 - 1.0]",
            ),
            (
                "filtered_throttle",
                t.filtered_throttle,
                f"{t.filtered_throttle * 100:.1f} %",
                "Processed throttle after TC / aids [0.0 - 1.0]",
            ),
            (
                "filtered_brake",
                t.filtered_brake,
                f"{t.filtered_brake * 100:.1f} %",
                "Processed brake after ABS / aids [0.0 - 1.0]",
            ),
            (
                "filtered_steering",
                t.filtered_steering,
                f"{t.filtered_steering:+.3f}",
                "Processed steering input after speed sensitivity [-1.0 to +1.0]",
            ),
            (
                "filtered_clutch",
                t.filtered_clutch,
                f"{t.filtered_clutch * 100:.1f} %",
                "Processed clutch input after anti-stall [0.0 - 1.0]",
            ),
            (
                "steering_shaft_torque",
                t.steering_shaft_torque,
                f"{t.steering_shaft_torque:.2f} N·m",
                "Feedback torque on steering shaft column (N·m)",
            ),
            # Suspension & Aerodynamics
            (
                "front_3rd_deflection",
                t.front_3rd_deflection,
                f"{t.front_3rd_deflection * 1000:.2f} mm",
                "Front 3rd / heave spring suspension deflection (m)",
            ),
            (
                "rear_3rd_deflection",
                t.rear_3rd_deflection,
                f"{t.rear_3rd_deflection * 1000:.2f} mm",
                "Rear 3rd / heave spring suspension deflection (m)",
            ),
            (
                "front_wing_height",
                t.front_wing_height,
                f"{t.front_wing_height * 1000:.1f} mm",
                "Front aerodynamic wing ride height clearance (m)",
            ),
            (
                "front_ride_height",
                t.front_ride_height,
                f"{t.front_ride_height * 1000:.1f} mm",
                "Front chassis underbody ride height (m)",
            ),
            (
                "rear_ride_height",
                t.rear_ride_height,
                f"{t.rear_ride_height * 1000:.1f} mm",
                "Rear chassis underbody ride height (m)",
            ),
            ("drag", t.drag, f"{t.drag:.1f} N", "Aerodynamic drag force (Newtons)"),
            (
                "front_downforce",
                t.front_downforce,
                f"{t.front_downforce:.1f} N",
                "Front axle aerodynamic downforce (Newtons)",
            ),
            (
                "rear_downforce",
                t.rear_downforce,
                f"{t.rear_downforce:.1f} N",
                "Rear axle aerodynamic downforce (Newtons)",
            ),
            (
                "rear_brake_bias",
                t.rear_brake_bias,
                f"{t.rear_brake_bias * 100:.1f} %",
                "Rear brake proportion bias fraction [0.0 - 1.0]",
            ),
            # Fuel & System Status
            ("fuel", t.fuel, f"{t.fuel:.2f} L", "Current remaining fuel volume (liters)"),
            ("fuel_capacity", t.fuel_capacity, f"{t.fuel_capacity:.1f} L", "Maximum fuel tank capacity (liters)"),
            (
                "current_sector",
                t.current_sector,
                format_value(t.current_sector),
                "Current sector index (0-based; pitlane in sign bit)",
            ),
            (
                "scheduled_stops",
                t.scheduled_stops,
                format_value(t.scheduled_stops),
                "Number of scheduled pitstops in strategy",
            ),
            ("overheating", t.overheating, format_value(t.overheating), "Engine overheating warning flag"),
            ("detached", t.detached, format_value(t.detached), "Detached / missing vehicle parts flag"),
            ("headlights", t.headlights, format_value(t.headlights), "Headlights active illumination state"),
            (
                "speed_limiter",
                bool(t.speed_limiter),
                format_value(bool(t.speed_limiter)),
                "Pitlane speed limiter enabled flag",
            ),
            (
                "speed_limiter_available",
                bool(t.speed_limiter_available),
                format_value(bool(t.speed_limiter_available)),
                "Speed limiter available on vehicle flag",
            ),
            (
                "anti_stall_activated",
                bool(t.anti_stall_activated),
                format_value(bool(t.anti_stall_activated)),
                "Anti-stall electronic aid active flag",
            ),
            (
                "ignition_starter",
                t.ignition_starter,
                format_value(t.ignition_starter),
                "Ignition / Starter switch state (0=off, 1=ign, 2=ign+start)",
            ),
            (
                "front_flap_activated",
                t.front_flap_activated,
                format_value(t.front_flap_activated),
                "Front active aero flap status",
            ),
            (
                "rear_flap_activated",
                t.rear_flap_activated,
                format_value(t.rear_flap_activated),
                "Rear DRS / active aero flap status",
            ),
            (
                "rear_flap_legal_status",
                t.rear_flap_legal_status,
                format_value(t.rear_flap_legal_status),
                "DRS legal zone status (0=disallowed, 1=detected, 2=allowed)",
            ),
            (
                "front_tire_compound_index",
                t.front_tire_compound_index,
                format_value(t.front_tire_compound_index),
                "Front tire compound index",
            ),
            (
                "rear_tire_compound_index",
                t.rear_tire_compound_index,
                format_value(t.rear_tire_compound_index),
                "Rear tire compound index",
            ),
            (
                "front_tire_compound_name",
                t.front_tire_compound_name,
                format_value(t.front_tire_compound_name),
                "Front tire compound specification name",
            ),
            (
                "rear_tire_compound_name",
                t.rear_tire_compound_name,
                format_value(t.rear_tire_compound_name),
                "Rear tire compound specification name",
            ),
            (
                "turbo_boost_pressure",
                t.turbo_boost_pressure,
                f"{t.turbo_boost_pressure:.2f} kPa",
                "Turbocharger forced-induction boost pressure",
            ),
            (
                "visual_steering_wheel_range",
                t.visual_steering_wheel_range,
                f"{t.visual_steering_wheel_range:.1f}°",
                "Cockpit visual steering wheel lock angle (deg)",
            ),
            (
                "physical_steering_wheel_range",
                t.physical_steering_wheel_range,
                f"{t.physical_steering_wheel_range:.1f}°",
                "Hardware physical FFB steering lock angle (deg)",
            ),
            (
                "physics_to_graphics_offset",
                t.physics_to_graphics_offset,
                format_value(t.physics_to_graphics_offset),
                "Offset from physics center to graphical model (x, y, z)",
            ),
            (
                "dent_severity",
                t.dent_severity,
                format_value(t.dent_severity),
                "Body damage dent severity across 8 zones [0..2]",
            ),
            (
                "last_impact_et",
                t.last_impact_et,
                f"{t.last_impact_et:.3f} s",
                "Session time of last recorded collision impact (s)",
            ),
            (
                "last_impact_magnitude",
                t.last_impact_magnitude,
                f"{t.last_impact_magnitude:.2f}",
                "Magnitude / force of last collision impact",
            ),
            (
                "last_impact_pos",
                t.last_impact_pos.as_tuple(),
                format_value(t.last_impact_pos.as_tuple()),
                "Vehicle local coordinate of last impact",
            ),
            # Hybrid & E-Motor
            (
                "battery_charge_fraction",
                t.battery_charge_fraction,
                f"{t.battery_charge_fraction * 100:.1f} %",
                "Hybrid battery State of Charge (SoC) [0.0 - 1.0]",
            ),
            (
                "electric_boost_motor_torque",
                t.electric_boost_motor_torque,
                f"{t.electric_boost_motor_torque:.1f} N·m",
                "Electric hybrid MGU boost motor torque (N·m)",
            ),
            (
                "electric_boost_motor_rpm",
                t.electric_boost_motor_rpm,
                f"{t.electric_boost_motor_rpm:.0f} RPM",
                "Electric hybrid MGU motor speed (RPM)",
            ),
            (
                "electric_boost_motor_temperature",
                t.electric_boost_motor_temperature,
                f"{t.electric_boost_motor_temperature:.1f} °C",
                "Electric hybrid motor stator temperature (°C)",
            ),
            (
                "electric_boost_water_temperature",
                t.electric_boost_water_temperature,
                f"{t.electric_boost_water_temperature:.1f} °C",
                "Electric hybrid cooling water loop temp (°C)",
            ),
            (
                "electric_boost_motor_state",
                t.electric_boost_motor_state,
                format_value(t.electric_boost_motor_state),
                "MGU operating state (0=off, 1=idle, 2=propulsion, 3=regen)",
            ),
        ]
    )

    # 4 Wheels
    wheel_labels = [("fl", "Front-Left", 0), ("fr", "Front-Right", 1), ("rl", "Rear-Left", 2), ("rr", "Rear-Right", 3)]
    for code, lbl, idx in wheel_labels:
        w = t.wheels[idx]
        rows.extend(
            [
                (
                    f"wheels.{code}.suspension_deflection",
                    w.suspension_deflection,
                    f"{w.suspension_deflection * 1000:.2f} mm",
                    f"{lbl} suspension spring travel deflection",
                ),
                (
                    f"wheels.{code}.ride_height",
                    w.ride_height,
                    f"{w.ride_height * 1000:.1f} mm",
                    f"{lbl} underbody clearance at wheel corner",
                ),
                (
                    f"wheels.{code}.susp_force",
                    w.susp_force,
                    f"{w.susp_force:.1f} N",
                    f"{lbl} pushrod suspension load force (Newtons)",
                ),
                (
                    f"wheels.{code}.brake_temp",
                    w.brake_temp,
                    f"{w.brake_temp:.1f} °C",
                    f"{lbl} brake disc rotor temperature (°C)",
                ),
                (
                    f"wheels.{code}.brake_pressure",
                    w.brake_pressure,
                    f"{w.brake_pressure * 100:.1f} %",
                    f"{lbl} brake caliper hydraulic line pressure",
                ),
                (
                    f"wheels.{code}.rotation",
                    w.rotation,
                    f"{w.rotation:.2f} rad/s",
                    f"{lbl} wheel angular rotational speed (rad/s)",
                ),
                (
                    f"wheels.{code}.lateral_patch_vel",
                    w.lateral_patch_vel,
                    f"{w.lateral_patch_vel:.2f} m/s",
                    f"{lbl} lateral velocity at tire contact patch (m/s)",
                ),
                (
                    f"wheels.{code}.longitudinal_patch_vel",
                    w.longitudinal_patch_vel,
                    f"{w.longitudinal_patch_vel:.2f} m/s",
                    f"{lbl} longitudinal contact patch speed (m/s)",
                ),
                (
                    f"wheels.{code}.patch_speed_kmh",
                    w.patch_speed_kmh,
                    f"{w.patch_speed_kmh:.1f} km/h",
                    f"{lbl} longitudinal contact patch speed (km/h)",
                ),
                (
                    f"wheels.{code}.lateral_ground_vel",
                    w.lateral_ground_vel,
                    f"{w.lateral_ground_vel:.2f} m/s",
                    f"{lbl} lateral velocity of track ground surface (m/s)",
                ),
                (
                    f"wheels.{code}.longitudinal_ground_vel",
                    w.longitudinal_ground_vel,
                    f"{w.longitudinal_ground_vel:.2f} m/s",
                    f"{lbl} longitudinal ground surface speed (m/s)",
                ),
                (
                    f"wheels.{code}.ground_speed_kmh",
                    w.ground_speed_kmh,
                    f"{w.ground_speed_kmh:.1f} km/h",
                    f"{lbl} longitudinal ground speed under tire (km/h)",
                ),
                (
                    f"wheels.{code}.slip_ratio",
                    w.slip_ratio,
                    f"{w.slip_ratio:+.3f}",
                    f"{lbl} longitudinal tire slip ratio ((patch - ground) / ground)",
                ),
                (f"wheels.{code}.camber", w.camber, f"{w.camber:+.4f} rad", f"{lbl} wheel camber angle (radians)"),
                (f"wheels.{code}.toe", w.toe, f"{w.toe:+.4f} rad", f"{lbl} wheel toe alignment angle (radians)"),
                (
                    f"wheels.{code}.lateral_force",
                    w.lateral_force,
                    f"{w.lateral_force:.1f} N",
                    f"{lbl} lateral cornering grip force (Newtons)",
                ),
                (
                    f"wheels.{code}.longitudinal_force",
                    w.longitudinal_force,
                    f"{w.longitudinal_force:.1f} N",
                    f"{lbl} longitudinal drive/braking force (Newtons)",
                ),
                (
                    f"wheels.{code}.tire_load",
                    w.tire_load,
                    f"{w.tire_load:.1f} N",
                    f"{lbl} vertical normal downward load on tire (Newtons)",
                ),
                (
                    f"wheels.{code}.grip_fraction",
                    w.grip_fraction,
                    f"{w.grip_fraction * 100:.1f} %",
                    f"{lbl} sliding fraction of tire contact patch [0..1]",
                ),
                (
                    f"wheels.{code}.pressure",
                    w.pressure,
                    f"{w.pressure:.1f} kPa",
                    f"{lbl} tire internal inflation pressure (kPa)",
                ),
                (
                    f"wheels.{code}.temperature_celsius",
                    w.temperature_celsius,
                    f"({w.temperature_celsius[0]:.1f}, {w.temperature_celsius[1]:.1f}, {w.temperature_celsius[2]:.1f}) °C",
                    f"{lbl} tire surface temperatures Left/Center/Right (°C)",
                ),
                (
                    f"wheels.{code}.carcass_temp_celsius",
                    w.carcass_temp_celsius,
                    f"{w.carcass_temp_celsius:.1f} °C",
                    f"{lbl} tire deep carcass core temperature (°C)",
                ),
                (
                    f"wheels.{code}.wear",
                    w.wear,
                    f"{w.wear * 100:.1f} %",
                    f"{lbl} tire tread surface wear fraction [0.0 - 1.0]",
                ),
                (
                    f"wheels.{code}.terrain_name",
                    w.terrain_name,
                    format_value(w.terrain_name),
                    f"{lbl} track surface material code from TDF file",
                ),
                (
                    f"wheels.{code}.surface_type",
                    w.surface_type,
                    format_value(w.surface_type),
                    f"{lbl} surface grip type (0=dry, 1=wet, 2=grass, 3=dirt...)",
                ),
                (f"wheels.{code}.flat", w.flat, format_value(w.flat), f"{lbl} punctured flat tire state"),
                (
                    f"wheels.{code}.detached",
                    w.detached,
                    format_value(w.detached),
                    f"{lbl} detached / broken off wheel state",
                ),
                (
                    f"wheels.{code}.vertical_tire_deflection",
                    w.vertical_tire_deflection,
                    f"{w.vertical_tire_deflection * 1000:.2f} mm",
                    f"{lbl} vertical tire carcass compression (mm)",
                ),
            ]
        )

    return rows


def extract_scoring_rows(
    s: CompactScoring | None,
    fs: FullScoringSession | None = None,
    st: PacketStats | None = None,
) -> list[tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for CompactScoring and FullScoringSession streams.
    """
    rows: list[tuple[str, Any, str, str]] = []

    # Channel / Stream Diagnostics
    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of Scoring stream"),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total Scoring packets received on this channel"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between consecutive Scoring packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for Scoring stream",
                ),
            ]
        )

    session_names = {
        0: "Test Day",
        1: "Practice 1",
        2: "Practice 2",
        3: "Practice 3",
        4: "Practice 4",
        5: "Qualifying 1",
        6: "Qualifying 2",
        7: "Qualifying 3",
        8: "Qualifying 4",
        9: "Warmup",
        10: "Race 1",
        11: "Race 2",
        12: "Race 3",
        13: "Race 4",
    }

    # 1. Full Multi-Car Grid Scoring (SIMP Type 4)
    if fs is not None:
        session_label = session_names.get(fs.session, f"Session({fs.session})")
        rows.extend(
            [
                (
                    "grid.track_name",
                    fs.track_name,
                    format_value(fs.track_name),
                    "Track / circuit identification string",
                ),
                ("grid.session_type", session_label, f"[bold #58a6ff]{session_label}[/]", "Current session type"),
                (
                    "grid.game_phase",
                    fs.game_phase_str,
                    f"[bold #3fb950]{fs.game_phase_str}[/]",
                    "Session game phase (Garage, Warmup, GreenFlag, FCY...)",
                ),
                ("grid.current_et", fs.current_et, f"{fs.current_et:.3f} s", "Session elapsed time"),
                ("grid.end_et", fs.end_et, f"{fs.end_et:.1f} s", "Session end elapsed time"),
                (
                    "grid.num_vehicles",
                    fs.num_vehicles,
                    f"[bold #f1e05a]{fs.num_vehicles}[/]",
                    "Active vehicles in session / grid",
                ),
                ("grid.ambient_temp", fs.ambient_temp, f"{fs.ambient_temp:.1f} °C", "Ambient air temperature"),
                ("grid.track_temp", fs.track_temp, f"{fs.track_temp:.1f} °C", "Track surface temperature"),
                ("grid.raining", fs.raining, f"{fs.raining * 100:.1f} %", "Rain intensity"),
                ("grid.dark_cloud", fs.dark_cloud, f"{fs.dark_cloud * 100:.1f} %", "Cloud cover darkness"),
            ]
        )

        # Leaderboard entries
        for rank, v in enumerate(fs.leaderboard, start=1):
            tag = f"car[{rank:02d}]"
            player_marker = " [bold #3fb950](PLAYER)[/]" if v.is_player else ""
            pit_str = f" [bold #f85149][PIT - {v.pit_state_str}][/]" if v.in_pits else ""
            gap_str = (
                f"+{v.time_behind_leader:.3f} s"
                if (v.time_behind_leader > 0 and rank > 1)
                else ("LEADER" if rank == 1 else "-")
            )
            best_lap_str = f"{v.best_lap_time:.3f} s" if v.best_lap_time > 0 else "-"
            last_lap_str = f"{v.last_lap_time:.3f} s" if v.last_lap_time > 0 else "-"

            rows.extend(
                [
                    (
                        f"{tag}.driver",
                        v.driver_name,
                        f"[bold]{v.driver_name}[/]{player_marker}{pit_str}",
                        f"P{v.place} | {v.vehicle_name} ({v.vehicle_class})",
                    ),
                    (f"{tag}.position", v.place, f"P{v.place}", "Current race position"),
                    (f"{tag}.laps", v.total_laps, format_value(v.total_laps), f"Completed laps | Sector {v.sector}"),
                    (f"{tag}.gap_leader", v.time_behind_leader, gap_str, "Gap to session leader (seconds)"),
                    (f"{tag}.best_lap", v.best_lap_time, best_lap_str, "Personal best lap time"),
                    (f"{tag}.last_lap", v.last_lap_time, last_lap_str, "Last completed lap time"),
                ]
            )
        return rows

    # 2. Compact Scoring Fallback (SIMP Type 2)
    if s is not None:
        session_label = session_names.get(s.session, f"Session({s.session})")
        rows.extend(
            [
                ("track_name", s.track_name, format_value(s.track_name), "Track / circuit identification string"),
                ("session", s.session, format_value(s.session), "Session numeric code"),
                ("session_type", session_label, f"[bold #58a6ff]{session_label}[/]", "Decoded session type"),
                ("current_et", s.current_et, f"{s.current_et:.3f} s", "Current session elapsed time (seconds)"),
                ("lap_dist", s.lap_dist, f"{s.lap_dist:.1f} m", "Total circuit lap distance (meters)"),
                ("max_laps", s.max_laps, format_value(s.max_laps), "Session scheduled lap limit"),
                ("in_realtime", s.in_realtime, format_value(s.in_realtime), "Real-time driving active state on track"),
                ("total_laps", s.total_laps, format_value(s.total_laps), "Completed lap count for player vehicle"),
                ("sector", s.sector, format_value(s.sector), "Current active sector"),
                (
                    "in_garage_stall",
                    s.in_garage_stall,
                    format_value(s.in_garage_stall),
                    "Vehicle inside pit garage stall flag",
                ),
                ("count_lap_flag", s.count_lap_flag, format_value(s.count_lap_flag), "Lap validity flag"),
                (
                    "cur_sector1",
                    s.cur_sector1,
                    f"{s.cur_sector1:.3f} s" if s.cur_sector1 > 0 else "[dim]-[/dim]",
                    "Current lap S1 split time",
                ),
                (
                    "cur_sector2",
                    s.cur_sector2,
                    f"{s.cur_sector2:.3f} s" if s.cur_sector2 > 0 else "[dim]-[/dim]",
                    "Current lap S2 split time",
                ),
                (
                    "last_lap_time",
                    s.last_lap_time,
                    f"[bold #3fb950]{s.last_lap_time:.3f} s[/]" if s.last_lap_time > 0 else "[dim]-[/dim]",
                    "Last lap total time",
                ),
                (
                    "best_lap_time",
                    s.best_lap_time,
                    f"[bold #bc8cff]{s.best_lap_time:.3f} s[/]" if s.best_lap_time > 0 else "[dim]-[/dim]",
                    "Personal best lap time",
                ),
            ]
        )
        return rows

    rows.append(
        (
            "status",
            "Waiting for packets",
            "[dim]No Scoring packet received yet[/dim]",
            "Scoring packets are streamed at 1-5 Hz",
        )
    )
    return rows


def extract_event_rows(
    ev: SystemEvent | None, st: PacketStats | None = None, event_time: float = 0.0
) -> list[tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for SystemEvent packet.
    """
    rows: list[tuple[str, Any, str, str]] = []

    if st is not None:
        rows.extend(
            [
                (
                    "_channel.packets_count",
                    st.count,
                    f"{st.count:,}",
                    "Total SystemEvent packets received on this channel",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for SystemEvent stream",
                ),
            ]
        )

    if ev is None:
        rows.append(
            (
                "status",
                "Waiting for events",
                "[dim]No SystemEvent packet received yet[/dim]",
                "System events are triggered on state transitions (Enter/Exit Realtime, Session start/end)",
            )
        )
        return rows

    ev_time_str = time.strftime("%H:%M:%S", time.localtime(event_time)) if event_time > 0 else "-"

    rows.extend(
        [
            (
                "event_id",
                ev.event_id,
                format_value(ev.event_id),
                "System event numeric code (1=EnterRealtime, 2=ExitRealtime, 3=StartSession, 4=EndSession)",
            ),
            ("name", ev.name, f"[bold #58a6ff]{ev.name}[/]", "Decoded human-readable event name"),
            (
                "in_realtime",
                ev.in_realtime,
                format_value(ev.in_realtime),
                "Whether event switches driving state to active real-time",
            ),
            ("timestamp", event_time, format_value(ev_time_str), "Local system receipt timestamp of the event"),
        ]
    )

    return rows


def extract_stats_rows(engine: TelemetryEngine) -> list[tuple[str, Any, str, str]]:
    """
    Returns list of (key, raw_value, formatted_string, description)
    for overall stream statistics and network bandwidth.
    """
    elapsed = time.time() - engine.start_time
    total_mb = engine.total_bytes / (1024.0 * 1024.0)

    rows: list[tuple[str, Any, str, str]] = [
        (
            "connection.endpoint",
            f"{engine.host}:{engine.port}",
            f"[bold #58a6ff]{engine.host}:{engine.port}[/]",
            "UDP socket listening endpoint",
        ),
        (
            "connection.elapsed_time",
            elapsed,
            f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d} s",
            "Total benchmark session elapsed time",
        ),
        (
            "connection.total_packets",
            engine.total_packets,
            f"{engine.total_packets:,}",
            "Total packets received across all streams",
        ),
        (
            "connection.total_bytes",
            engine.total_bytes,
            f"{total_mb:.2f} MB ({engine.total_bytes:,} bytes)",
            "Total payload volume received",
        ),
    ]

    for st_name, st in engine.stats.items():
        prefix = st_name.split()[0].lower()
        rows.extend(
            [
                (f"{prefix}.packets_count", st.count, f"{st.count:,}", f"{st.name} total packets received"),
                (
                    f"{prefix}.frequency_hz",
                    st.current_freq,
                    f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]",
                    f"{st.name} live packet frequency (1s window)",
                ),
                (
                    f"{prefix}.avg_delay_ms",
                    st.avg_interval_ms,
                    f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-",
                    f"{st.name} average inter-packet arrival delay",
                ),
                (
                    f"{prefix}.jitter_ms",
                    st.jitter_ms,
                    f"±{st.jitter_ms:3.1f} ms" if st.intervals else "-",
                    f"{st.name} packet jitter variation",
                ),
                (
                    f"{prefix}.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    f"{st.name} throughput bandwidth",
                ),
            ]
        )

    return rows


def model_to_clean_dict(obj: Any) -> dict[str, Any]:
    """Recursively converts dataclasses/models to clean JSON-serializable dictionaries."""
    if obj is None:
        return {}
    if hasattr(obj, "__dataclass_fields__"):
        res: dict[str, Any] = {}
        for f in obj.__dataclass_fields__:
            val = getattr(obj, f)
            if hasattr(val, "__dataclass_fields__"):
                res[f] = model_to_clean_dict(val)
            elif isinstance(val, (list, tuple)):
                res[f] = [model_to_clean_dict(x) if hasattr(x, "__dataclass_fields__") else x for x in val]
            else:
                res[f] = val
        return res
    if isinstance(obj, dict):
        return dict(obj)
    return {"value": str(obj)}


def extract_track_rules_rows(
    rules: TrackRulesSession | None, st: PacketStats | None = None
) -> list[tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for TrackRulesSession packet."""
    rows: list[tuple[str, Any, str, str]] = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                (
                    "_channel.frequency_hz",
                    st.current_freq,
                    freq_str,
                    "Real-time reception frequency of TrackRules stream",
                ),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total TrackRules packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between TrackRules packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for TrackRules stream",
                ),
            ]
        )

    if rules is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No TrackRules packet received yet[/dim]",
                "Active during caution / safety car / formation laps",
            )
        )
        return rows

    rows.extend(
        [
            (
                "session.stage",
                rules.stage_str,
                f"[bold #58a6ff]{rules.stage_str}[/]",
                "Current race stage (Formation, Normal, Caution)",
            ),
            (
                "session.pole_column",
                rules.pole_column_str,
                format_value(rules.pole_column_str),
                "Pole position lane/column",
            ),
            (
                "session.num_participants",
                rules.num_participants,
                format_value(rules.num_participants),
                "Total active participant cars in track order",
            ),
            (
                "session.yellow_flag_detected",
                rules.yellow_flag_detected,
                format_value(rules.yellow_flag_detected),
                "Yellow flag / caution condition detected",
            ),
            (
                "session.is_caution_active",
                rules.is_caution_active,
                format_value(rules.is_caution_active),
                "Full Course Yellow / Caution active",
            ),
            (
                "session.is_safety_car_active",
                rules.is_safety_car_active,
                format_value(rules.is_safety_car_active),
                "Safety car deployed on track",
            ),
            (
                "safety_car.laps",
                rules.safety_car_laps,
                format_value(rules.safety_car_laps),
                "Safety car caution laps completed",
            ),
            (
                "safety_car.lap_dist",
                rules.safety_car_lap_dist,
                f"{rules.safety_car_lap_dist:.1f} m",
                "Safety car track distance position (m)",
            ),
            (
                "safety_car.speed_kmh",
                rules.safety_car_speed * 3.6,
                f"{rules.safety_car_speed * 3.6:.1f} km/h",
                "Safety car target speed",
            ),
            ("session.message", rules.message, format_value(rules.message), "Global race control message"),
        ]
    )

    for i, p in enumerate(rules.participants):
        pfx = f"participant[{i}]."
        rows.extend(
            [
                (f"{pfx}id", p.id, format_value(p.id), f"Car slot ID (Place P{p.place})"),
                (f"{pfx}place", p.place, f"P{p.place}", "1-based track position"),
                (
                    f"{pfx}frozen_order",
                    p.frozen_order,
                    format_value(p.frozen_order),
                    "0-based order when caution was called",
                ),
                (f"{pfx}column", p.column_str, format_value(p.column_str), "Assigned column/lane"),
                (f"{pfx}pits_open", p.pits_open_bool, format_value(p.pits_open_bool), "Pits open for this vehicle"),
                (f"{pfx}up_to_speed", p.up_to_speed, format_value(p.up_to_speed), "Vehicle can be followed safely"),
                (f"{pfx}message", p.message, format_value(p.message), "Individual driver instruction"),
            ]
        )

    return rows


def extract_pit_menu_rows(pit: PitMenu | None, st: PacketStats | None = None) -> list[tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for PitMenu packet."""
    rows: list[tuple[str, Any, str, str]] = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of PitMenu stream"),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total PitMenu packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between PitMenu packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for PitMenu stream",
                ),
            ]
        )

    if pit is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No PitMenu packet received yet[/dim]",
                "Pit menu state streamed @ 100Hz",
            )
        )
        return rows

    rows.extend(
        [
            ("pit_menu.category_index", pit.category_index, format_value(pit.category_index), "Current category index"),
            (
                "pit_menu.category_name",
                pit.category_name,
                f"[bold #58a6ff]{pit.category_name}[/]",
                "Current pit menu category name (e.g. Tires, Fuel, Aero)",
            ),
            (
                "pit_menu.choice_index",
                pit.choice_index,
                format_value(pit.choice_index),
                "Current choice index within category",
            ),
            (
                "pit_menu.choice_string",
                pit.choice_string,
                f"[bold #3fb950]{pit.choice_string}[/]",
                "Selected choice / setting value",
            ),
            (
                "pit_menu.num_choices",
                pit.num_choices,
                format_value(pit.num_choices),
                "Total available options in category",
            ),
            ("pit_menu.is_available", pit.is_available, format_value(pit.is_available), "Pit menu active / accessible"),
        ]
    )

    return rows


def extract_weather_rows(w: WeatherControl | None, st: PacketStats | None = None) -> list[tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for WeatherControl packet."""
    rows: list[tuple[str, Any, str, str]] = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of Weather stream"),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total Weather packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between Weather packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for Weather stream",
                ),
            ]
        )

    if w is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No Weather packet received yet[/dim]",
                "Environmental conditions streamed @ 1Hz",
            )
        )
        return rows

    rows.extend(
        [
            ("weather.et", w.et, f"{w.et:.3f} s", "Session time when weather takes effect"),
            (
                "weather.cloudiness",
                w.cloudiness,
                f"{w.cloudiness * 100:.1f} %",
                "General cloud cover (0% clear, 100% dark overcast)",
            ),
            (
                "weather.ambient_temp_c",
                w.ambient_temp_c,
                f"[bold #e3b341]{w.ambient_temp_c:.1f} °C[/]",
                "Ambient air temperature (Celsius)",
            ),
            (
                "weather.ambient_temp_k",
                w.ambient_temp_k,
                f"{w.ambient_temp_k:.2f} K",
                "Ambient air temperature (Kelvin)",
            ),
            (
                "weather.wind_max_speed",
                w.wind_max_speed,
                f"{w.wind_max_speed:.1f} m/s ({w.wind_max_speed * 3.6:.1f} km/h)",
                "Maximum ground wind speed",
            ),
            (
                "weather.origin_raining",
                w.origin_raining,
                f"[bold #58a6ff]{w.origin_raining * 100:.1f} %[/]",
                "Rain intensity at track origin [1][1] (0.0 to 1.0)",
            ),
            (
                "weather.apply_cloudiness_instantly",
                w.apply_cloudiness_instantly,
                format_value(w.apply_cloudiness_instantly),
                "Instantaneous cloud change flag",
            ),
        ]
    )

    for r in range(3):
        for c in range(3):
            val = w.raining[r][c]
            rows.append(
                (
                    f"weather.raining[{r}][{c}]",
                    val,
                    f"{val * 100:.1f} %",
                    f"Rain intensity at track node grid position ({r}, {c})",
                )
            )

    return rows


def extract_ffb_rows(ffb: ForceFeedback | None, st: PacketStats | None = None) -> list[tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for ForceFeedback packet."""
    rows: list[tuple[str, Any, str, str]] = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.2f} ms" if st.intervals else "-"
        jitter_str = f"±{st.jitter_ms:3.2f} ms" if st.intervals else "-"
        rows.extend(
            [
                (
                    "_channel.frequency_hz",
                    st.current_freq,
                    freq_str,
                    "Real-time reception frequency of Ultra-High FFB stream (up to 400Hz)",
                ),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total ForceFeedback packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival interval (target: 2.5ms @ 400Hz)",
                ),
                ("_channel.jitter_ms", st.jitter_ms, jitter_str, "FFB packet arrival jitter variation"),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for FFB stream",
                ),
            ]
        )

    if ffb is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No ForceFeedback packet received yet[/dim]",
                "Direct steering shaft torque from physics engine",
            )
        )
        return rows

    # Visual force gauge
    pct = ffb.percentage
    abs_pct = abs(pct)
    bars_total = 20
    filled = int((abs_pct / 100.0) * bars_total)
    filled = min(bars_total, max(0, filled))
    bar_color = "#f85149" if abs_pct >= 98.0 else ("#e3b341" if abs_pct >= 85.0 else "#3fb950")
    gauge = f"[{bar_color}]{'█' * filled}[/][#30363d]{'░' * (bars_total - filled)}[/]"

    rows.extend(
        [
            (
                "ffb.force_value",
                ffb.force_value,
                f"[bold #58a6ff]{ffb.force_value:+.4f}[/]",
                "Normalized steering shaft torque (-1.0 to +1.0)",
            ),
            (
                "ffb.percentage",
                ffb.percentage,
                f"[bold {bar_color}]{pct:+6.1f} %[/] {gauge}",
                "Steering shaft torque percentage with real-time bar gauge",
            ),
            (
                "ffb.is_clipping",
                abs_pct >= 99.0,
                format_value(abs_pct >= 99.0),
                "True if force exceeds 99% causing direct-drive motor clipping",
            ),
        ]
    )

    return rows


def extract_graphics_rows(gfx: Graphics | None, st: PacketStats | None = None) -> list[tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for Graphics packet."""
    rows: list[tuple[str, Any, str, str]] = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                (
                    "_channel.frequency_hz",
                    st.current_freq,
                    freq_str,
                    "Real-time reception frequency of Graphics stream (60-100Hz)",
                ),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total Graphics packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between Graphics packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for Graphics stream",
                ),
            ]
        )

    if gfx is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No Graphics packet received yet[/dim]",
                "Camera 3D position, orientation & ambient lighting",
            )
        )
        return rows

    rows.extend(
        [
            (
                "camera.type",
                gfx.camera_type_str,
                f"[bold #58a6ff]{gfx.camera_type_str}[/] [dim](id: {gfx.camera_type})[/dim]",
                "Active camera perspective viewpoint",
            ),
            (
                "camera.is_cockpit",
                gfx.is_cockpit_view,
                format_value(gfx.is_cockpit_view),
                "True if active camera is inside driver cockpit",
            ),
            (
                "camera.slot_id",
                gfx.slot_id,
                format_value(gfx.slot_id),
                "Vehicle slot index currently tracked/viewed by camera (-1 = none)",
            ),
            (
                "camera.pos",
                gfx.cam_pos.as_tuple(),
                f"X:{gfx.cam_pos.x:8.2f}  Y:{gfx.cam_pos.y:8.2f}  Z:{gfx.cam_pos.z:8.2f} m",
                "World 3D coordinates of camera viewpoint",
            ),
            (
                "ambient.rgb",
                gfx.ambient_rgb,
                f"R:{gfx.ambient_rgb[0]:.3f}  G:{gfx.ambient_rgb[1]:.3f}  B:{gfx.ambient_rgb[2]:.3f}",
                "Track ambient environment light RGB intensity",
            ),
            (
                "camera.ori_matrix[0]",
                gfx.cam_ori[0].as_tuple(),
                format_value(gfx.cam_ori[0].as_tuple()),
                "Camera orientation matrix Row 0 (Pitch/Yaw/Roll)",
            ),
            (
                "camera.ori_matrix[1]",
                gfx.cam_ori[1].as_tuple(),
                format_value(gfx.cam_ori[1].as_tuple()),
                "Camera orientation matrix Row 1",
            ),
            (
                "camera.ori_matrix[2]",
                gfx.cam_ori[2].as_tuple(),
                format_value(gfx.cam_ori[2].as_tuple()),
                "Camera orientation matrix Row 2",
            ),
        ]
    )

    return rows


def extract_physics_rows(ext: ExtendedState | None, st: PacketStats | None = None) -> list[tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for ExtendedState packet."""
    rows: list[tuple[str, Any, str, str]] = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                (
                    "_channel.frequency_hz",
                    st.current_freq,
                    freq_str,
                    "Real-time reception frequency of ExtendedState stream (5Hz)",
                ),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total ExtendedState packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between ExtendedState packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for ExtendedState stream",
                ),
            ]
        )

    if ext is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No ExtendedState packet received yet[/dim]",
                "Driving aids, multipliers & accumulated impact damage",
            )
        )
        return rows

    p = ext.physics
    rows.extend(
        [
            # Driving Aids
            (
                "physics.traction_control",
                p.traction_control_str,
                f"[bold #58a6ff]{p.traction_control_str}[/] [dim]({p.traction_control})[/dim]",
                "Traction Control assistance level (0=Off, 1=Low, 2=Med, 3=High)",
            ),
            (
                "physics.anti_lock_brakes",
                p.anti_lock_brakes_str,
                f"[bold #58a6ff]{p.anti_lock_brakes_str}[/] [dim]({p.anti_lock_brakes})[/dim]",
                "ABS assistance level (0=Off, 1=Low, 2=High)",
            ),
            (
                "physics.stability_control",
                p.stability_control_str,
                f"[bold #58a6ff]{p.stability_control_str}[/] [dim]({p.stability_control})[/dim]",
                "Electronic Stability Control (ESC) level",
            ),
            (
                "physics.auto_shift",
                p.auto_shift_str,
                f"[bold #58a6ff]{p.auto_shift_str}[/] [dim]({p.auto_shift})[/dim]",
                "Automatic transmission shifting mode",
            ),
            (
                "physics.auto_clutch",
                bool(p.auto_clutch),
                format_value(bool(p.auto_clutch)),
                "Automatic clutch aid enabled",
            ),
            ("physics.auto_blip", bool(p.auto_blip), format_value(bool(p.auto_blip)), "Throttle blip on downshift aid"),
            ("physics.auto_lift", bool(p.auto_lift), format_value(bool(p.auto_lift)), "Throttle lift on upshift aid"),
            (
                "physics.opposite_lock",
                bool(p.opposite_lock),
                format_value(bool(p.opposite_lock)),
                "Counter-steering / opposite lock aid",
            ),
            ("physics.steering_help", p.steering_help, format_value(p.steering_help), "Steering help assist (0-3)"),
            ("physics.braking_help", p.braking_help, format_value(p.braking_help), "Braking help assist (0-2)"),
            (
                "physics.spin_recovery",
                bool(p.spin_recovery),
                format_value(bool(p.spin_recovery)),
                "Spin recovery assist",
            ),
            (
                "physics.auto_pit",
                bool(p.auto_pit),
                format_value(bool(p.auto_pit)),
                "Auto pit drive / speed control aid",
            ),
            (
                "physics.invulnerable",
                bool(p.invulnerable),
                format_value(bool(p.invulnerable)),
                "Invulnerability / no damage cheat active",
            ),
            (
                "physics.ai_control",
                bool(p.ai_control),
                format_value(bool(p.ai_control)),
                "AI driving active (0=Human player, 1=AI takeover)",
            ),
            # Multipliers
            ("physics.fuel_mult", p.fuel_mult, f"{p.fuel_mult}x", "Fuel consumption multiplier rate"),
            ("physics.tire_mult", p.tire_mult, f"{p.tire_mult}x", "Tire wear degradation rate multiplier"),
            (
                "physics.mech_fail",
                p.mech_fail,
                format_value(p.mech_fail),
                "Mechanical failures mode (0=Off, 1=Normal, 2=Time-scaled)",
            ),
            # Steering & Controls Sensitivity
            (
                "physics.speed_sensitive_steering",
                p.speed_sensitive_steering,
                format_value(p.speed_sensitive_steering),
                "Speed-sensitive steering attenuation (0.0 to 1.0)",
            ),
            (
                "physics.steer_ratio_speed",
                p.steer_ratio_speed,
                f"{p.steer_ratio_speed:.1f} m/s",
                "Speed below which steering lock expands",
            ),
            (
                "physics.manual_shift_override_time",
                p.manual_shift_override_time,
                f"{p.manual_shift_override_time:.2f} s",
                "Override timeout before auto-shift can resume",
            ),
            # Damage Tracking
            (
                "damage.max_impact_magnitude",
                ext.max_impact_magnitude,
                f"[bold {'#f85149' if ext.max_impact_magnitude > 5000 else '#e3b341'}]{ext.max_impact_magnitude:,.1f} N[/]",
                "Peak collision impact force recorded in current session",
            ),
            (
                "damage.accumulated_impact_magnitude",
                ext.accumulated_impact_magnitude,
                f"[bold {'#f85149' if ext.accumulated_impact_magnitude > 10000 else '#58a6ff'}]{ext.accumulated_impact_magnitude:,.1f} N·s[/]",
                "Cumulative crash impact damage energy",
            ),
            # Session Status
            (
                "session.in_realtime_fc",
                ext.in_realtime_fc,
                format_value(ext.in_realtime_fc),
                "Real-time cockpit driving mode flag",
            ),
            ("session.session_started", ext.session_started, format_value(ext.session_started), "Session started flag"),
            ("session.session_index", ext.session, format_value(ext.session), "Session type index"),
            (
                "session.pit_speed_limit",
                ext.current_pit_speed_limit_kmh,
                f"[bold #e3b341]{ext.current_pit_speed_limit_kmh:.1f} km/h[/] [dim]({ext.current_pit_speed_limit:.2f} m/s)[/dim]",
                "Speed limit enforced in pit lane",
            ),
        ]
    )

    return rows


def extract_inbound_rows(engine: TelemetryEngine) -> list[tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for Inbound Control testing."""
    rows: list[tuple[str, Any, str, str]] = []
    rows.append(("_inbound.status", "Active", "[bold green]Online / Ready[/]", "Status of Inbound UDP Control socket"))
    rows.append(
        (
            "_inbound.target_host",
            engine.inbound_target_host,
            f"[cyan]{engine.inbound_target_host}[/]",
            "Destination IP for HW / Weather commands",
        )
    )
    rows.append(
        (
            "_inbound.target_port",
            engine.inbound_target_port,
            f"[yellow]{engine.inbound_target_port}[/]",
            "Destination Inbound UDP Port (default: 5001)",
        )
    )
    rows.append(
        (
            "_inbound.last_command",
            engine.last_inbound_cmd_sent,
            f"[bold #58a6ff]{engine.last_inbound_cmd_sent}[/]",
            "Last transmitted command name or payload",
        )
    )
    rows.append(
        (
            "_inbound.last_command_time",
            engine.last_inbound_cmd_time,
            f"{time.strftime('%H:%M:%S', time.localtime(engine.last_inbound_cmd_time))}"
            if engine.last_inbound_cmd_time > 0
            else "-",
            "Timestamp of last command sent",
        )
    )
    rows.append(("_inbound.pulse_duration", 50, "50 ms", "Default pulse hold time before auto-release"))
    rows.append(
        (
            "_inbound.interactive_keys",
            "U / D / L / R / Enter / W",
            "[bold yellow]U[/]: Pit Up | [bold yellow]D[/]: Pit Down | [bold yellow]L[/]: Prev | [bold yellow]R[/]: Next | [bold yellow]Enter[/]: Select | [bold yellow]W[/]: Rain Injection",
            "Interactive Keyboard Shortcuts to trigger live UDP commands",
        )
    )
    rows.append(
        (
            "_inbound.supported_controls",
            "12 items",
            "PitMenuUp/Down/Prev/Next/Select, TCIncrease/Decrease, ABSIncrease/Decrease, BrakeBias, Ignition, Wipers",
            "Supported CheckHWControl identifiers",
        )
    )

    # Live Feedback from connected channels
    if engine.latest_pit_menu:
        pm = engine.latest_pit_menu
        rows.append(
            (
                "live_feedback.pit_category",
                pm.category_name,
                f"[bold green]{pm.category_name}[/]",
                "Live pit category reflected from Type 6 stream",
            )
        )
        rows.append(
            (
                "live_feedback.pit_choice",
                pm.choice_string,
                f"[bold green]{pm.choice_string}[/] ({pm.choice_index + 1}/{pm.num_choices})",
                "Live pit choice reflected from Type 6 stream",
            )
        )

    if engine.latest_weather:
        w = engine.latest_weather
        rows.append(
            (
                "live_feedback.ambient_temp_c",
                w.ambient_temp_c,
                f"[bold green]{w.ambient_temp_c:.1f} °C[/]",
                "Live ambient temperature reflected from Type 7 stream",
            )
        )
        rows.append(
            (
                "live_feedback.rain_intensity",
                w.origin_raining,
                f"[bold green]{w.origin_raining * 100:.1f} %[/]",
                "Live rain intensity reflected from Type 7 stream",
            )
        )

    return rows


def extract_config_rows(overview: dict[str, Any]) -> list[tuple[str, Any, str, str]]:
    """Returns list of (key, raw_value, formatted_string, description) for JSON Configuration overview."""
    rows: list[tuple[str, Any, str, str]] = []

    src = overview.get("source_dll", {})
    dll_exists = src.get("exists", False)
    dll_size = src.get("size_bytes", 0)
    dll_path = src.get("path", "")
    dll_mtime_str = src.get("mtime_str", "-")

    # 1. Source DLL Information
    rows.append(
        (
            "dll.status",
            "Compiled" if dll_exists else "Missing",
            f"[bold green]✓ Compiled ({dll_size:,} B)[/]"
            if dll_exists
            else "[bold red]✗ Not Compiled (run 'make cross' or 'make build')[/]",
            "Status of compiled isiMotor_RawUDP.dll binary",
        )
    )
    rows.append(
        (
            "dll.source_path",
            dll_path if dll_path else "Not found",
            f"[cyan]{dll_path}[/]" if dll_path else "[dim]None[/dim]",
            "Local filesystem path of compiled DLL binary",
        )
    )
    rows.append(
        (
            "dll.last_build",
            dll_mtime_str,
            f"[dim]{dll_mtime_str}[/dim]",
            "Last compilation timestamp",
        )
    )

    # 2. Detected Game Installations
    games = overview.get("games", [])
    if not games:
        rows.append(
            (
                "games.detected",
                0,
                "[bold yellow]⚠️ No games detected in standard Steam library folders[/]",
                "Auto-detection via Steam VDF registry / Linux / SteamDeck paths",
            )
        )
    else:
        for g in games:
            g_name = g.get("name", "Unknown Game")
            g_key = g.get("key", "").lower()
            g_installed = g.get("dll_installed", False)
            g_size = g.get("dll_size", 0)
            g_mtime = g.get("dll_mtime_str", "-")
            g_json = g.get("json_path", "")
            g_json_exists = g.get("json_exists", False)
            g_ext_enabled = g.get("external_plugins_enabled", False)
            g_mask = g.get("plugin_mask", 0)

            rows.append(
                (
                    f"game.{g_key}.name",
                    g_name,
                    f"[bold #58a6ff]{g_name}[/]",
                    f"Root: {g.get('root_dir', '')}",
                )
            )
            rows.append(
                (
                    f"game.{g_key}.dll_status",
                    "Installed" if g_installed else "Not Installed",
                    f"[bold green]✓ Installed ({g_size:,} B, {g_mtime})[/]"
                    if g_installed
                    else "[bold red]✗ Missing in Plugins/[/]",
                    f"Path: {g.get('dll_path', '')}",
                )
            )
            rows.append(
                (
                    f"game.{g_key}.json_config",
                    "Found" if g_json_exists else "Default",
                    f"[bold green]✓ Active[/] [dim]({g_json})[/dim]"
                    if g_json_exists
                    else f"[bold yellow]Default / Not created yet[/] [dim]({g_json})[/dim]",
                    "CustomPluginVariables.JSON profile configuration",
                )
            )
            rows.append(
                (
                    f"game.{g_key}.settings_mask",
                    g_mask,
                    f"[bold green]Enabled: {g_ext_enabled} (Mask: {g_mask})[/]"
                    if g_ext_enabled
                    else "[bold yellow]Disabled in Settings.JSON[/]",
                    "Settings.JSON external plugin execution mask",
                )
            )

    # 3. Active Plugin Variables (CustomPluginVariables.JSON)
    active_vars = overview.get("active_variables", {})
    rows.append(
        (
            "config.Enabled",
            active_vars.get(" Enabled", 1),
            f"[bold {'green' if active_vars.get(' Enabled', 1) else 'red'}]{active_vars.get(' Enabled', 1)}[/]",
            "Main plugin enable switch in isiMotor engine (1=Active, 0=Disabled)",
        )
    )
    rows.append(
        (
            "config.TargetIP",
            active_vars.get("TargetIP", "127.0.0.1"),
            f"[bold cyan]{active_vars.get('TargetIP', '127.0.0.1')}[/]",
            "Target UDP destination IP (Unicast, Multicast 239.x or Broadcast 255.255.255.255)",
        )
    )
    rows.append(
        (
            "config.TargetPort",
            active_vars.get("TargetPort", "5000"),
            f"[bold yellow]{active_vars.get('TargetPort', '5000')}[/]",
            "Target UDP destination port (Default: 5000)",
        )
    )
    rows.append(
        (
            "config.InboundControl",
            active_vars.get("InboundControl", "Enabled"),
            f"[bold {'green' if str(active_vars.get('InboundControl')).lower() in ('enabled', 'true', '1') else 'red'}]{active_vars.get('InboundControl', 'Enabled')}[/]",
            "Bi-directional UDP remote control & hardware inputs (Enabled / Disabled)",
        )
    )
    rows.append(
        (
            "config.InboundPort",
            active_vars.get("InboundPort", "5001"),
            f"[bold yellow]{active_vars.get('InboundPort', '5001')}[/]",
            "Listening UDP port for remote commands (Default: 5001)",
        )
    )
    rows.append(
        (
            "config.TelemetryRate",
            active_vars.get("TelemetryRate", "unlimited"),
            f"[bold #e3b341]{active_vars.get('TelemetryRate', 'unlimited')}[/]",
            "Raw binary TelemInfo streaming rate (unlimited, 60Hz, 100Hz, Off)",
        )
    )
    rows.append(
        (
            "config.CompactScoringRate",
            active_vars.get("CompactScoringRate", "unlimited"),
            f"[bold #e3b341]{active_vars.get('CompactScoringRate', 'unlimited')}[/]",
            "Compact timing & lap scoring stream rate (unlimited, 10Hz, 5Hz, Off)",
        )
    )
    rows.append(
        (
            "config.FullScoringRate",
            active_vars.get("FullScoringRate", "5Hz"),
            f"[bold #e3b341]{active_vars.get('FullScoringRate', '5Hz')}[/]",
            "Multi-vehicle full grid scoring stream rate (5Hz, 10Hz, Off)",
        )
    )
    rows.append(
        (
            "config.TrackRulesRate",
            active_vars.get("TrackRulesRate", "3Hz"),
            f"[bold #e3b341]{active_vars.get('TrackRulesRate', '3Hz')}[/]",
            "Safety car, FCY & track rules stream rate (3Hz, 5Hz, Off)",
        )
    )
    rows.append(
        (
            "config.PitMenuRate",
            active_vars.get("PitMenuRate", "100Hz"),
            f"[bold #e3b341]{active_vars.get('PitMenuRate', '100Hz')}[/]",
            "Interactive pit stop menu stream rate (100Hz, 60Hz, Off)",
        )
    )
    rows.append(
        (
            "config.WeatherRate",
            active_vars.get("WeatherRate", "1Hz"),
            f"[bold #e3b341]{active_vars.get('WeatherRate', '1Hz')}[/]",
            "Ambient weather conditions stream rate (1Hz, 2Hz, Off)",
        )
    )
    rows.append(
        (
            "config.ExtendedStateRate",
            active_vars.get("ExtendedStateRate", "5Hz"),
            f"[bold #e3b341]{active_vars.get('ExtendedStateRate', '5Hz')}[/]",
            "Physics aids, multipliers, damage impact stream rate (5Hz, 10Hz, Off)",
        )
    )
    rows.append(
        (
            "config.ForceFeedbackRate",
            active_vars.get("ForceFeedbackRate", "unlimited"),
            f"[bold #e3b341]{active_vars.get('ForceFeedbackRate', 'unlimited')}[/]",
            "Steering wheel FFB torque stream rate (unlimited @ 400Hz, Off)",
        )
    )
    rows.append(
        (
            "config.GraphicsRate",
            active_vars.get("GraphicsRate", "60Hz"),
            f"[bold #e3b341]{active_vars.get('GraphicsRate', '60Hz')}[/]",
            "Camera & graphics info stream rate (60Hz, 100Hz, Off)",
        )
    )
    rows.append(
        (
            "config.SystemEvents",
            active_vars.get("SystemEvents", "Enabled"),
            f"[bold {'green' if str(active_vars.get('SystemEvents')).lower() in ('enabled', 'true', '1') else 'red'}]{active_vars.get('SystemEvents', 'Enabled')}[/]",
            "Realtime session state change notification events (Enabled / Disabled)",
        )
    )
    rows.append(
        (
            "config.UnsubscribedBuffersMask",
            active_vars.get("UnsubscribedBuffersMask", "0"),
            f"[bold cyan]{active_vars.get('UnsubscribedBuffersMask', '0')}[/]",
            "Shared memory stream disable mask bitfield (0 = all enabled)",
        )
    )

    # 4. Native Hot-Reload Architecture
    rows.append(
        (
            "hotreload.architecture",
            "InternalsPluginV07 Standard",
            "[bold green]✓ Native AccessCustomVariable Callback[/]",
            "Standard isiMotor hot-reload mechanism triggered on game configuration changes",
        )
    )
    rows.append(
        (
            "hotreload.action",
            "Copy DLL",
            "[bold yellow]Cliquez sur '📦 Copier DLL'[/] pour installer ou mettre à jour le plugin",
            "Copies DLL and configures CustomPluginVariables.JSON & Settings.JSON automatically",
        )
    )

    return rows


# ── Home Dashboard Summary Renderers ───────────────────────────────────────────


def render_home_install_summary(overview: dict[str, Any]) -> str:
    """Renders formatted Rich markup for the Home Installation summary card."""
    src = overview.get("source_dll", {})
    dll_exists = src.get("exists", False)
    dll_size = src.get("size_bytes", 0)
    dll_mtime = src.get("mtime_str", "-")
    dll_path = src.get("path", "")

    lines: list[str] = []
    if dll_exists:
        lines.append(f"• [bold white]DLL Binary :[/] [bold green]✓ Compiled[/] [dim]({dll_size:,} B)[/dim]")
        lines.append(f"• [bold white]Last Build :[/] [dim]{dll_mtime}[/dim]")
        if dll_path:
            lines.append(f"• [bold white]Source :[/] [cyan]{Path(dll_path).name}[/]")
    else:
        lines.append("• [bold white]DLL Binary :[/] [bold red]✗ Not compiled[/] [dim]('make cross')[/dim]")

    lines.append("[bold #58a6ff]Detected Simulators :[/]")
    games = overview.get("games", [])
    if not games:
        lines.append("  [dim]• None in default Steam library[/dim]")
    else:
        for g in games:
            g_name = g.get("name", "Game")
            g_inst = g.get("dll_installed", False)
            g_ext = g.get("external_plugins_enabled", False)
            inst_tag = f"[bold green]✓ Installed[/]" if g_inst else "[bold red]✗ Missing[/]"
            ext_tag = "[bold green]✓ Active[/]" if g_ext else "[yellow]⚠️ Inactive[/]"
            lines.append(f"  • [white]{g_name}[/] : {inst_tag} | {ext_tag}")

    return "\n".join(lines)


def render_home_config_summary(overview: dict[str, Any]) -> str:
    """Renders formatted Rich markup for the Home Configuration summary card."""
    vars_dict = overview.get("active_variables", {})
    target_ip = vars_dict.get("TargetIP", "127.0.0.1")
    target_port = vars_dict.get("TargetPort", "5000")
    inbound_ctrl = vars_dict.get("InboundControl", "Enabled")
    inbound_port = vars_dict.get("InboundPort", "5001")
    telem_rate = vars_dict.get("TelemetryRate", "unlimited")
    scoring_rate = vars_dict.get("FullScoringRate", "5Hz")
    rules_rate = vars_dict.get("TrackRulesRate", "3Hz")
    pit_rate = vars_dict.get("PitMenuRate", "100Hz")
    weather_rate = vars_dict.get("WeatherRate", "1Hz")
    ffb_rate = vars_dict.get("ForceFeedbackRate", "unlimited (400Hz)")

    lines = [
        f"• [bold white]UDP Destination :[/] [bold cyan]{target_ip}:{target_port}[/]",
        f"• [bold white]Inbound Control :[/] [bold green]{inbound_ctrl}[/] [dim](Port {inbound_port})[/dim]",
        f"• [bold white]Telemetry Rate  :[/] [bold #58a6ff]{telem_rate}[/]",
        f"• [bold white]Scoring / Rules :[/] [cyan]{scoring_rate}[/] / [cyan]{rules_rate}[/]",
        f"• [bold white]Pit / Weather   :[/] [cyan]{pit_rate}[/] / [cyan]{weather_rate}[/]",
        f"• [bold white]Force Feedback  :[/] [bold #bc8cff]{ffb_rate}[/]",
    ]
    return "\n".join(lines)


def render_home_network_summary(engine: TelemetryEngine, elapsed: float) -> str:
    """Renders formatted Rich markup for the Home Connectivity summary card."""
    total_kb_s = sum(s.bandwidth_kb_s for s in engine.stats.values())
    total_freq = sum(s.current_freq for s in engine.stats.values())

    if engine.total_packets > 0 and total_freq > 0.1:
        status_tag = "[bold green]🟢 Streaming (Game Active)[/]"
    elif engine.total_packets > 0:
        status_tag = "[bold yellow]🟡 Paused (No new packets)[/]"
    else:
        status_tag = "[bold yellow]🟡 Listening (Waiting for game)[/]"

    min_sec = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}s"

    lines = [
        f"• [bold white]Telemetry UDP Socket :[/] [bold cyan]{engine.host}:{engine.port}[/]",
        f"• [bold white]Connection Status    :[/] {status_tag}",
        f"• [bold white]Total Packets        :[/] [bold yellow]{engine.total_packets:,}[/] pkts",
        f"• [bold white]Current Bandwidth    :[/] [bold magenta]{total_kb_s:5.1f} KB/s[/] [dim]({total_freq:5.1f} Hz)[/dim]",
        f"• [bold white]Session Duration     :[/] [bold green]{min_sec}[/]",
        f"• [bold white]Inbound Commands     :[/] [cyan]{engine.inbound_target_host}:{engine.inbound_target_port}[/]",
    ]
    return "\n".join(lines)


# ── Textual TUI Application ───────────────────────────────────────────────────


class IsiMotorBenchmarkApp(App):
    """Raw UDP Telemetry Explorer & Benchmark for isiMotor."""

    CSS = """
    Screen {
        background: #0d1117;
        color: #c9d1d9;
    }

    #top-nav-bar {
        layout: horizontal;
        height: 3;
        background: #161b22;
        border-bottom: solid #30363d;
        align: left middle;
    }

    #main-nav-tabs {
        width: 1fr;
        height: 100%;
        background: transparent;
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

    #main-content-switcher {
        height: 1fr;
        margin: 0 1;
    }

    /* ── 1. Home View Styles ────────────────────────────────────────── */
    #view-home {
        height: 100%;
        layout: vertical;
        padding: 0 0;
    }

    #home-hero-banner {
        height: 3;
        background: #161b22;
        border: round #58a6ff;
        margin: 1 0 0 0;
        content-align: center middle;
        text-align: center;
    }

    #home-cards-container {
        layout: horizontal;
        height: 1fr;
        margin: 1 0 0 0;
    }

    .home-card {
        width: 1fr;
        height: 100%;
        background: #161b22;
        border: round #30363d;
        padding: 1 1;
        margin: 0 1;
        layout: vertical;
    }

    .home-card-header {
        text-align: center;
        text-style: bold;
        padding-bottom: 0;
        border-bottom: solid #30363d;
        margin-bottom: 1;
        height: 2;
    }

    .home-card-content {
        height: 1fr;
    }

    .home-card-actions {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }

    .home-card-btn {
        width: 1fr;
        margin: 0 1;
        height: 3;
    }

    /* ── 2. Install / Config View Styles ────────────────────────────── */
    #view-install {
        height: 100%;
        layout: vertical;
    }

    #install-controls {
        layout: horizontal;
        height: 3;
        margin: 1 0 0 0;
        background: #161b22;
        border-top: solid #30363d;
        border-bottom: solid #30363d;
        align: left middle;
    }

    #install-search-box {
        width: 1fr;
        height: 100%;
        margin: 0 1;
        background: #0d1117;
        border: none;
        color: #c9d1d9;
    }

    #table-container-install {
        height: 1fr;
        margin: 1 0 0 0;
        background: #161b22;
        border: round #58a6ff;
    }

    /* ── 3. Explorer View Styles ────────────────────────────────────── */
    #view-explorer {
        height: 100%;
        layout: vertical;
    }

    #explorer-controls {
        layout: horizontal;
        height: 3;
        margin: 1 0 0 0;
        background: #161b22;
        border-top: solid #30363d;
        border-bottom: solid #30363d;
        align: left middle;
    }

    #packet-tabs {
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

    #table-container-explorer {
        height: 1fr;
        margin: 1 0 0 0;
        background: #161b22;
        border: round #58a6ff;
    }

    /* ── 4. Commands View Styles ────────────────────────────────────── */
    #view-commands {
        height: 100%;
        layout: vertical;
    }

    #commands-status-bar {
        height: 3;
        margin: 1 0 0 0;
        background: #161b22;
        border-top: solid #30363d;
        border-bottom: solid #30363d;
        content-align: center middle;
        text-align: center;
    }

    #commands-panels-container {
        layout: horizontal;
        height: auto;
        margin: 1 0 0 0;
    }

    .cmd-panel {
        width: 1fr;
        background: #161b22;
        border: round #30363d;
        padding: 1;
        margin: 0 1;
        layout: vertical;
    }

    .cmd-panel-title {
        text-align: center;
        text-style: bold;
        color: #e3b341;
        border-bottom: solid #30363d;
        padding-bottom: 1;
        margin-bottom: 1;
    }

    .cmd-btn {
        width: 100%;
        margin-bottom: 1;
        height: 3;
    }

    .cmd-grid {
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
    }

    #input-cmd-name {
        margin-bottom: 1;
        height: 3;
    }

    #input-cmd-val {
        margin-bottom: 1;
        height: 3;
    }

    #table-container-commands {
        height: 1fr;
        margin: 1 0 0 0;
        background: #161b22;
        border: round #58a6ff;
    }

    /* Common Actions & Tables */
    .actions-box {
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
        Binding("h", "select_nav_home", "Home", show=True),
        Binding("p", "select_nav_install", "Install/Config", show=True),
        Binding("e", "select_nav_explorer", "Explorer", show=True),
        Binding("i", "select_nav_commands", "Commands", show=True),
        Binding("c", "copy_json", "Copy JSON", show=True),
        Binding("t", "copy_table", "Copy Table", show=True),
        Binding("r", "reset_stats", "Reset Stats", show=True),
        Binding("k", "copy_dll_action", "Copy DLL", show=False),
        Binding("slash", "focus_search", "Search", show=True),
        Binding("1", "select_tab_telem", "Telem", show=False),
        Binding("2", "select_tab_scoring", "Scoring", show=False),
        Binding("3", "select_tab_rules", "Rules", show=False),
        Binding("4", "select_tab_pit", "Pit", show=False),
        Binding("5", "select_tab_weather", "Weather", show=False),
        Binding("6", "select_tab_ffb", "FFB", show=False),
        Binding("7", "select_tab_graphics", "Graphics", show=False),
        Binding("8", "select_tab_physics", "Physics", show=False),
        Binding("9", "select_tab_event", "Event", show=False),
        Binding("0", "select_tab_stats", "Stats", show=False),
        Binding("u", "inbound_pit_up", "Pit Up", show=False),
        Binding("d", "inbound_pit_down", "Pit Down", show=False),
        Binding("l", "inbound_pit_prev", "Pit Prev", show=False),
        Binding("right", "inbound_pit_next", "Pit Next", show=False),
        Binding("j", "inbound_pit_select", "Pit Select", show=False),
        Binding("w", "inbound_rain_toggle", "Rain Toggle", show=False),
    ]

    active_nav = reactive(NAV_HOME)
    active_tab = reactive(TAB_TELEM)
    search_query_explorer = reactive("")
    search_query_install = reactive("")

    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        super().__init__()
        self.host = host
        self.port = port

        self.engine = TelemetryEngine(host=host, port=port)
        self.config_overview: dict[str, Any] = {}
        self.refresh_config_overview()

        # Top Navigation Tabs
        self.main_tabs = Tabs(
            Tab("🏠 Home", id=NAV_HOME),
            Tab("📦 Installer & Config", id=NAV_INSTALL),
            Tab("🔍 Packet Explorer", id=NAV_EXPLORER),
            Tab("🎮 Inbound Controls", id=NAV_COMMANDS),
            active=NAV_HOME,
            id="main-nav-tabs",
        )

        # Global Metric widgets
        self.lbl_elapsed = Static("⏱️ Session: [bold green]00:00s[/]", classes="metric-box")
        self.lbl_packets = Static("📦 Packets: [bold yellow]0[/]", classes="metric-box")
        self.lbl_channel_freq = Static("📶 Stream: [bold yellow]0.0 Hz[/]", classes="metric-box")
        self.lbl_rate = Static("⚡ Total: [bold magenta]0.0 KB/s[/]", classes="metric-box")
        self.lbl_visible_rows = Static("🔍 Fields: [bold cyan]0 / 0[/]", classes="metric-box")

        # Home View widgets
        self.lbl_home_install = Static(render_home_install_summary(self.config_overview), classes="home-card-content")
        self.lbl_home_config = Static(render_home_config_summary(self.config_overview), classes="home-card-content")
        self.lbl_home_network = Static(render_home_network_summary(self.engine, 0.0), classes="home-card-content")

        # Install View widgets
        self.search_install = Input(placeholder="🔍 Filter configuration parameters...", id="install-search-box")
        self.table_install: DataTable[Any] = DataTable(cursor_type="row")
        self._current_install_keys: list[str] = []

        # Explorer View widgets
        self.packet_tabs = Tabs(
            Tab("🏎️ TelemInfo (1888 B)", id=TAB_TELEM),
            Tab("🏁 Grid Scoring", id=TAB_SCORING),
            Tab("🚩 Track Rules & SC", id=TAB_RULES),
            Tab("⛽ Pit Menu", id=TAB_PIT),
            Tab("🌦️ Weather", id=TAB_WEATHER),
            Tab("⚡ FFB (400Hz)", id=TAB_FFB),
            Tab("🎥 Graphics", id=TAB_GRAPHICS),
            Tab("🔧 Physics & Aids", id=TAB_PHYSICS),
            Tab("🔔 Events (6 B)", id=TAB_EVENT),
            Tab("📊 Stream Rates", id=TAB_STATS),
            active=TAB_TELEM,
            id="packet-tabs",
        )
        self.search_explorer = Input(
            placeholder="🔍 Filter fields by name or description... (Press '/' to focus)", id="search-box"
        )
        self.table_explorer: DataTable[Any] = DataTable(cursor_type="row")
        self._current_explorer_keys: list[str] = []

        # Commands View widgets
        self.lbl_commands_status = Static(
            f"🎮 Inbound Target: [bold cyan]{self.engine.inbound_target_host}:{self.engine.inbound_target_port}[/] | "
            f"Last Command: [bold #58a6ff]{self.engine.last_inbound_cmd_sent}[/] | Pulse: [bold yellow]50 ms[/]",
            id="commands-status-bar",
        )
        self.input_cmd_name = Input(placeholder="Name (e.g. PitMenuSelect, BrakeBiasForward)", id="input-cmd-name")
        self.input_cmd_val = Input(placeholder="Value (default: 1.0)", id="input-cmd-val")
        self.table_commands: DataTable[Any] = DataTable(cursor_type="row")
        self._current_commands_keys: list[str] = []

        # Content Switcher reference
        self.switcher = ContentSwitcher(initial=VIEW_HOME, id="main-content-switcher")

    def refresh_config_overview(self) -> None:
        """Refreshes the detected game installations and JSON configuration overview."""
        try:
            self.config_overview = get_configuration_overview(project_root=project_root)
        except Exception as e:
            self.config_overview = {"error": str(e), "source_dll": {}, "games": [], "active_variables": {}}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="top-nav-bar"):
            yield self.main_tabs

        with Horizontal(id="metrics-bar"):
            yield Static("🏎️ [bold cyan]isiMotorRawUDP[/]", classes="metric-box")
            yield self.lbl_elapsed
            yield self.lbl_packets
            yield self.lbl_channel_freq
            yield self.lbl_rate
            yield self.lbl_visible_rows
            yield Static(f"🌐 [bold cyan]{self.host}:{self.port}[/]", classes="metric-box")

        with ContentSwitcher(initial=VIEW_HOME, id="main-content-switcher"):
            # ── 1. Home View ──────────────────────────────────────────
            with Vertical(id=VIEW_HOME):
                with Container(id="home-hero-banner"):
                    yield Static(
                        "🏎️  [bold #58a6ff]isiMotorRawUDP[/] [bold #3fb950]Manager[/] [dim]│ Low-Latency SIMP Telemetry & Bidirectional Inbound Bridge[/]",
                        id="home-hero-text",
                    )
                with Horizontal(id="home-cards-container"):
                    with Vertical(id="card-install", classes="home-card"):
                        yield Static("📦 [bold #58a6ff]1. Installation & DLL[/]", classes="home-card-header")
                        yield self.lbl_home_install
                        with Horizontal(classes="home-card-actions"):
                            yield Button(
                                "🚀 Copy DLL",
                                id="btn-home-copy-dll",
                                variant="success",
                                classes="home-card-btn",
                            )
                            yield Button(
                                "📂 Manage ➔",
                                id="btn-home-goto-install",
                                variant="primary",
                                classes="home-card-btn",
                            )

                    with Vertical(id="card-config", classes="home-card"):
                        yield Static("⚙️ [bold #e3b341]2. Active Config[/]", classes="home-card-header")
                        yield self.lbl_home_config
                        with Horizontal(classes="home-card-actions"):
                            yield Button(
                                "⚙️ View Config Details ➔",
                                id="btn-home-goto-config",
                                variant="primary",
                                classes="home-card-btn",
                            )

                    with Vertical(id="card-network", classes="home-card"):
                        yield Static("🌐 [bold #3fb950]3. UDP Network & Live[/]", classes="home-card-header")
                        yield self.lbl_home_network
                        with Horizontal(classes="home-card-actions"):
                            yield Button(
                                "🔍 Explorer ➔",
                                id="btn-home-goto-explorer",
                                variant="primary",
                                classes="home-card-btn",
                            )
                            yield Button(
                                "🎮 Controls ➔",
                                id="btn-home-goto-commands",
                                variant="default",
                                classes="home-card-btn",
                            )

            # ── 2. Install / Config View ──────────────────────────────
            with Vertical(id=VIEW_INSTALL):
                with Horizontal(id="install-controls"):
                    yield self.search_install
                    with Horizontal(classes="actions-box"):
                        yield Button("📦 Copy DLL", id="btn-install-copy-dll", variant="success", classes="btn-action")
                        yield Button("📋 Copy JSON", id="btn-install-copy-json", variant="primary", classes="btn-action")
                        yield Button("📑 Copy Table", id="btn-install-copy-table", variant="default", classes="btn-action")
                        yield Button("🔄 Refresh", id="btn-install-refresh", variant="default", classes="btn-action")
                with Container(id="table-container-install"):
                    yield self.table_install

            # ── 3. Packet Explorer View ───────────────────────────────
            with Vertical(id=VIEW_EXPLORER):
                with Horizontal(id="explorer-controls"):
                    yield self.packet_tabs
                    yield self.search_explorer
                    with Horizontal(classes="actions-box"):
                        yield Button("📋 Copy JSON", id="btn-explorer-copy-json", variant="primary", classes="btn-action")
                        yield Button("📑 Copy Table", id="btn-explorer-copy-table", variant="default", classes="btn-action")
                        yield Button("🔄 Reset Stats", id="btn-explorer-reset-stats", variant="default", classes="btn-action")
                with Container(id="table-container-explorer"):
                    yield self.table_explorer

            # ── 4. Commands View ──────────────────────────────────────
            with Vertical(id=VIEW_COMMANDS):
                yield self.lbl_commands_status
                with Horizontal(id="commands-panels-container"):
                    with Vertical(classes="cmd-panel"):
                        yield Static("⛽ [bold #e3b341]Pit Menu (Type 100)[/]", classes="cmd-panel-title")
                        with Grid(classes="cmd-grid"):
                            yield Button("⬆️ Up", id="btn-cmd-pit-up", classes="cmd-btn")
                            yield Button("⬇️ Down", id="btn-cmd-pit-down", classes="cmd-btn")
                            yield Button("⬅️ Prev", id="btn-cmd-pit-prev", classes="cmd-btn")
                            yield Button("➡️ Next", id="btn-cmd-pit-next", classes="cmd-btn")
                        yield Button("✅ Select / Enter", id="btn-cmd-pit-select", variant="success", classes="cmd-btn")

                    with Vertical(classes="cmd-panel"):
                        yield Static("🌦️ [bold #58a6ff]Weather Override (Type 101)[/]", classes="cmd-panel-title")
                        with Grid(classes="cmd-grid"):
                            yield Button("☀️ Clear (0%)", id="btn-cmd-weather-sun", classes="cmd-btn")
                            yield Button("⛅ Drizzle (25%)", id="btn-cmd-weather-drizzle", classes="cmd-btn")
                            yield Button("🌧️ Rain (60%)", id="btn-cmd-weather-rain", classes="cmd-btn")
                            yield Button("⛈️ Storm (95%)", id="btn-cmd-weather-storm", classes="cmd-btn")

                    with Vertical(classes="cmd-panel"):
                        yield Static("🏎️ [bold #3fb950]Vehicle Aids & Controls[/]", classes="cmd-panel-title")
                        with Grid(classes="cmd-grid"):
                            yield Button("🔑 Ignition", id="btn-cmd-ignition", classes="cmd-btn")
                            yield Button("🌧️ Wipers", id="btn-cmd-wipers", classes="cmd-btn")
                            yield Button("🏎️ TC +", id="btn-cmd-tc-up", classes="cmd-btn")
                            yield Button("🏎️ TC -", id="btn-cmd-tc-down", classes="cmd-btn")
                            yield Button("🛑 ABS +", id="btn-cmd-abs-up", classes="cmd-btn")
                            yield Button("🛑 ABS -", id="btn-cmd-abs-down", classes="cmd-btn")

                    with Vertical(classes="cmd-panel"):
                        yield Static("📤 [bold #bc8cff]Custom Command Sender[/]", classes="cmd-panel-title")
                        yield self.input_cmd_name
                        yield self.input_cmd_val
                        yield Button("📤 Send Command", id="btn-cmd-send-custom", variant="primary", classes="cmd-btn")

                with Container(id="table-container-commands"):
                    yield self.table_commands

        yield Footer()

    def on_mount(self) -> None:
        self.title = "isiMotorRawUDP Manager"
        self.sub_title = "Le Mans Ultimate & rFactor 2 Telemetry Hub"

        # Initialize DataTable columns
        for dt in [self.table_explorer, self.table_install, self.table_commands]:
            dt.add_column("Field / Key", key="col_key", width=34)
            dt.add_column("Current Value", key="col_val", width=32)
            dt.add_column("Description & Units", key="col_desc")

        # Start UDP receiver engine
        self.engine.start()

        # Populate tables and home cards
        self._update_home_cards()
        self._rebuild_explorer_rows()
        self._rebuild_install_rows()
        self._rebuild_commands_rows()

        # High-frequency UI tick (30 FPS)
        self.timer = self.set_interval(0.033, self._update_ui)

    # ── Tab & Navigation Handlers ──────────────────────────────────────────────

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        switcher = self.query_one(ContentSwitcher)
        if event.tabs.id == "main-nav-tabs":
            if event.tab and event.tab.id:
                self.active_nav = event.tab.id
                if self.active_nav == NAV_HOME:
                    switcher.current = VIEW_HOME
                    self.refresh_config_overview()
                    self._update_home_cards()
                elif self.active_nav == NAV_INSTALL:
                    switcher.current = VIEW_INSTALL
                    self.refresh_config_overview()
                    self._rebuild_install_rows()
                elif self.active_nav == NAV_EXPLORER:
                    switcher.current = VIEW_EXPLORER
                    self._rebuild_explorer_rows()
                elif self.active_nav == NAV_COMMANDS:
                    switcher.current = VIEW_COMMANDS
                    self._rebuild_commands_rows()
        elif event.tabs.id == "packet-tabs":
            if event.tab and event.tab.id:
                self.active_tab = event.tab.id
                self._rebuild_explorer_rows()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-box":
            self.search_query_explorer = event.value.strip().lower()
            self._rebuild_explorer_rows()
        elif event.input.id == "install-search-box":
            self.search_query_install = event.value.strip().lower()
            self._rebuild_install_rows()

    # ── Keyboard Action Handlers ───────────────────────────────────────────────

    def action_select_nav_home(self) -> None:
        self.main_tabs.active = NAV_HOME

    def action_select_nav_install(self) -> None:
        self.main_tabs.active = NAV_INSTALL

    def action_select_nav_explorer(self) -> None:
        self.main_tabs.active = NAV_EXPLORER

    def action_select_nav_commands(self) -> None:
        self.main_tabs.active = NAV_COMMANDS

    def action_focus_search(self) -> None:
        if self.active_nav == NAV_EXPLORER:
            self.search_explorer.focus()
        elif self.active_nav == NAV_INSTALL:
            self.search_install.focus()
        elif self.active_nav == NAV_COMMANDS:
            self.input_cmd_name.focus()

    def action_select_tab_telem(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_TELEM

    def action_select_tab_scoring(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_SCORING

    def action_select_tab_rules(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_RULES

    def action_select_tab_pit(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_PIT

    def action_select_tab_weather(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_WEATHER

    def action_select_tab_ffb(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_FFB

    def action_select_tab_graphics(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_GRAPHICS

    def action_select_tab_physics(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_PHYSICS

    def action_select_tab_event(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_EVENT

    def action_select_tab_stats(self) -> None:
        self.main_tabs.active = NAV_EXPLORER
        self.packet_tabs.active = TAB_STATS

    def action_copy_dll_action(self) -> None:
        self.action_copy_dll()

    def action_copy_dll(self) -> None:
        """Copies compiled DLL to detected games and configures JSON settings."""
        success, msg, _paths = copy_and_install_dll(project_root=project_root)
        self.refresh_config_overview()
        self._update_home_cards()
        self._rebuild_install_rows()
        if success:
            self.notify(msg, title="📦 DLL Copied Successfully!", severity="information")
        else:
            self.notify(msg, title="❌ DLL Installation Error", severity="error")

    def action_inbound_pit_up(self) -> None:
        self.engine.send_hw_control("PitMenuUp", 1.0, 50)
        self.notify("Sent command: PitMenuUp", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_pit_down(self) -> None:
        self.engine.send_hw_control("PitMenuDown", 1.0, 50)
        self.notify("Sent command: PitMenuDown", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_pit_prev(self) -> None:
        self.engine.send_hw_control("PitMenuPrev", 1.0, 50)
        self.notify("Sent command: PitMenuPrev", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_pit_next(self) -> None:
        self.engine.send_hw_control("PitMenuNext", 1.0, 50)
        self.notify("Sent command: PitMenuNext", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_pit_select(self) -> None:
        self.engine.send_hw_control("PitMenuSelect", 1.0, 50)
        self.notify("Sent command: PitMenuSelect", title="Inbound Control")
        self._rebuild_commands_rows()

    def action_inbound_rain_toggle(self) -> None:
        current_rain = self.engine.latest_weather.origin_raining if self.engine.latest_weather else 0.0
        new_rain = 0.0 if current_rain > 0.3 else 0.85
        self.engine.send_weather_override(ambient_temp=25.0, raining=new_rain)
        self.notify(f"Injected Weather: Rain={new_rain * 100:.0f}%", title="Weather Override")
        self._rebuild_commands_rows()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ["btn-home-goto-install", "btn-hub-install", "btn-home-goto-config"]:
            self.main_tabs.active = NAV_INSTALL
        elif bid in ["btn-home-goto-explorer", "btn-hub-explorer"]:
            self.main_tabs.active = NAV_EXPLORER
        elif bid in ["btn-home-goto-commands", "btn-hub-commands"]:
            self.main_tabs.active = NAV_COMMANDS
        elif bid in ["btn-home-copy-dll", "btn-install-copy-dll"]:
            self.action_copy_dll()
        elif bid == "btn-install-refresh":
            self.refresh_config_overview()
            self._update_home_cards()
            self._rebuild_install_rows()
            self.notify("Configuration overview refreshed.", title="🔄 Refresh")
        elif bid in ["btn-explorer-copy-json", "btn-install-copy-json"]:
            self.action_copy_json()
        elif bid in ["btn-explorer-copy-table", "btn-install-copy-table"]:
            self.action_copy_table()
        elif bid == "btn-explorer-reset-stats":
            self.action_reset_stats()
        elif bid == "btn-cmd-pit-up":
            self.action_inbound_pit_up()
        elif bid == "btn-cmd-pit-down":
            self.action_inbound_pit_down()
        elif bid == "btn-cmd-pit-prev":
            self.action_inbound_pit_prev()
        elif bid == "btn-cmd-pit-next":
            self.action_inbound_pit_next()
        elif bid == "btn-cmd-pit-select":
            self.action_inbound_pit_select()
        elif bid == "btn-cmd-weather-sun":
            self.engine.send_weather_override(ambient_temp=25.0, raining=0.0)
            self.notify("Injected Weather: Clear (0% rain)", title="Weather Override")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-weather-drizzle":
            self.engine.send_weather_override(ambient_temp=22.0, raining=0.25)
            self.notify("Injected Weather: Drizzle (25% rain)", title="Weather Override")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-weather-rain":
            self.engine.send_weather_override(ambient_temp=19.0, raining=0.60)
            self.notify("Injected Weather: Rain (60% rain)", title="Weather Override")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-weather-storm":
            self.engine.send_weather_override(ambient_temp=16.0, raining=0.95)
            self.notify("Injected Weather: Storm (95% rain)", title="Weather Override")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-ignition":
            self.engine.send_hw_control("Ignition", 1.0, 50)
            self.notify("Sent command: Ignition", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-wipers":
            self.engine.send_hw_control("Wipers", 1.0, 50)
            self.notify("Sent command: Wipers", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-tc-up":
            self.engine.send_hw_control("TCIncrease", 1.0, 50)
            self.notify("Sent command: TCIncrease", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-tc-down":
            self.engine.send_hw_control("TCDecrease", 1.0, 50)
            self.notify("Sent command: TCDecrease", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-abs-up":
            self.engine.send_hw_control("ABSIncrease", 1.0, 50)
            self.notify("Sent command: ABSIncrease", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-abs-down":
            self.engine.send_hw_control("ABSDecrease", 1.0, 50)
            self.notify("Sent command: ABSDecrease", title="HW Control")
            self._rebuild_commands_rows()
        elif bid == "btn-cmd-send-custom":
            name = self.input_cmd_name.value.strip()
            val_str = self.input_cmd_val.value.strip()
            if not name:
                self.notify("Please enter a control identifier", title="Error", severity="error")
            else:
                try:
                    val = float(val_str) if val_str else 1.0
                except ValueError:
                    val = 1.0
                self.engine.send_hw_control(name, val, 50)
                self.notify(f"Sent command: {name}={val}", title="HW Control")
                self._rebuild_commands_rows()

    # ── Data Extraction Helpers ────────────────────────────────────────────────

    def _get_active_explorer_rows(self) -> list[tuple[str, Any, str, str]]:
        """Returns the raw rows for the currently selected stream in the Explorer."""
        if self.active_tab == TAB_TELEM:
            return extract_telemetry_rows(self.engine.latest_telemetry, self.engine.stats[PKT_RAW_TELEMETRY])
        elif self.active_tab == TAB_SCORING:
            st = (
                self.engine.stats.get(PKT_FULL_SCORING)
                if self.engine.latest_full_scoring
                else self.engine.stats[PKT_COMPACT_SCORING]
            )
            return extract_scoring_rows(self.engine.latest_scoring, self.engine.latest_full_scoring, st)
        elif self.active_tab == TAB_RULES:
            return extract_track_rules_rows(self.engine.latest_track_rules, self.engine.stats[PKT_TRACK_RULES])
        elif self.active_tab == TAB_PIT:
            return extract_pit_menu_rows(self.engine.latest_pit_menu, self.engine.stats[PKT_PIT_MENU])
        elif self.active_tab == TAB_WEATHER:
            return extract_weather_rows(self.engine.latest_weather, self.engine.stats[PKT_WEATHER])
        elif self.active_tab == TAB_FFB:
            return extract_ffb_rows(self.engine.latest_force_feedback, self.engine.stats[PKT_FORCE_FEEDBACK])
        elif self.active_tab == TAB_GRAPHICS:
            return extract_graphics_rows(self.engine.latest_graphics, self.engine.stats[PKT_GRAPHICS])
        elif self.active_tab == TAB_PHYSICS:
            return extract_physics_rows(self.engine.latest_extended_state, self.engine.stats[PKT_EXTENDED_STATE])
        elif self.active_tab == TAB_EVENT:
            return extract_event_rows(
                self.engine.latest_event, self.engine.stats[PKT_SYSTEM_EVENT], self.engine.latest_event_time
            )
        elif self.active_tab == TAB_STATS:
            return extract_stats_rows(self.engine)
        return []

    def _get_active_model_dict(self) -> dict[str, Any]:
        """Returns clean dictionary for JSON export based on active navigation mode."""
        if self.active_nav == NAV_INSTALL:
            return self.config_overview
        elif self.active_nav == NAV_COMMANDS:
            rows = extract_inbound_rows(self.engine)
            return {k: raw for k, raw, _, _ in rows}
        elif self.active_nav == NAV_HOME:
            return {
                "config_overview": self.config_overview,
                "engine_stats": {k: s.count for k, s in self.engine.stats.items()},
                "total_packets": self.engine.total_packets,
            }

        # Explorer view export
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
            return {"status": "No Weather packet received yet"}
        elif self.active_tab == TAB_FFB:
            st = self.engine.stats[PKT_FORCE_FEEDBACK]
            if self.engine.latest_force_feedback:
                d = model_to_clean_dict(self.engine.latest_force_feedback)
                d["percentage"] = self.engine.latest_force_feedback.percentage
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "jitter_ms": round(st.jitter_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No ForceFeedback packet received yet"}
        elif self.active_tab == TAB_GRAPHICS:
            st = self.engine.stats[PKT_GRAPHICS]
            if self.engine.latest_graphics:
                d = model_to_clean_dict(self.engine.latest_graphics)
                d["camera_type_str"] = self.engine.latest_graphics.camera_type_str
                d["is_cockpit_view"] = self.engine.latest_graphics.is_cockpit_view
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No Graphics packet received yet"}
        elif self.active_tab == TAB_PHYSICS:
            st = self.engine.stats[PKT_EXTENDED_STATE]
            if self.engine.latest_extended_state:
                d = model_to_clean_dict(self.engine.latest_extended_state)
                d["pit_speed_limit_kmh"] = self.engine.latest_extended_state.current_pit_speed_limit_kmh
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
                return d
            return {"status": "No ExtendedState packet received yet"}
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
        """Copies JSON representation of currently active view/packet to clipboard."""
        data_dict = self._get_active_model_dict()
        json_text = json.dumps(data_dict, indent=2)
        try:
            self.copy_to_clipboard(json_text)
            self.notify(f"JSON copied to clipboard ({len(data_dict)} items)!", title="📋 JSON Copied")
        except Exception as e:
            self.notify(f"Could not copy to clipboard: {e}", title="Error", severity="error")

    def action_copy_table(self) -> None:
        """Copies formatted table (Key, Value, Description) to clipboard."""
        if self.active_nav == NAV_INSTALL:
            rows = extract_config_rows(self.config_overview)
        elif self.active_nav == NAV_COMMANDS:
            rows = extract_inbound_rows(self.engine)
        else:
            rows = self._get_active_explorer_rows()

        lines = ["Key\tValue\tDescription"]
        for key, _raw_val, fmt_val, desc in rows:
            clean_fmt = (
                fmt_val.replace("[bold]", "")
                .replace("[/bold]", "")
                .replace("[bold #58a6ff]", "")
                .replace("[bold #3fb950]", "")
                .replace("[bold #f85149]", "")
                .replace("[bold #e3b341]", "")
                .replace("[bold #f1e05a]", "")
                .replace("[bold #bc8cff]", "")
                .replace("[#a5d6ff]", "")
                .replace("[dim]", "")
                .replace("[/dim]", "")
                .replace("[/]", "")
            )
            lines.append(f"{key}\t{clean_fmt}\t{desc}")

        table_text = "\n".join(lines)
        try:
            self.copy_to_clipboard(table_text)
            self.notify(f"Table copied to clipboard ({len(rows)} rows)!", title="📑 Table Copied")
        except Exception as e:
            self.notify(f"Could not copy to clipboard: {e}", title="Error", severity="error")

    def action_reset_stats(self) -> None:
        self.engine.reset_stats()
        self._rebuild_explorer_rows()
        self.notify("Statistics & packet counters reset.", title="🔄 Reset Complete")

    # ── Table & UI Rendering Helpers ───────────────────────────────────────────

    def _update_home_cards(self) -> None:
        """Updates the 3 dashboard cards on the Home page."""
        elapsed = time.time() - self.engine.start_time
        self.lbl_home_install.update(render_home_install_summary(self.config_overview))
        self.lbl_home_config.update(render_home_config_summary(self.config_overview))
        self.lbl_home_network.update(render_home_network_summary(self.engine, elapsed))

    def _rebuild_explorer_rows(self) -> None:
        """Rebuilds the Explorer DataTable rows."""
        all_rows = self._get_active_explorer_rows()
        query = self.search_query_explorer.lower()

        if query:
            filtered_rows = [
                r for r in all_rows if query in r[0].lower() or query in r[3].lower() or query in str(r[1]).lower()
            ]
        else:
            filtered_rows = all_rows

        self.table_explorer.clear()
        self._current_explorer_keys = []

        for key, _raw_val, fmt_val, desc in filtered_rows:
            self.table_explorer.add_row(f"[bold #58a6ff]{key}[/]", fmt_val, desc, key=key)
            self._current_explorer_keys.append(key)

        self.lbl_visible_rows.update(f"🔍 Fields: [bold cyan]{len(filtered_rows)} / {len(all_rows)}[/]")

    def _rebuild_install_rows(self) -> None:
        """Rebuilds the Install / Config DataTable rows."""
        all_rows = extract_config_rows(self.config_overview)
        query = self.search_query_install.lower()

        if query:
            filtered_rows = [
                r for r in all_rows if query in r[0].lower() or query in r[3].lower() or query in str(r[1]).lower()
            ]
        else:
            filtered_rows = all_rows

        self.table_install.clear()
        self._current_install_keys = []

        for key, _raw_val, fmt_val, desc in filtered_rows:
            self.table_install.add_row(f"[bold #58a6ff]{key}[/]", fmt_val, desc, key=key)
            self._current_install_keys.append(key)

    def _rebuild_commands_rows(self) -> None:
        """Rebuilds the Commands / Inbound DataTable rows."""
        all_rows = extract_inbound_rows(self.engine)
        self.table_commands.clear()
        self._current_commands_keys = []

        for key, _raw_val, fmt_val, desc in all_rows:
            self.table_commands.add_row(f"[bold #58a6ff]{key}[/]", fmt_val, desc, key=key)
            self._current_commands_keys.append(key)

        self.lbl_commands_status.update(
            f"🎮 Inbound Target: [bold cyan]{self.engine.inbound_target_host}:{self.engine.inbound_target_port}[/] | "
            f"Last Command: [bold #58a6ff]{self.engine.last_inbound_cmd_sent}[/] | Pulse: [bold yellow]50 ms[/]"
        )

    def _update_ui(self) -> None:
        """Periodic UI update: polls UDP socket and refreshes active view cells."""
        if not self.is_running:
            return

        self.engine.poll()

        now = time.time()
        elapsed = now - self.engine.start_time
        current_kb_s = sum(s.bandwidth_kb_s for s in self.engine.stats.values())
        current_total_freq = sum(s.current_freq for s in self.engine.stats.values())

        # Update Top Global Metrics Bar
        self.lbl_elapsed.update(f"⏱️ Elapsed: [bold green]{int(elapsed // 60):02d}:{int(elapsed % 60):02d}s[/]")
        self.lbl_packets.update(f"📦 Packets: [bold yellow]{self.engine.total_packets:,}[/]")
        self.lbl_rate.update(f"⚡ Total: [bold magenta]{current_kb_s:5.1f} KB/s[/]")

        # Update Channel Real Reception Frequency
        if self.active_nav == NAV_HOME:
            self.lbl_channel_freq.update(f"📶 [bold cyan]All Streams:[/] [bold yellow]{current_total_freq:5.1f} Hz[/]")
            self._update_home_cards()
        elif self.active_nav == NAV_INSTALL:
            src = self.config_overview.get("source_dll", {})
            status = "Compiled" if src.get("exists") else "Not Compiled"
            self.lbl_channel_freq.update(
                f"⚙️ [bold cyan]Config JSON:[/] [bold {'green' if src.get('exists') else 'red'}]{status}[/]"
            )
            # In-place cell update for Install table
            rows = extract_config_rows(self.config_overview)
            row_map = {r[0]: r[2] for r in rows}
            for key in self._current_install_keys:
                if key in row_map:
                    try:
                        self.table_install.update_cell(key, "col_val", row_map[key])
                    except Exception:
                        pass
        elif self.active_nav == NAV_COMMANDS:
            self.lbl_channel_freq.update(
                f"📶 [bold cyan]Inbound:[/] [bold yellow]{self.engine.inbound_target_host}:{self.engine.inbound_target_port}[/]"
            )
            # In-place cell update for Commands table
            rows = extract_inbound_rows(self.engine)
            row_map = {r[0]: r[2] for r in rows}
            for key in self._current_commands_keys:
                if key in row_map:
                    try:
                        self.table_commands.update_cell(key, "col_val", row_map[key])
                    except Exception:
                        pass
        elif self.active_nav == NAV_EXPLORER:
            if self.active_tab == TAB_TELEM:
                st = self.engine.stats[PKT_RAW_TELEMETRY]
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]TelemInfo:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_SCORING:
                st = (
                    self.engine.stats[PKT_FULL_SCORING]
                    if self.engine.latest_full_scoring
                    else self.engine.stats[PKT_COMPACT_SCORING]
                )
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
            elif self.active_tab == TAB_FFB:
                st = self.engine.stats[PKT_FORCE_FEEDBACK]
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]FFB (400Hz):[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_GRAPHICS:
                st = self.engine.stats[PKT_GRAPHICS]
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]Graphics:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_PHYSICS:
                st = self.engine.stats[PKT_EXTENDED_STATE]
                self.lbl_channel_freq.update(
                    f"📶 [bold cyan]Physics & Aids:[/] [bold yellow]{st.current_freq:5.1f} Hz[/] [dim]({st.count:,} pkts)[/dim]"
                )
            elif self.active_tab == TAB_EVENT:
                st = self.engine.stats[PKT_SYSTEM_EVENT]
                self.lbl_channel_freq.update(f"📶 [bold cyan]Events:[/] [bold yellow]{st.count}[/] [dim]pkts[/dim]")
            elif self.active_tab == TAB_STATS:
                self.lbl_channel_freq.update(f"📶 [bold cyan]All Streams:[/] [bold yellow]{current_total_freq:5.1f} Hz[/]")

            # In-place table cell updates for smooth 30 FPS rendering
            rows = self._get_active_explorer_rows()
            row_map = {r[0]: r[2] for r in rows}

            for key in self._current_explorer_keys:
                if key in row_map:
                    try:
                        self.table_explorer.update_cell(key, "col_val", row_map[key])
                    except Exception:
                        pass

    def on_unmount(self) -> None:
        self.engine.stop()


def main():
    parser = argparse.ArgumentParser(description="isiMotor UDP Raw Telemetry Explorer & Benchmark (Textual)")
    parser.add_argument("--host", default="0.0.0.0", help="UDP listening host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="UDP listening port (default: 5000)")
    args = parser.parse_args()

    app = IsiMotorBenchmarkApp(host=args.host, port=args.port)
    app.run()


if __name__ == "__main__":
    main()

