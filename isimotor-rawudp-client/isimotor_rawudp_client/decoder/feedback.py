"""
Steering shaft force feedback packet decoder.
"""

import struct

from ..constants import FORCE_FEEDBACK_SIZE, FORCE_FEEDBACK_STRUCT
from ..models import ForceFeedback


def decode_force_feedback(data: bytes, offset: int = 0) -> ForceFeedback | None:
    """Decodes an 8-byte ForceFeedback packet (Type 9)."""
    if len(data) - offset < FORCE_FEEDBACK_SIZE:
        return None

    force_val = struct.unpack_from(FORCE_FEEDBACK_STRUCT, data, offset)[0]
    return ForceFeedback(force_value=force_val)
