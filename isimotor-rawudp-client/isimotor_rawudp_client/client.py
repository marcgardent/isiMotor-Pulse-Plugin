"""
High-level UDP Client for receiving isiMotor telemetry and scoring packets.
"""

import socket
import select
import threading
import time
from typing import Optional, Callable, Generator, List, Union
from .models import TelemInfo, CompactScoring, SystemEvent
from .decoder import decode_packet, decode_telemetry, decode_compact_scoring, decode_system_event


class IsiMotorClient:
    """
    Thread-safe UDP Client for isiMotor-RawUDP-Plugin.
    
    Usage Examples:
    
    1. Callback-based:
        client = IsiMotorClient(port=5000)
        client.on_telemetry = lambda t: print(f"RPM: {t.engine_rpm}, Speed: {t.speed_kmh:.1f}")
        client.start()
        ...
        client.stop()

    2. Context Manager / Polling:
        with IsiMotorClient(port=5000) as client:
            while True:
                telem = client.get_latest_telemetry()
                if telem:
                    print(telem.gear_str, telem.speed_kmh)
                time.sleep(0.01)

    3. Generator Stream:
        client = IsiMotorClient(port=5000)
        for telemetry in client.stream_telemetry():
            print(telemetry.speed_kmh)
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        self.host = host
        self.port = port

        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Cached latest frames
        self._latest_telemetry: Optional[TelemInfo] = None
        self._latest_scoring: Optional[CompactScoring] = None
        self._latest_system_event: Optional[SystemEvent] = None
        self._last_packet_time: float = 0.0
        self._packet_count: int = 0

        # Callbacks
        self.on_telemetry: Optional[Callable[[TelemInfo], None]] = None
        self.on_scoring: Optional[Callable[[CompactScoring], None]] = None
        self.on_system_event: Optional[Callable[[SystemEvent], None]] = None
        self.on_packet: Optional[Callable[[Union[TelemInfo, CompactScoring, SystemEvent]], None]] = None

    def start(self) -> "IsiMotorClient":
        """Starts the background receiver thread."""
        if self._running:
            return self

        self._running = True
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        self._socket.bind((self.host, self.port))

        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="IsiMotorUdpReceiver")
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stops the background receiver thread and closes socket."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def _listen_loop(self) -> None:
        """Internal ultra-low latency receive loop."""
        while self._running:
            if not self._socket:
                time.sleep(0.005)
                continue

            try:
                r, _, _ = select.select([self._socket], [], [], 0.01)
                if r:
                    while self._running:
                        try:
                            data, _ = self._socket.recvfrom(65535)
                            now = time.time()
                            pkt = decode_packet(data)

                            if pkt is not None:
                                with self._lock:
                                    self._last_packet_time = now
                                    self._packet_count += 1

                                    if isinstance(pkt, TelemInfo):
                                        self._latest_telemetry = pkt
                                    elif isinstance(pkt, CompactScoring):
                                        self._latest_scoring = pkt
                                    elif isinstance(pkt, SystemEvent):
                                        self._latest_system_event = pkt

                                # Invoke callbacks outside lock
                                if self.on_packet:
                                    self.on_packet(pkt)

                                if isinstance(pkt, TelemInfo) and self.on_telemetry:
                                    self.on_telemetry(pkt)
                                elif isinstance(pkt, CompactScoring) and self.on_scoring:
                                    self.on_scoring(pkt)
                                elif isinstance(pkt, SystemEvent) and self.on_system_event:
                                    self.on_system_event(pkt)

                        except (BlockingIOError, socket.error):
                            break
            except Exception:
                if not self._running:
                    break

    def get_latest_telemetry(self) -> Optional[TelemInfo]:
        """Returns the most recently received TelemInfo frame thread-safely."""
        with self._lock:
            return self._latest_telemetry

    def get_latest_scoring(self) -> Optional[CompactScoring]:
        """Returns the most recently received CompactScoring frame thread-safely."""
        with self._lock:
            return self._latest_scoring

    def get_latest_system_event(self) -> Optional[SystemEvent]:
        """Returns the most recently received SystemEvent thread-safely."""
        with self._lock:
            return self._latest_system_event

    def is_connected(self, timeout: float = 1.0) -> bool:
        """Returns True if a valid packet was received within the timeout."""
        with self._lock:
            return (time.time() - self._last_packet_time) < timeout if self._last_packet_time > 0 else False

    @property
    def packet_count(self) -> int:
        """Total number of packets received."""
        with self._lock:
            return self._packet_count

    def stream_telemetry(self, poll_interval: float = 0.005) -> Generator[TelemInfo, None, None]:
        """Generator yielding new telemetry frames as they arrive."""
        if not self._running:
            self.start()

        last_ts = 0.0
        while self._running:
            with self._lock:
                telem = self._latest_telemetry
                ts = self._last_packet_time

            if telem and ts != last_ts:
                last_ts = ts
                yield telem
            time.sleep(poll_interval)

    def __enter__(self) -> "IsiMotorClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
