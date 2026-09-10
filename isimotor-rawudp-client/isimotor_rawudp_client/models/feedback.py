"""
Steering shaft force feedback data models.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ForceFeedback:
    """
    Ultra-high frequency Steering Shaft Force Feedback Torque (SIMP Type 9 @ up to 400Hz, 8 bytes).
    """

    force_value: float = 0.0
    """Steering shaft FFB torque (-1.0 to +1.0 normalized or N·m)."""

    @property
    def percentage(self) -> float:
        """Force feedback output percentage (-100% to +100%)."""
        return self.force_value * 100.0
