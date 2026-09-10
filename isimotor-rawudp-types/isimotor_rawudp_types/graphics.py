"""
Graphics rendering, camera viewpoint, and lighting data models.
"""

from dataclasses import dataclass, field

from .common import TelemVect3
from .enums import CameraType


@dataclass(frozen=True)
class Graphics:
    """
    Graphics rendering, camera viewpoint & ambient lighting (SIMP Type 10 @ 60-100Hz, 128 bytes).
    """

    cam_pos: TelemVect3 = field(default_factory=TelemVect3)
    cam_ori: tuple[TelemVect3, TelemVect3, TelemVect3] = (
        TelemVect3(1.0, 0.0, 0.0),
        TelemVect3(0.0, 1.0, 0.0),
        TelemVect3(0.0, 0.0, 1.0),
    )
    ambient_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    slot_id: int = -1
    """Slot ID being viewed (-1 if none)."""
    camera_type: int = CameraType.COCKPIT
    """See `CameraType`; values >= CameraType.ONBOARD are onboard camera slots."""

    @property
    def is_cockpit_view(self) -> bool:
        """True if camera is currently inside cockpit."""
        return self.camera_type in (CameraType.TV_COCKPIT, CameraType.COCKPIT)

    @property
    def camera_type_str(self) -> str:
        types = {
            CameraType.TV_COCKPIT: "TV Cockpit",
            CameraType.COCKPIT: "Cockpit",
            CameraType.NOSE: "Nosecam",
            CameraType.SWINGMAN: "Swingman",
            CameraType.TRACKSIDE: "Trackside",
        }
        if self.camera_type >= CameraType.ONBOARD:
            return f"Onboard #{self.camera_type - CameraType.ONBOARD}"
        return types.get(self.camera_type, f"Camera({self.camera_type})")
