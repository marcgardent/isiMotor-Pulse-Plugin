"""
Single-packet-type ZeroMQ client.

Where `IsiMotorClient` fans in every outbound packet type into one shared
StateStore/EventDispatcher, `SinglePacketClient[T]` is the "I only care
about this one stream" counterpart: which packet type it handles is pinned
once, at construction (by the factory that built it), so there is no
packet_type dispatch table, no isinstance, no per-message "which packet is
this" decision anywhere in this class - it only ever sees one type.
"""

import threading
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from .transport import ZmqSubscriber

T = TypeVar("T")


class SinglePacketClient(Generic[T]):
    """
    Ultra-low latency ZeroMQ client dedicated to exactly one outbound packet type.

    Not meant to be constructed directly - use one of the `*_client()`
    factory functions in `single_packet_client_factory.py`, each of which
    pins the packet_type and decoder for one domain type.
    """

    def __init__(
        self,
        packet_type: int,
        decoder: Callable[[bytes], T | None],
        host: str = "127.0.0.1",
        base_port: int = 5000,
    ) -> None:
        self._decoder = decoder
        self._receiver = ZmqSubscriber(host=host, port=base_port, packet_types=(packet_type,))
        self._lock = threading.Lock()
        self._latest: T | None = None
        self._packet_count = 0
        self._last_packet_time = 0.0
        self.on_packet: Callable[[T], None] | None = None

    # ── Context Manager Protocol ───────────────────────────────────────────────

    def __enter__(self) -> "SinglePacketClient[T]":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    # ── Lifecycle Orchestration ─────────────────────────────────────────────────

    def start(self) -> "SinglePacketClient[T]":
        """Starts the background ZeroMQ SUB receiver thread."""
        self._receiver.start(self._on_datagram_received)
        return self

    def stop(self) -> None:
        """Stops the background ZeroMQ SUB receiver thread."""
        self._receiver.stop()

    @property
    def is_running(self) -> bool:
        """True if the ZeroMQ background listener thread is active."""
        return self._receiver.is_running

    # ── Internal Ingestion Pipeline ─────────────────────────────────────────────

    def _on_datagram_received(self, packet_type: int, data: bytes, timestamp: float) -> None:
        packet = self._decoder(data)
        if packet is None:
            return

        with self._lock:
            self._latest = packet
            self._packet_count += 1
            self._last_packet_time = timestamp

        if self.on_packet:
            try:
                self.on_packet(packet)
            except Exception:
                pass

    # ── State Accessors (Thread-Safe) ──────────────────────────────────────────

    def get_latest(self) -> T | None:
        """Returns the most recently received packet thread-safely."""
        with self._lock:
            return self._latest

    @property
    def packet_count(self) -> int:
        with self._lock:
            return self._packet_count

    @property
    def last_packet_time(self) -> float:
        with self._lock:
            return self._last_packet_time
