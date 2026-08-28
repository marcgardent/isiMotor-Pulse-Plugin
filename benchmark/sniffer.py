#!/usr/bin/env python3
"""
isiMotor UDP Telemetry Packet Sniffer & Frequency Benchmark
Built with Textual for a modern, responsive Terminal User Interface.
"""

import sys
import time
import math
import struct
import socket
import select
import threading
import argparse
from pathlib import Path
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple

# Support loading parent package
client_pkg_path = Path(__file__).resolve().parent.parent / "isimotor-rawudp-client"
if client_pkg_path.exists():
    sys.path.insert(0, str(client_pkg_path))

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Header, Footer, Static, DataTable, Label, ProgressBar, Rule
    from textual.binding import Binding
except ImportError:
    print("\n[!] The 'textual' package is required to run the benchmark dashboard.")
    print("    Install dependencies in the benchmark environment:")
    print("      cd benchmark && uv venv && uv pip install -e ../isimotor-rawudp-client textual rich\n")
    sys.exit(1)


# ── Packet Stream Definitions ──────────────────────────────────────────────────
PKT_RAW_TELEMETRY   = "TelemInfoV01 (Raw Binary)"
PKT_COMPACT_SCORING = "CompactScoring (SIMP v2)"
PKT_SYSTEM_EVENT    = "SystemEvent (SIMP v3)"
PKT_FOREIGN         = "Foreign / Unknown"


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
    """Non-blocking UDP receiver & binary unpacker."""

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

        self.latest_telemetry: Dict[str, Any] = {}
        self.latest_scoring: Dict[str, Any] = {}
        self.latest_event: Dict[str, Any] = {}

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
            try:
                vx, vy, vz = struct.unpack_from("<ddd", data, 192)
                gear = struct.unpack_from("<i", data, 360)[0]
                rpm = struct.unpack_from("<d", data, 368)[0]
                max_rpm = struct.unpack_from("<d", data, 544)[0]
                thr = struct.unpack_from("<d", data, 400)[0]
                brk = struct.unpack_from("<d", data, 408)[0]
                str_val = struct.unpack_from("<d", data, 416)[0]
                f_df = struct.unpack_from("<d", data, 520)[0]
                r_df = struct.unpack_from("<d", data, 528)[0]
                fuel = struct.unpack_from("<d", data, 536)[0]

                # 4 Wheels
                wheels = []
                for i in range(4):
                    b = 864 + i * 260
                    defl = struct.unpack_from("<d", data, b + 0)[0] * 1000.0
                    brake_temp = struct.unpack_from("<d", data, b + 24)[0]
                    lpv = struct.unpack_from("<d", data, b + 56)[0] * 3.6
                    lgv = struct.unpack_from("<d", data, b + 72)[0] * 3.6
                    t_kelvin = struct.unpack_from("<ddd", data, b + 128)
                    t_celsius = t_kelvin[1] - 273.15
                    slip = (lpv - lgv) / max(abs(lgv), 1.0)
                    wheels.append({
                        "lpv": lpv,
                        "lgv": lgv,
                        "temp": t_celsius,
                        "brake_temp": brake_temp,
                        "defl_mm": defl,
                        "slip": slip
                    })

                speed_kmh = math.sqrt(vx*vx + vy*vy + vz*vz) * 3.6
                forward_kmh = (-vz) * 3.6

                self.latest_telemetry = {
                    "speed_kmh": speed_kmh,
                    "forward_kmh": forward_kmh,
                    "gear": "R" if gear == -1 else ("N" if gear == 0 else str(gear)),
                    "rpm": rpm,
                    "max_rpm": max_rpm if max_rpm > 100 else 8500.0,
                    "throttle": thr,
                    "brake": brk,
                    "steering": str_val,
                    "downforce": f_df + r_df,
                    "fuel": fuel,
                    "wheels": wheels,
                }
            except Exception:
                pass

        # 2. Compact Scoring (SIMP Type 2, 176 bytes)
        elif data.startswith(b"SIMP") and len(data) >= 5 and data[4] == 2:
            pkt_type = PKT_COMPACT_SCORING
            try:
                track = data[5:69].split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
                session = struct.unpack_from("<i", data, 72)[0]
                laps = struct.unpack_from("<h", data, 106)[0]
                sector = struct.unpack_from("<b", data, 108)[0]
                s1 = struct.unpack_from("<d", data, 112)[0]
                s2 = struct.unpack_from("<d", data, 120)[0]
                last_lap = struct.unpack_from("<d", data, 144)[0]
                best_lap = struct.unpack_from("<d", data, 168)[0]

                self.latest_scoring = {
                    "track": track,
                    "session": session,
                    "laps": laps,
                    "sector": sector,
                    "s1": s1,
                    "s2": s2,
                    "last_lap": last_lap,
                    "best_lap": best_lap,
                }
            except Exception:
                pass

        # 3. System Event (SIMP Type 3, 6 bytes)
        elif data.startswith(b"SIMP") and len(data) >= 5 and data[4] == 3:
            pkt_type = PKT_SYSTEM_EVENT
            ev_id = data[5]
            ev_names = {1: "EnterRealtime", 2: "ExitRealtime", 3: "StartSession", 4: "EndSession"}
            self.latest_event = {"id": ev_id, "name": ev_names.get(ev_id, f"ID {ev_id}"), "time": now}
        else:
            pkt_type = PKT_FOREIGN

        self.stats[pkt_type].record(size, now)

    def reset_stats(self):
        self.total_packets = 0
        self.total_bytes = 0
        self.start_time = time.time()
        for s in self.stats.values():
            s.reset()


def mock_transmitter_loop(port: int, stop_flag: threading.Event):
    """Generates realistic telemetry streams for simulation mode."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = ("127.0.0.1", port)

    buf_telemetry = bytearray(1904)
    buf_scoring = bytearray(176)
    buf_scoring[0:4] = b"SIMP"
    buf_scoring[4] = 2
    track = b"Circuit de Spa-Francorchamps\x00"
    buf_scoring[5:5+len(track)] = track
    struct.pack_into("<i", buf_scoring, 72, 11)
    struct.pack_into("<h", buf_scoring, 106, 5)
    struct.pack_into("<b", buf_scoring, 108, 2)
    struct.pack_into("<d", buf_scoring, 112, 38.420)
    struct.pack_into("<d", buf_scoring, 120, 94.850)
    struct.pack_into("<d", buf_scoring, 144, 138.452)
    struct.pack_into("<d", buf_scoring, 168, 137.910)

    t = 0.0
    while not stop_flag.is_set():
        t += 0.01
        spd = 60.0 + 30.0 * math.sin(t * 0.5)
        rpm = 5000.0 + 2500.0 * math.sin(t * 1.5)
        struct.pack_into("<ddd", buf_telemetry, 192, 0.0, 0.0, -spd)
        struct.pack_into("<i", buf_telemetry, 360, 4)
        struct.pack_into("<d", buf_telemetry, 368, rpm)
        struct.pack_into("<d", buf_telemetry, 544, 8500.0)
        struct.pack_into("<d", buf_telemetry, 400, 0.5 + 0.5 * math.sin(t * 2))
        struct.pack_into("<d", buf_telemetry, 408, max(0.0, -math.sin(t * 2)))
        struct.pack_into("<d", buf_telemetry, 416, 0.2 * math.sin(t * 0.8))
        struct.pack_into("<d", buf_telemetry, 520, 1200.0)
        struct.pack_into("<d", buf_telemetry, 528, 1800.0)
        struct.pack_into("<d", buf_telemetry, 536, 42.5)

        for i in range(4):
            base = 864 + i * 260
            struct.pack_into("<d", buf_telemetry, base + 0, 0.018 + 0.005 * math.sin(t * 3 + i))
            struct.pack_into("<d", buf_telemetry, base + 24, 380.0 + 20.0 * i)
            struct.pack_into("<d", buf_telemetry, base + 56, spd + 1.5 * math.sin(t * 5 + i))
            struct.pack_into("<d", buf_telemetry, base + 72, spd)
            struct.pack_into("<ddd", buf_telemetry, base + 128, 360.0, 365.0, 362.0)

        sock.sendto(buf_telemetry, dest)

        # Scoring @ 2 Hz
        if int(t * 100) % 50 == 0:
            sock.sendto(buf_scoring, dest)

        time.sleep(0.01)


# ── Textual TUI Application ───────────────────────────────────────────────────

class IsiMotorBenchmarkApp(App):
    """Modern Textual Terminal Dashboard for isiMotor UDP Telemetry."""

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

    #table-container {
        height: 8;
        margin: 1 1 0 1;
        background: #161b22;
        border: round #58a6ff;
    }

    DataTable {
        height: 100%;
        background: #161b22;
    }

    #lower-grid {
        layout: horizontal;
        height: 1fr;
        margin: 1 1 0 1;
    }

    #physics-panel {
        width: 1fr;
        height: 100%;
        margin-right: 1;
        background: #161b22;
        border: round #3fb950;
        padding: 1;
    }

    #wheels-panel {
        width: 1fr;
        height: 100%;
        background: #161b22;
        border: round #bc8cff;
        padding: 1;
    }

    .panel-title {
        text-style: bold;
        color: #58a6ff;
        margin-bottom: 1;
    }

    .gauge-label {
        color: #8b949e;
        width: 12;
    }

    .gauge-row {
        layout: horizontal;
        height: 1;
        margin-bottom: 1;
    }

    ProgressBar {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("m", "toggle_mock", "Toggle Mock Sim", show=True),
        Binding("r", "reset_stats", "Reset Stats", show=True),
    ]

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
        self.lbl_throughput = Static("⚡ Throughput: [bold magenta]0.0 KB/s[/]", classes="metric-box")
        self.table = DataTable(cursor_type="none")
        self.txt_physics_main = Static("Speed: -- km/h │ Gear: [bold yellow]N[/] │ RPM: -- │ Fuel: --L")
        self.bar_throttle = ProgressBar(total=100, show_eta=False)
        self.bar_brake = ProgressBar(total=100, show_eta=False)
        self.bar_steer = ProgressBar(total=100, show_eta=False)
        self.txt_wheels_front = Static("FL: --°C (Slip: --)   FR: --°C (Slip: --)")
        self.txt_wheels_rear = Static("RL: --°C (Slip: --)   RR: --°C (Slip: --)")
        self.txt_scoring = Static("Track: -- │ Lap: -- (Sector -) │ Last: --:--.--- │ Best: --:--.---")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="metrics-bar"):
            yield Static("🏁 [bold cyan]isiMotor-RawUDP[/]", classes="metric-box")
            yield self.lbl_elapsed
            yield self.lbl_packets
            yield self.lbl_throughput
            yield Static(f"🌐 Endpoint: [bold cyan]{self.host}:{self.port}[/]", classes="metric-box")

        with Container(id="table-container"):
            yield self.table

        with Horizontal(id="lower-grid"):
            with Vertical(id="physics-panel"):
                yield Label("🏎️  VEHICLE PHYSICS & DRIVER INPUTS", classes="panel-title")
                yield self.txt_physics_main
                yield Rule()
                with Horizontal(classes="gauge-row"):
                    yield Label("Throttle:", classes="gauge-label")
                    yield self.bar_throttle
                with Horizontal(classes="gauge-row"):
                    yield Label("Brake:", classes="gauge-label")
                    yield self.bar_brake
                with Horizontal(classes="gauge-row"):
                    yield Label("Steering:", classes="gauge-label")
                    yield self.bar_steer

            with Vertical(id="wheels-panel"):
                yield Label("🛞  4 WHEELS & TIMING INSPECTOR", classes="panel-title")
                yield self.txt_wheels_front
                yield self.txt_wheels_rear
                yield Rule()
                yield self.txt_scoring

        yield Footer()

    def on_mount(self) -> None:
        self.title = "isiMotor-RawUDP Telemetry Benchmark"
        self.sub_title = "Zero-Overhead Binary UDP Sniffer"

        # Initialize DataTable columns
        self.table.add_column("Stream / Packet Type", key="col_stream")
        self.table.add_column("Format", key="col_format")
        self.table.add_column("Packet Size", key="col_size")
        self.table.add_column("Packets", key="col_packets")
        self.table.add_column("Frequency (Hz)", key="col_freq")
        self.table.add_column("Avg Delay (ms)", key="col_delay")
        self.table.add_column("Jitter (ms)", key="col_jitter")
        self.table.add_column("Throughput", key="col_rate")

        for st_name in [PKT_RAW_TELEMETRY, PKT_COMPACT_SCORING, PKT_SYSTEM_EVENT]:
            st = self.engine.stats[st_name]
            self.table.add_row(
                st.name,
                st.format_type,
                st.expected_size,
                "0",
                "0.0 Hz",
                "-",
                "-",
                "0.0 KB/s",
                key=st_name
            )

        # Start UDP socket
        self.engine.start()

        # Start mock simulation if requested
        if self.mock_enabled:
            self._start_mock_sim()

        # 30 FPS update timer
        self.timer = self.set_interval(0.033, self._update_ui)

    def _start_mock_sim(self):
        self.mock_stop_event.clear()
        self.mock_thread = threading.Thread(
            target=mock_transmitter_loop,
            args=(self.port, self.mock_stop_event),
            daemon=True
        )
        self.mock_thread.start()

    def _stop_mock_sim(self):
        if self.mock_thread and self.mock_thread.is_alive():
            self.mock_stop_event.set()
            self.mock_thread = None

    def action_toggle_mock(self):
        self.mock_enabled = not self.mock_enabled
        if self.mock_enabled:
            self._start_mock_sim()
            self.notify("Mock Telemetry Transmitter Started (@ 100Hz)", title="Simulation Active")
        else:
            self._stop_mock_sim()
            self.notify("Mock Telemetry Transmitter Stopped", title="Simulation Inactive")

    def action_reset_stats(self):
        self.engine.reset_stats()
        for st_name in [PKT_RAW_TELEMETRY, PKT_COMPACT_SCORING, PKT_SYSTEM_EVENT]:
            self.table.update_cell(st_name, "col_packets", "0")
            self.table.update_cell(st_name, "col_freq", "0.0 Hz")
            self.table.update_cell(st_name, "col_delay", "-")
            self.table.update_cell(st_name, "col_jitter", "-")
            self.table.update_cell(st_name, "col_rate", "0.0 KB/s")
        self.notify("Statistics & packet counters reset.", title="Reset Complete")

    def _update_ui(self) -> None:
        if not self.is_mounted:
            return

        self.engine.poll()

        now = time.time()
        elapsed = now - self.engine.start_time
        total_mb = self.engine.total_bytes / (1024.0 * 1024.0)
        current_kb_s = sum(s.bandwidth_kb_s for s in self.engine.stats.values())

        # Update Top Bar
        self.lbl_elapsed.update(
            f"⏱️ Elapsed: [bold green]{int(elapsed // 60):02d}:{int(elapsed % 60):02d}s[/]"
        )
        self.lbl_packets.update(
            f"📦 Packets: [bold yellow]{self.engine.total_packets:,}[/]"
        )
        self.lbl_throughput.update(
            f"⚡ Rate: [bold magenta]{current_kb_s:5.1f} KB/s ({total_mb:4.1f} MB)[/]"
        )

        # Update DataTable
        for st_name in [PKT_RAW_TELEMETRY, PKT_COMPACT_SCORING, PKT_SYSTEM_EVENT]:
            st = self.engine.stats[st_name]
            if st.count > 0:
                self.table.update_cell(st_name, "col_packets", f"{st.count:,}")
                self.table.update_cell(st_name, "col_freq", f"[bold yellow]{st.current_freq:5.1f} Hz[/]")
                self.table.update_cell(st_name, "col_delay", f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-")
                self.table.update_cell(st_name, "col_jitter", f"±{st.jitter_ms:3.1f} ms" if st.intervals else "-")
                self.table.update_cell(st_name, "col_rate", f"{st.bandwidth_kb_s:5.1f} KB/s")

        # Update Vehicle Physics
        telem = self.engine.latest_telemetry
        if telem:
            spd = telem.get("speed_kmh", 0.0)
            gear = telem.get("gear", "N")
            rpm = telem.get("rpm", 0.0)
            max_rpm = telem.get("max_rpm", 8500.0)
            fuel = telem.get("fuel", 0.0)
            df = telem.get("downforce", 0.0)

            self.txt_physics_main.update(
                f"Speed: [bold white]{spd:5.1f}[/] km/h  │  Gear: [bold yellow on black] {gear} [/]  │  "
                f"RPM: [bold cyan]{rpm:5.0f}[/] / {max_rpm:.0f}  │  Fuel: [bold green]{fuel:4.1f}[/]L  │  Aero: {df:4.0f}N"
            )

            thr = telem.get("throttle", 0.0)
            brk = telem.get("brake", 0.0)
            steer = telem.get("steering", 0.0)

            self.bar_throttle.update(progress=int(thr * 100))
            self.bar_brake.update(progress=int(brk * 100))
            self.bar_steer.update(progress=int((steer + 1.0) * 50))

            wheels = telem.get("wheels", [])
            if len(wheels) == 4:
                w_fl, w_fr, w_rl, w_rr = wheels[0], wheels[1], wheels[2], wheels[3]
                self.txt_wheels_front.update(
                    f"FL: [bold white]{w_fl['temp']:3.0f}°C[/] (Slip: {w_fl['slip']:+4.2f} │ {w_fl['brake_temp']:3.0f}°C Brk)   "
                    f"FR: [bold white]{w_fr['temp']:3.0f}°C[/] (Slip: {w_fr['slip']:+4.2f} │ {w_fr['brake_temp']:3.0f}°C Brk)"
                )
                self.txt_wheels_rear.update(
                    f"RL: [bold white]{w_rl['temp']:3.0f}°C[/] (Slip: {w_rl['slip']:+4.2f} │ {w_rl['brake_temp']:3.0f}°C Brk)   "
                    f"RR: [bold white]{w_rr['temp']:3.0f}°C[/] (Slip: {w_rr['slip']:+4.2f} │ {w_rr['brake_temp']:3.0f}°C Brk)"
                )

        sc = self.engine.latest_scoring
        if sc:
            self.txt_scoring.update(
                f"Track: [bold cyan]'{sc.get('track', 'N/A')}'[/] │ Lap: [bold yellow]{sc.get('laps', 0)}[/] (Sector {sc.get('sector', 1)}) │ "
                f"Last: [bold green]{sc.get('last_lap', 0.0):.3f}s[/] │ Best: [bold magenta]{sc.get('best_lap', 0.0):.3f}s[/]"
            )

    def on_unmount(self) -> None:
        self._stop_mock_sim()
        self.engine.stop()


def main():
    parser = argparse.ArgumentParser(description="isiMotor UDP Telemetry Sniffer & Frequency Benchmark (Textual)")
    parser.add_argument("--host", default="0.0.0.0", help="UDP listening host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="UDP listening port (default: 5000)")
    parser.add_argument("--mock", action="store_true", help="Start with simulated mock telemetry transmitter enabled")
    args = parser.parse_args()

    app = IsiMotorBenchmarkApp(host=args.host, port=args.port, mock=args.mock)
    app.run()


if __name__ == "__main__":
    main()
