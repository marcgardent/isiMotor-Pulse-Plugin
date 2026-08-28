"""
Environmental conditions and live weather grid data models.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class WeatherControl:
    """
    Environmental conditions & weather node grid (SIMP Type 7, 108 bytes).
    """
    et: float = 0.0
    raining: Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]] = (
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    )
    cloudiness: float = 0.0                # 0.0 (clear) to 1.0 (dark overcast)
    ambient_temp_k: float = 293.15         # Air temp in Kelvin
    wind_max_speed: float = 0.0            # Wind speed in m/s
    apply_cloudiness_instantly: bool = False

    @property
    def ambient_temp_c(self) -> float:
        """Air temperature in Celsius (°C)."""
        return self.ambient_temp_k - 273.15

    @property
    def origin_raining(self) -> float:
        """Rain intensity at origin node [1][1] (0.0 to 1.0)."""
        return self.raining[1][1]
