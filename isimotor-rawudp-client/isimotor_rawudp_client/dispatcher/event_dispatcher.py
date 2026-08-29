"""
Event dispatching layer for routing typed telemetry & scoring packets to callbacks.
"""

from collections.abc import Callable
from typing import Any

from ..models import (
    CompactScoring,
    ExtendedState,
    ForceFeedback,
    FullScoringSession,
    Graphics,
    HWControlCommand,
    PitMenu,
    SystemEvent,
    TelemInfo,
    TrackRulesSession,
    WeatherControl,
    WeatherControlCommand,
)

PacketCallback = Callable[[Any], None]


class EventDispatcher:
    """
    Manages callback subscriptions and dispatches decoded packets.
    """

    def __init__(self) -> None:
        # Standard callback attributes for direct property access
        self.on_telemetry: Callable[[TelemInfo], None] | None = None
        self.on_scoring: Callable[[CompactScoring], None] | None = None
        self.on_full_scoring: Callable[[FullScoringSession], None] | None = None
        self.on_track_rules: Callable[[TrackRulesSession], None] | None = None
        self.on_pit_menu: Callable[[PitMenu], None] | None = None
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

    def dispatch(self, packet: Any) -> None:
        """Dispatches packet to all matching listeners and attribute callbacks."""
        if packet is None:
            return

        # 1. Global packet listener
        if self.on_packet:
            try:
                self.on_packet(packet)
            except Exception:
                pass

        # 2. Attribute-based callbacks
        if isinstance(packet, TelemInfo) and self.on_telemetry:
            try:
                self.on_telemetry(packet)
            except Exception:
                pass
        elif isinstance(packet, CompactScoring) and self.on_scoring:
            try:
                self.on_scoring(packet)
            except Exception:
                pass
        elif isinstance(packet, FullScoringSession) and self.on_full_scoring:
            try:
                self.on_full_scoring(packet)
            except Exception:
                pass
        elif isinstance(packet, TrackRulesSession) and self.on_track_rules:
            try:
                self.on_track_rules(packet)
            except Exception:
                pass
        elif isinstance(packet, PitMenu) and self.on_pit_menu:
            try:
                self.on_pit_menu(packet)
            except Exception:
                pass
        elif isinstance(packet, WeatherControl) and self.on_weather:
            try:
                self.on_weather(packet)
            except Exception:
                pass
        elif isinstance(packet, ExtendedState) and self.on_extended_state:
            try:
                self.on_extended_state(packet)
            except Exception:
                pass
        elif isinstance(packet, ForceFeedback) and self.on_force_feedback:
            try:
                self.on_force_feedback(packet)
            except Exception:
                pass
        elif isinstance(packet, Graphics) and self.on_graphics:
            try:
                self.on_graphics(packet)
            except Exception:
                pass
        elif isinstance(packet, SystemEvent) and self.on_system_event:
            try:
                self.on_system_event(packet)
            except Exception:
                pass
        elif isinstance(packet, HWControlCommand) and self.on_hw_control:
            try:
                self.on_hw_control(packet)
            except Exception:
                pass
        elif isinstance(packet, WeatherControlCommand) and self.on_weather_control:
            try:
                self.on_weather_control(packet)
            except Exception:
                pass

        # 3. Dynamic type-based listeners
        pkt_type = type(packet)
        if pkt_type in self._listeners:
            for cb in self._listeners[pkt_type]:
                try:
                    cb(packet)
                except Exception:
                    pass
