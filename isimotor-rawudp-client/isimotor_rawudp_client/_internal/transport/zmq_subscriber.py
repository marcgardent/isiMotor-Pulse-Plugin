"""
Non-blocking ZeroMQ SUB receiver thread and socket transport.

The isiMotor plugin publishes each outbound packet type on its own ZeroMQ PUB
socket, bound on its own TCP port (base_port + packet_type) so that a
consumer can subscribe to only the stream(s) it needs. Ports are hardcoded
arithmetically for now, pending a future service registry that will allocate
them dynamically. This class opens one SUB socket per known packet type,
connected to the plugin, and fans all of them into a single callback. Since
several packet types are pure FlatBuffers with no outer header (the message
boundary IS the FlatBuffer), the callback is told which packet type a given
message came from via the socket it arrived on, rather than by inspecting
the payload.
"""

import threading
import time
from collections.abc import Callable, Iterable

import zmq

DataReceivedCallback = Callable[[int, bytes, float], None]

# Outbound packet types actually emitted by the plugin (see
# isimotor-rawudp-plugin/src/main.cpp's kOutboundPacketTypes), each bound on
# its own port (base_port + packet_type).
OUTBOUND_PACKET_TYPES: tuple[int, ...] = (1, 2, 3, 4, 7, 8, 9, 10)


class ZmqSubscriber:
    """
    Low-latency non-blocking ZeroMQ SUB receiver managing background thread and socket lifecycle.

    Opens one SUB socket per requested packet type (every outbound type by
    default, or a smaller fixed set - e.g. just one - passed as
    `packet_types`), each connected to ``tcp://{host}:{base_port + packet_type}``.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        packet_types: Iterable[int] = OUTBOUND_PACKET_TYPES,
    ) -> None:
        self.host = host
        self.port = port  # Base port; per-type endpoints are base_port + packet_type.
        self.packet_types = tuple(packet_types)
        self._context: zmq.Context | None = None
        self._sockets: list[tuple[int, zmq.Socket]] = []
        self._poller: zmq.Poller | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._on_data_received: DataReceivedCallback | None = None

    def endpoint_for(self, packet_type: int) -> str:
        return f"tcp://{self.host}:{self.port + packet_type}"

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
        self._poller = zmq.Poller()
        self._sockets = []

        for packet_type in self.packet_types:
            sock = self._context.socket(zmq.SUB)
            sock.setsockopt(zmq.SUBSCRIBE, b"")
            sock.setsockopt(zmq.LINGER, 0)
            sock.connect(self.endpoint_for(packet_type))
            self._poller.register(sock, zmq.POLLIN)
            self._sockets.append((packet_type, sock))

        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="IsiMotorZmqSubscriber")
        self._thread.start()

    def stop(self) -> None:
        """Stops the receiver thread and closes all sockets."""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

        for _packet_type, sock in self._sockets:
            try:
                sock.close()
            except Exception:
                pass
        self._sockets = []

        if self._context:
            try:
                self._context.term()
            except Exception:
                pass
            self._context = None

        self._poller = None

    def _listen_loop(self) -> None:
        """Internal low-latency poll and receive loop, fanning in from every connected socket."""
        while self._running:
            if not self._sockets or not self._poller:
                time.sleep(0.005)
                continue

            try:
                events = dict(self._poller.poll(timeout=10))
                for packet_type, sock in self._sockets:
                    if sock not in events:
                        continue
                    while self._running:
                        try:
                            data = sock.recv(flags=zmq.NOBLOCK)
                            now = time.time()
                            if self._on_data_received:
                                self._on_data_received(packet_type, data, now)
                        except zmq.Again:
                            break
            except zmq.ZMQError:
                if not self._running:
                    break
