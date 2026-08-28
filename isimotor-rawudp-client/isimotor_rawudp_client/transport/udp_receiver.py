"""
Non-blocking UDP receiver thread and socket transport.
"""

import socket
import select
import threading
import time
from typing import Optional, Callable

DataReceivedCallback = Callable[[bytes, float], None]


class UdpReceiver:
    """
    Low-latency non-blocking UDP datagram receiver managing background thread and socket lifecycle.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5000) -> None:
        self.host = host
        self.port = port
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._on_data_received: Optional[DataReceivedCallback] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, on_data_received: DataReceivedCallback) -> None:
        """Starts the background receiver thread with the specified datagram callback."""
        if self._running:
            return

        self._on_data_received = on_data_received
        self._running = True

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        self._socket.bind((self.host, self.port))

        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="IsiMotorUdpReceiver"
        )
        self._thread.start()

    def stop(self) -> None:
        """Stops the receiver thread and closes the socket."""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def _listen_loop(self) -> None:
        """Internal low-latency select and receive loop."""
        while self._running:
            if not self._socket:
                time.sleep(0.005)
                continue

            try:
                r, _, _ = select.select([self._socket], [], [], 0.01)
                if r:
                    while self._running:
                        try:
                            data, _ = self._socket.recvfrom(65535)
                            now = time.time()
                            if self._on_data_received:
                                self._on_data_received(data, now)
                        except (BlockingIOError, socket.error):
                            break
            except Exception:
                if not self._running:
                    break
