"""
Steering shaft force feedback packet decoder.

Wire format: FlatBuffers (schemas/force_feedback.fbs), one message per packet
type 9 (its own ZeroMQ port), no header/framing.
"""

from isimotor_pulse_types import ForceFeedback

from .fbs_codec import decode_force_feedback_fbs


def decode_force_feedback(data: bytes, offset: int = 0) -> ForceFeedback | None:
    """Decodes a ForceFeedback FlatBuffer payload (packet type 9)."""
    force_val = decode_force_feedback_fbs(data[offset:] if offset else data)
    if force_val is None:
        return None
    return ForceFeedback(force_value=force_val)
