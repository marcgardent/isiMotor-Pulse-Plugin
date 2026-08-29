"""
Inbound control and simulation command data models.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HWControlCommand:
    """
    Inbound Hardware / Button Box / Pit Menu Control Command (SIMP Type 100, 44 bytes).
    """

    control_name: str = ""  # Control name (e.g. "PitMenuUp", "TCIncrease", "ABSDecrease")
    control_value: float = 1.0  # 1.0 for press/trigger, 0.0 for release
    duration_ms: int = 50  # Pulse duration in ms (default 50ms)


@dataclass(frozen=True)
class WeatherControlCommand:
    """
    Inbound Weather Control Override Command (SIMP Type 101, 64 bytes).
    """

    ambient_temp: float = 20.0  # Air temperature (°C)
    track_temp: float = 25.0  # Track surface temperature (°C)
    dark_cloud: float = 0.0  # Overcast fraction (0.0 to 1.0)
    raining: float = 0.0  # Rain intensity (0.0 to 1.0)
    wind_speed: float = 0.0  # Wind speed (m/s)
    wind_direction: float = 0.0  # Wind angle in radians
    min_path_wetness: float = 0.0  # Minimum racing line wetness (0.0 to 1.0)
    max_path_wetness: float = 0.0  # Maximum off-line wetness (0.0 to 1.0)
