"""
System state event packet decoder.
"""

from isimotor_rawudp_types import SystemEvent


def decode_system_event(data: bytes, offset: int = 0) -> SystemEvent | None:
    """Decodes a 2-byte SIMP Type 3 system event payload."""
    if len(data) - offset < 2:
        return None
    return SystemEvent(event_id=data[offset])
