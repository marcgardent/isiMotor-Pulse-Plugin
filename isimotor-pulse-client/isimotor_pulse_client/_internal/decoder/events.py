"""
System state event packet decoder.

Wire format: FlatBuffers (schemas/system_event.fbs), one message per packet
type 3 (its own ZeroMQ port), no header/framing.
"""

from isimotor_pulse_types import SystemEvent

from .fbs_codec import decode_system_event_fbs


def decode_system_event(data: bytes, offset: int = 0) -> SystemEvent | None:
    """Decodes a SystemEvent FlatBuffer payload (packet type 3)."""
    event_type = decode_system_event_fbs(data[offset:] if offset else data)
    if event_type is None:
        return None
    return SystemEvent(event_id=event_type)
