"""
Graphics rendering, camera viewpoint, and lighting data models.
"""

from dataclasses import dataclass, field
from typing import Tuple
from .common import TelemVect3


@dataclass(frozen=True)
class Graphics:
    """
    Graphics rendering, camera viewpoint & ambient lighting (SIMP Type 10 @ 60-100Hz, 128 bytes).
    """
    cam_pos: TelemVect3 = field(default_factory=TelemVect3)
    cam_ori: Tuple[TelemVect3, TelemVect3, TelemVect3] = (
        TelemVect3(1.0, 0.0, 0.0),
        TelemVect3(0.0, 1.0, 0.0),
        TelemVect3(0.0, 0.0, 1.0),
    )
    ambient_rgb: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    slot_id: int = -1                      # Slot ID being viewed (-1 if none)
    camera_type: int = 1                   # 0=TV Cockpit, 1=Cockpit, 2=Nose, 3=Swingman, 4=Trackside, 5+=Onboard

    @property
    def is_cockpit_view(self) -> bool:
        """True if camera is currently inside cockpit."""
        return self.camera_type in (0, 1)

    @property
    def camera_type_str(self) -> str:
        types = {
            0: "TV Cockpit",
            1: "Cockpit",
            2: "Nosecam",
            3: "Swingman",
            4: "Trackside",
        }
        if self.camera_type >= 5:
            return f"Onboard #{self.camera_type - 5}"
        return types.get(self.camera_type, f"Camera({self.camera_type})")
