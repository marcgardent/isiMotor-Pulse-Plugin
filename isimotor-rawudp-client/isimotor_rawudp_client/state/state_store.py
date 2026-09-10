"""
Thread-safe client state and latest telemetry / scoring cache store.
"""

import threading
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


class StateStore:
    """
    Thread-safe storage holding the most recently received packet of each domain type.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_telemetry: TelemInfo | None = None
        self._latest_scoring: CompactScoring | None = None
        self._latest_full_scoring: FullScoringSession | None = None
        self._latest_weather: WeatherControl | None = None
        self._latest_extended_state: ExtendedState | None = None
        self._latest_force_feedback: ForceFeedback | None = None
        self._latest_graphics: Graphics | None = None
        self._latest_system_event: SystemEvent | None = None
        self._latest_hw_control: HWControlCommand | None = None
        self._latest_weather_control: WeatherControlCommand | None = None
        self._last_packet_time: float = 0.0
        self._packet_count: int = 0

    def update(self, packet: Any, timestamp: float) -> None:
        """Updates internal cache with a new decoded packet under lock."""
        with self._lock:
            self._last_packet_time = timestamp
            self._packet_count += 1

            if isinstance(packet, TelemInfo):
                self._latest_telemetry = packet
            elif isinstance(packet, CompactScoring):
                self._latest_scoring = packet
            elif isinstance(packet, FullScoringSession):
                self._latest_full_scoring = packet
            elif isinstance(packet, WeatherControl):
                self._latest_weather = packet
            elif isinstance(packet, ExtendedState):
                self._latest_extended_state = packet
            elif isinstance(packet, ForceFeedback):
                self._latest_force_feedback = packet
            elif isinstance(packet, Graphics):
                self._latest_graphics = packet
            elif isinstance(packet, SystemEvent):
                self._latest_system_event = packet
            elif isinstance(packet, HWControlCommand):
                self._latest_hw_control = packet
            elif isinstance(packet, WeatherControlCommand):
                self._latest_weather_control = packet

    def get_telemetry(self) -> TelemInfo | None:
        """Returns the most recently received TelemInfo frame thread-safely."""
        with self._lock:
            return self._latest_telemetry

    def get_scoring(self) -> CompactScoring | None:
        """Returns the most recently received CompactScoring frame thread-safely."""
        with self._lock:
            return self._latest_scoring

    def get_full_scoring(self) -> FullScoringSession | None:
        """Returns the most recently received FullScoringSession frame thread-safely."""
        with self._lock:
            return self._latest_full_scoring

    def get_weather(self) -> WeatherControl | None:
        """Returns the most recently received WeatherControl frame thread-safely."""
        with self._lock:
            return self._latest_weather

    def get_extended_state(self) -> ExtendedState | None:
        """Returns the most recently received ExtendedState frame thread-safely."""
        with self._lock:
            return self._latest_extended_state

    def get_force_feedback(self) -> ForceFeedback | None:
        """Returns the most recently received ForceFeedback frame thread-safely."""
        with self._lock:
            return self._latest_force_feedback

    def get_graphics(self) -> Graphics | None:
        """Returns the most recently received Graphics frame thread-safely."""
        with self._lock:
            return self._latest_graphics

    def get_system_event(self) -> SystemEvent | None:
        """Returns the most recently received SystemEvent thread-safely."""
        with self._lock:
            return self._latest_system_event

    def get_hw_control(self) -> HWControlCommand | None:
        """Returns the most recently received HWControlCommand thread-safely."""
        with self._lock:
            return self._latest_hw_control

    def get_weather_control(self) -> WeatherControlCommand | None:
        """Returns the most recently received WeatherControlCommand thread-safely."""
        with self._lock:
            return self._latest_weather_control

    @property
    def packet_count(self) -> int:
        with self._lock:
            return self._packet_count

    @property
    def last_packet_time(self) -> float:
        with self._lock:
            return self._last_packet_time

    def reset(self) -> None:
        """Clears all cached state."""
        with self._lock:
            self._latest_telemetry = None
            self._latest_scoring = None
            self._latest_full_scoring = None
            self._latest_track_rules = None
            self._latest_pit_menu = None
            self._latest_weather = None
            self._latest_extended_state = None
            self._latest_force_feedback = None
            self._latest_graphics = None
            self._latest_system_event = None
            self._latest_hw_control = None
            self._latest_weather_control = None
            self._last_packet_time = 0.0
            self._packet_count = 0
