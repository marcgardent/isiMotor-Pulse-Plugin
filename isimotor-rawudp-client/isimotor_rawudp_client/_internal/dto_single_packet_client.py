"""
Dto single-packet-type ZeroMQ client.

One level up from `RawSinglePacketClient`: instead of handing out raw
undecoded message bytes, it hands out the parsed FlatBuffer root accessor
for exactly one packet type - zero-copy, lazy field access, but not yet
converted into this package's friendly domain dataclass (that conversion is
`DomainSinglePacketClient[T]`, one level further up). Which root parser to apply
is pinned once, at construction (by the factory that built it).
"""

import threading
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from .raw_single_packet_client import RawSinglePacketClient

F = TypeVar("F")


class DtoSinglePacketClient(Generic[F]):
    """
    Ultra-low latency ZeroMQ client dedicated to exactly one outbound packet
    type, exposing its parsed FlatBuffer root accessor (no dataclass
    conversion).

    Not meant to be constructed directly - use one of the `*_client()`
    factory functions in `dto_single_packet_client_factory.py`, each
    of which pins the packet_type and root parser for one domain type.
    """

    def __init__(
        self,
        packet_type: int,
        root_parser: Callable[[bytes], F],
        host: str = "127.0.0.1",
        base_port: int = 5000,
    ) -> None:
        self._root_parser = root_parser
        self._raw = RawSinglePacketClient(packet_type=packet_type, host=host, base_port=base_port)
        self._raw.on_packet = self._on_raw_packet
        self._lock = threading.Lock()
        self._latest: F | None = None
        self._packet_count = 0
        self._last_packet_time = 0.0
        self.on_packet: Callable[[F], None] | None = None

    # ── Context Manager Protocol ───────────────────────────────────────────────

    def __enter__(self) -> "DtoSinglePacketClient[F]":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    # ── Lifecycle Orchestration ─────────────────────────────────────────────────

    def start(self) -> "DtoSinglePacketClient[F]":
        """Starts the background ZeroMQ SUB receiver thread."""
        self._raw.start()
        return self

    def stop(self) -> None:
        """Stops the background ZeroMQ SUB receiver thread."""
        self._raw.stop()

    @property
    def is_running(self) -> bool:
        """True if the ZeroMQ background listener thread is active."""
        return self._raw.is_running

    # ── Internal Ingestion Pipeline ─────────────────────────────────────────────

    def _on_raw_packet(self, data: bytes) -> None:
        """Parses one raw message handed up by the underlying RawSinglePacketClient into its FlatBuffer root."""
        if not data:
            return
        root = self._root_parser(data)

        with self._lock:
            self._latest = root
            self._packet_count += 1
            self._last_packet_time = self._raw.last_packet_time

        if self.on_packet:
            try:
                self.on_packet(root)
            except Exception:
                pass

    # ── State Accessors (Thread-Safe) ──────────────────────────────────────────

    def get_latest(self) -> F | None:
        """Returns the most recently received FlatBuffer root accessor thread-safely."""
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
