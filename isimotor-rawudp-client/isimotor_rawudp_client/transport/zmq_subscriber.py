"""
Non-blocking ZeroMQ SUB receiver thread and socket transport.

The isiMotor plugin publishes telemetry as a ZeroMQ PUB socket bound on a
TCP endpoint; this class connects to it as a SUB socket subscribed to all
topics, mirroring the previous UDP receive semantics (single flat byte
stream, no application-level topic filtering).
"""

import threading
import time
from collections.abc import Callable

import zmq

DataReceivedCallback = Callable[[bytes, float], None]


class ZmqSubscriber:
    """
    Low-latency non-blocking ZeroMQ SUB receiver managing background thread and socket lifecycle.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5000) -> None:
        self.host = host
        self.port = port
        self._context: zmq.Context | None = None
        self._socket: zmq.Socket | None = None
        self._poller: zmq.Poller | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._on_data_received: DataReceivedCallback | None = None

    @property
    def endpoint(self) -> str:
        return f"tcp://{self.host}:{self.port}"

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, on_data_received: DataReceivedCallback) -> None:
        """Starts the background receiver thread with the specified datagram callback."""
        if self._running:
            return

        self._on_data_received = on_data_received
        self._running = True

        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt(zmq.SUBSCRIBE, b"")
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.connect(self.endpoint)

        self._poller = zmq.Poller()
        self._poller.register(self._socket, zmq.POLLIN)

        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="IsiMotorZmqSubscriber")
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

        if self._context:
            try:
                self._context.term()
            except Exception:
                pass
            self._context = None

        self._poller = None

    def _listen_loop(self) -> None:
        """Internal low-latency poll and receive loop."""
        while self._running:
            if not self._socket or not self._poller:
                time.sleep(0.005)
                continue

            try:
                events = dict(self._poller.poll(timeout=10))
                if self._socket in events:
                    while self._running:
                        try:
                            data = self._socket.recv(flags=zmq.NOBLOCK)
                            now = time.time()
                            if self._on_data_received:
                                self._on_data_received(data, now)
                        except zmq.Again:
                            break
            except zmq.ZMQError:
                if not self._running:
                    break
