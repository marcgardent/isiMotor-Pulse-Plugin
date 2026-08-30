"""
Outbound UDP command transmitter for hardware controls, pit menu actions, and weather overrides.
"""

import socket
import threading

from ..decoder.commands import encode_hw_control, encode_weather_control


class UdpSender:
    """
    Handles encoding and transmission of inbound simulation commands to the game plugin.
    """

    def __init__(self, default_host: str = "127.0.0.1", default_port: int = 5001) -> None:
        self.default_host = default_host
        self.default_port = default_port
        self._lock = threading.Lock()
        self._sequence_number = 0

    def _next_sequence(self) -> int:
        with self._lock:
            self._sequence_number += 1
            return self._sequence_number

    def send_hw_control(
        self,
        control_name: str,
        control_value: float = 1.0,
        duration_ms: int = 50,
        host: str | None = None,
        port: int | None = None,
    ) -> bool:
        """
        Transmits a hardware control command (SIMP Type 100) to the game plugin.

        :param control_name: Control name (e.g. "TCIncrease", "ABSDecrease").
        :param control_value: 1.0 = press/activate, 0.0 = release, or analog value.
        :param duration_ms: Pulse duration in milliseconds (default: 50ms).
        :param host: Destination IP (defaults to self.default_host).
        :param port: Destination inbound port (defaults to self.default_port).
        """
        dest_host = host or self.default_host
        dest_port = port or self.default_port
        seq = self._next_sequence()

        packet = encode_hw_control(
            control_name=control_name,
            control_value=control_value,
            duration_ms=duration_ms,
            with_header=True,
            sequence_number=seq,
        )

        return self._transmit(packet, dest_host, dest_port)

    def send_weather_override(
        self,
        ambient_temp: float = 20.0,
        track_temp: float = 25.0,
        dark_cloud: float = 0.0,
        raining: float = 0.0,
        wind_speed: float = 0.0,
        wind_direction: float = 0.0,
        min_path_wetness: float = 0.0,
        max_path_wetness: float = 0.0,
        host: str | None = None,
        port: int | None = None,
    ) -> bool:
        """
        Injects dynamic weather and ambient environmental conditions (SIMP Type 101) into the game session.

        :param ambient_temp: Ambient air temperature in °C.
        :param track_temp: Track surface temperature in °C.
        :param dark_cloud: Cloudiness / overcast fraction (0.0 to 1.0).
        :param raining: Rain intensity (0.0 to 1.0).
        :param wind_speed: Wind speed in m/s.
        :param wind_direction: Wind direction in radians.
        :param min_path_wetness: Minimum path wetness (0.0 to 1.0).
        :param max_path_wetness: Maximum off-line wetness (0.0 to 1.0).
        :param host: Destination IP (defaults to self.default_host).
        :param port: Destination inbound port (defaults to self.default_port).
        """
        dest_host = host or self.default_host
        dest_port = port or self.default_port
        seq = self._next_sequence()

        packet = encode_weather_control(
            ambient_temp=ambient_temp,
            track_temp=track_temp,
            dark_cloud=dark_cloud,
            raining=raining,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            min_path_wetness=min_path_wetness,
            max_path_wetness=max_path_wetness,
            with_header=True,
            sequence_number=seq,
        )

        return self._transmit(packet, dest_host, dest_port)

    def _transmit(self, packet: bytes, host: str, port: int) -> bool:
        """Sends raw UDP packet bytes to target destination."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(packet, (host, port))
            return True
        except Exception:
            return False
        finally:
            sock.close()
