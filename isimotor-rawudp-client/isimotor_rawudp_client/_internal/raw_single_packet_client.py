"""
Raw single-packet-type ZeroMQ client - no decoding.

The lowest level of the single-packet-type client family: it hands out the
raw ZeroMQ message bytes for exactly one packet type, undecoded. Which
packet type it listens to is pinned once, at construction, so there is no
packet_type dispatch table and no decoder involved at all here.
`DomainSinglePacketClient[T]` builds on top of this by adding a decoder; use this
class directly when you want the bytes themselves - e.g. to record/replay a
stream, or to decode with something other than this package's codecs.
"""

import threading
from collections.abc import Callable
from typing import Any

from .transport import ZmqSubscriber


class RawSinglePacketClient:
    """
    Ultra-low latency ZeroMQ client dedicated to exactly one outbound packet
    type, exposing its raw undecoded message bytes.
    """

    def __init__(
        self,
        packet_type: int,
        host: str = "127.0.0.1",
        base_port: int = 5000,
    ) -> None:
        self.packet_type = packet_type
        self._receiver = ZmqSubscriber(host=host, port=base_port, packet_types=(packet_type,))
        self._lock = threading.Lock()
        self._latest: bytes | None = None
        self._packet_count = 0
        self._last_packet_time = 0.0
        self.on_packet: Callable[[bytes], None] | None = None

    # ── Context Manager Protocol ───────────────────────────────────────────────

    def __enter__(self) -> "RawSinglePacketClient":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    # ── Lifecycle Orchestration ─────────────────────────────────────────────────

    def start(self) -> "RawSinglePacketClient":
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
        with self._lock:
            self._latest = data
            self._packet_count += 1
            self._last_packet_time = timestamp

        if self.on_packet:
            try:
                self.on_packet(data)
            except Exception:
                pass

    # ── State Accessors (Thread-Safe) ──────────────────────────────────────────

    def get_latest(self) -> bytes | None:
        """Returns the most recently received raw message bytes thread-safely."""
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
