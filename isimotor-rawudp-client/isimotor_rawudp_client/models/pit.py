"""
Pit stop menu state and pit navigation action models.
"""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class PitMenu:
    """
    Live in-car pit stop menu state (SIMP Type 6, 76 bytes).
    """

    category_index: int = 0
    category_name: str = ""
    choice_index: int = 0
    choice_string: str = ""
    num_choices: int = 0

    @property
    def is_available(self) -> bool:
        return self.num_choices > 0 or len(self.category_name) > 0


class PitAction(str, Enum):
    """Convenience pit menu navigation actions for button boxes / Stream Deck."""

    MENU_UP = "PitMenuUp"
    MENU_DOWN = "PitMenuDown"
    MENU_PREV = "PitMenuPrev"
    MENU_NEXT = "PitMenuNext"
    MENU_SELECT = "PitMenuSelect"
