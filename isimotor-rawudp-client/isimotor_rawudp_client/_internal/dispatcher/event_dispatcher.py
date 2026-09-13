"""
Event dispatching layer for routing typed telemetry & scoring packets to callbacks.
"""

from collections.abc import Callable
from typing import Any

from isimotor_rawudp_types import (
    CompactScoring,
    ExtendedState,
    ForceFeedback,
    FullScoringSession,
    Graphics,
    HWControlCommand,
    SystemEvent,
    TelemInfo,
    WeatherControl,
    WeatherControlCommand,
)

PacketCallback = Callable[[Any], None]


class EventDispatcher:
    """
    Manages callback subscriptions and dispatches decoded packets.

    One `dispatch_*` method per domain type: the caller already knows which
    packet it just decoded, so it is told here once, directly, by calling
    the matching method - the attribute callback to invoke is never
    re-decided via an isinstance ladder.
    """

    def __init__(self) -> None:
        # Standard callback attributes for direct property access
        self.on_telemetry: Callable[[TelemInfo], None] | None = None
        self.on_scoring: Callable[[CompactScoring], None] | None = None
        self.on_full_scoring: Callable[[FullScoringSession], None] | None = None
        self.on_weather: Callable[[WeatherControl], None] | None = None
        self.on_extended_state: Callable[[ExtendedState], None] | None = None
        self.on_force_feedback: Callable[[ForceFeedback], None] | None = None
        self.on_graphics: Callable[[Graphics], None] | None = None
        self.on_system_event: Callable[[SystemEvent], None] | None = None
        self.on_hw_control: Callable[[HWControlCommand], None] | None = None
        self.on_weather_control: Callable[[WeatherControlCommand], None] | None = None
        self.on_packet: Callable[[Any], None] | None = None

        # Dynamic type-based listeners (Open/Closed principle)
        self._listeners: dict[type, list[PacketCallback]] = {}

    def subscribe(self, packet_cls: type, callback: PacketCallback) -> None:
        """Subscribes a callback to a specific packet class type."""
        if packet_cls not in self._listeners:
            self._listeners[packet_cls] = []
        self._listeners[packet_cls].append(callback)

    def unsubscribe(self, packet_cls: type, callback: PacketCallback) -> None:
        """Unsubscribes a callback from a specific packet class type."""
        if packet_cls in self._listeners and callback in self._listeners[packet_cls]:
            self._listeners[packet_cls].remove(callback)

    def _dispatch(self, packet: Any, attribute_callback: PacketCallback | None) -> None:
        """Shared plumbing: global listener, the one matching attribute callback, dynamic listeners."""
        if packet is None:
            return

        if self.on_packet:
            try:
                self.on_packet(packet)
            except Exception:
                pass

        if attribute_callback:
            try:
                attribute_callback(packet)
            except Exception:
                pass

        for cb in self._listeners.get(type(packet), ()):
            try:
                cb(packet)
            except Exception:
                pass

    def dispatch_telemetry(self, packet: TelemInfo) -> None:
        """Dispatches a decoded TelemInfo frame to its matching listeners."""
        self._dispatch(packet, self.on_telemetry)

    def dispatch_scoring(self, packet: CompactScoring) -> None:
        """Dispatches a decoded CompactScoring frame to its matching listeners."""
        self._dispatch(packet, self.on_scoring)

    def dispatch_full_scoring(self, packet: FullScoringSession) -> None:
        """Dispatches a decoded FullScoringSession frame to its matching listeners."""
        self._dispatch(packet, self.on_full_scoring)

    def dispatch_weather(self, packet: WeatherControl) -> None:
        """Dispatches a decoded WeatherControl frame to its matching listeners."""
        self._dispatch(packet, self.on_weather)

    def dispatch_extended_state(self, packet: ExtendedState) -> None:
        """Dispatches a decoded ExtendedState frame to its matching listeners."""
        self._dispatch(packet, self.on_extended_state)

    def dispatch_force_feedback(self, packet: ForceFeedback) -> None:
        """Dispatches a decoded ForceFeedback frame to its matching listeners."""
        self._dispatch(packet, self.on_force_feedback)

    def dispatch_graphics(self, packet: Graphics) -> None:
        """Dispatches a decoded Graphics frame to its matching listeners."""
        self._dispatch(packet, self.on_graphics)

    def dispatch_system_event(self, packet: SystemEvent) -> None:
        """Dispatches a decoded SystemEvent to its matching listeners."""
        self._dispatch(packet, self.on_system_event)

    def dispatch_hw_control(self, packet: HWControlCommand) -> None:
        """Dispatches a decoded HWControlCommand to its matching listeners."""
        self._dispatch(packet, self.on_hw_control)

    def dispatch_weather_control(self, packet: WeatherControlCommand) -> None:
        """Dispatches a decoded WeatherControlCommand to its matching listeners."""
        self._dispatch(packet, self.on_weather_control)
