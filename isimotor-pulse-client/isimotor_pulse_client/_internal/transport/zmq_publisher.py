"""
Outbound ZeroMQ command transmitter for hardware controls, pit menu actions, and weather overrides.

The isiMotor plugin subscribes to inbound commands as a ZeroMQ SUB socket
bound on a TCP endpoint; this class connects to it as a PUB socket and
publishes commands to it. The PUB socket is created once and reused across
calls (unlike the previous per-call UDP socket).
"""

import threading
import time

import zmq

from ..decoder.commands import encode_hw_control, encode_weather_control


class ZmqPublisher:
    """
    Handles encoding and transmission of inbound simulation commands to the game plugin.
    """

    def __init__(self, default_host: str = "127.0.0.1", default_port: int = 5101) -> None:
        self.default_host = default_host
        self.default_port = default_port
        self._lock = threading.Lock()
        self._context: zmq.Context | None = None
        self._socket: zmq.Socket | None = None
        self._connected_endpoint: str | None = None

    def _ensure_connected(self, host: str, port: int) -> None:
        """Lazily creates the PUB socket and (re)connects it if the target endpoint changed."""
        endpoint = f"tcp://{host}:{port}"
        if self._socket is not None and self._connected_endpoint == endpoint:
            return

        with self._lock:
            if self._context is None:
                self._context = zmq.Context()
            if self._socket is not None:
                try:
                    self._socket.close()
                except Exception:
                    pass
            self._socket = self._context.socket(zmq.PUB)
            self._socket.setsockopt(zmq.LINGER, 0)
            self._socket.connect(endpoint)
            self._connected_endpoint = endpoint
            # Mitigates the ZeroMQ PUB/SUB "slow joiner" syndrome: give the
            # subscriber a brief moment to complete its connection handshake
            # before the very first message is published on a fresh socket.
            time.sleep(0.1)

    def close(self) -> None:
        """Closes the underlying PUB socket and context, if any."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
            self._connected_endpoint = None

        if self._context:
            try:
                self._context.term()
            except Exception:
                pass
            self._context = None

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
        :param host: Destination host (defaults to self.default_host).
        :param port: Destination inbound port (defaults to self.default_port).
        """
        dest_host = host or self.default_host
        dest_port = port or self.default_port

        packet = encode_hw_control(
            control_name=control_name,
            control_value=control_value,
            duration_ms=duration_ms,
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
        :param host: Destination host (defaults to self.default_host).
        :param port: Destination inbound port (defaults to self.default_port).
        """
        dest_host = host or self.default_host
        dest_port = port or self.default_port

        packet = encode_weather_control(
            ambient_temp=ambient_temp,
            track_temp=track_temp,
            dark_cloud=dark_cloud,
            raining=raining,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            min_path_wetness=min_path_wetness,
            max_path_wetness=max_path_wetness,
        )

        return self._transmit(packet, dest_host, dest_port)

    def send_raw(self, packet: bytes, host: str | None = None, port: int | None = None) -> bool:
        """Publishes a pre-encoded raw command packet to the target plugin endpoint."""
        return self._transmit(packet, host or self.default_host, port or self.default_port)

    def _transmit(self, packet: bytes, host: str, port: int) -> bool:
        """Publishes a command packet to the target plugin endpoint."""
        try:
            self._ensure_connected(host, port)
            assert self._socket is not None
            self._socket.send(packet, flags=zmq.NOBLOCK)
            return True
        except Exception:
            return False
