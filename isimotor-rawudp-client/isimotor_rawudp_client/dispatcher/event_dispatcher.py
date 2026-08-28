"""
Event dispatching layer for routing typed telemetry & scoring packets to callbacks.
"""

from typing import Optional, Callable, Dict, List, Type, Any, Union
from ..models import (
    TelemInfo,
    CompactScoring,
    FullScoringSession,
    TrackRulesSession,
    PitMenu,
    WeatherControl,
    ExtendedState,
    ForceFeedback,
    Graphics,
    SystemEvent,
    HWControlCommand,
    WeatherControlCommand,
)

PacketCallback = Callable[[Any], None]


class EventDispatcher:
    """
    Manages callback subscriptions and dispatches decoded packets.
    """

    def __init__(self) -> None:
        # Standard callback attributes for direct property access
        self.on_telemetry: Optional[Callable[[TelemInfo], None]] = None
        self.on_scoring: Optional[Callable[[CompactScoring], None]] = None
        self.on_full_scoring: Optional[Callable[[FullScoringSession], None]] = None
        self.on_track_rules: Optional[Callable[[TrackRulesSession], None]] = None
        self.on_pit_menu: Optional[Callable[[PitMenu], None]] = None
        self.on_weather: Optional[Callable[[WeatherControl], None]] = None
        self.on_extended_state: Optional[Callable[[ExtendedState], None]] = None
        self.on_force_feedback: Optional[Callable[[ForceFeedback], None]] = None
        self.on_graphics: Optional[Callable[[Graphics], None]] = None
        self.on_system_event: Optional[Callable[[SystemEvent], None]] = None
        self.on_hw_control: Optional[Callable[[HWControlCommand], None]] = None
        self.on_weather_control: Optional[Callable[[WeatherControlCommand], None]] = None
        self.on_packet: Optional[Callable[[Any], None]] = None

        # Dynamic type-based listeners (Open/Closed principle)
        self._listeners: Dict[Type, List[PacketCallback]] = {}

    def subscribe(self, packet_cls: Type, callback: PacketCallback) -> None:
        """Subscribes a callback to a specific packet class type."""
        if packet_cls not in self._listeners:
            self._listeners[packet_cls] = []
        self._listeners[packet_cls].append(callback)

    def unsubscribe(self, packet_cls: Type, callback: PacketCallback) -> None:
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
