"""
Pit stop menu packet decoder.
"""

import struct
from typing import Optional
from ..constants import PIT_MENU_SIZE, PIT_MENU_STRUCT
from ..models import PitMenu
from .base import _decode_string


def decode_pit_menu(data: bytes, offset: int = 0) -> Optional[PitMenu]:
    """Decodes a 76-byte PitMenu packet (Type 6)."""
    if len(data) - offset < PIT_MENU_SIZE:
        return None

    cat_idx, raw_cat_name, choice_idx, raw_choice_str, num_choices = (
        struct.unpack_from(PIT_MENU_STRUCT, data, offset)
    )
    return PitMenu(
        category_index=cat_idx,
        category_name=_decode_string(raw_cat_name),
        choice_index=choice_idx,
        choice_string=_decode_string(raw_choice_str),
        num_choices=num_choices,
    )
