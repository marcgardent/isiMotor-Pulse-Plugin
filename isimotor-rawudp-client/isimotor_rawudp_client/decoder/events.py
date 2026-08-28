"""
System state event packet decoder.
"""

from typing import Optional
from ..models import SystemEvent


def decode_system_event(data: bytes, offset: int = 0) -> Optional[SystemEvent]:
    """Decodes a 6-byte SIMP Type 3 system event packet."""
    if len(data) - offset < 2:
        return None
    event_id = data[offset + 5] if (offset == 0 and data.startswith(b"SIMP")) else data[offset]
    return SystemEvent(event_id=event_id)
