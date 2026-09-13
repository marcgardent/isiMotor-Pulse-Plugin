"""
Common data models: 3D vector, packet header, and system events.
"""

import math
from dataclasses import dataclass

from .enums import SystemEventType


@dataclass(frozen=True)
class TelemVect3:
    """3D Vector in isiMotor coordinates (meters or rad/s or m/s)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @property
    def magnitude(self) -> float:
        """Euclidean norm / magnitude of the vector."""
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class RawUdpHeader:
    """
    Standard 24-byte UDP packet header (SIMP protocol).
    """

    magic: bytes = b"SIMP"
    protocol_version: int = 1
    packet_type: int = 0
    """Discriminates the payload's wire format; see `PacketType`."""
    payload_size: int = 0
    sequence_number: int = 0
    session_et: float = 0.0
    chunk_index: int = 0
    total_chunks: int = 1
    sub_type_or_id: int = 0


@dataclass(frozen=True)
class SystemEvent:
    """
    System state event packet (SIMP Type 3 / PacketType.SYSTEM_EVENT, 6 bytes).
    """

    event_id: int = 0
    """See `SystemEventType`."""

    @property
    def name(self) -> str:
        try:
            return SystemEventType(self.event_id).name.title().replace("_", "")
        except ValueError:
            return f"Unknown({self.event_id})"

    @property
    def in_realtime(self) -> bool | None:
        if self.event_id in (SystemEventType.ENTER_REALTIME, SystemEventType.START_SESSION):
            return True
        elif self.event_id in (SystemEventType.EXIT_REALTIME, SystemEventType.END_SESSION):
            return False
        return None
