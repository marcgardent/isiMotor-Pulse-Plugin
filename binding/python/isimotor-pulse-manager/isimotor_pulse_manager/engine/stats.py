"""
Packet statistics and timing metrics for telemetry channels.
"""

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class PacketStats:
    """Tracks throughput, frequency, latency and jitter for a specific packet stream."""

    name: str
    format_type: str
    expected_size: str
    count: int = 0
    bytes_total: int = 0
    timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=300))
    intervals: deque[float] = field(default_factory=lambda: deque(maxlen=150))
    logical_timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=300))
    last_timestamp: float = 0.0
    last_size: int = 0

    def record(self, size: int, now: float) -> None:
        """Records arrival of a packet of size bytes at timestamp now."""
        if self.last_timestamp > 0:
            dt = (now - self.last_timestamp) * 1000.0
            self.intervals.append(dt)
        self.last_timestamp = now
        self.timestamps.append(now)
        self.count += 1
        self.bytes_total += size
        self.last_size = size

    def record_logical(self, now: float) -> None:
        """Records a reassembled logical update event, for sliced/chunked packet types (e.g. FullScoring)."""
        self.logical_timestamps.append(now)

    def _windowed_freq(self, timestamps: "deque[float]") -> float:
        """Shared sliding-window Hz computation over an arbitrary timestamp deque."""
        now = time.time()
        if not timestamps or (now - timestamps[-1]) > 2.0:
            return 0.0
        recent = [t for t in timestamps if (now - t) <= 1.5]
        if len(recent) >= 2:
            dt = recent[-1] - recent[0]
            if dt > 0:
                return (len(recent) - 1) / dt
        return 0.0

    @property
    def current_freq(self) -> float:
        """Calculates instantaneous reception frequency (Hz) over recent sliding window."""
        freq = self._windowed_freq(self.timestamps)
        if freq > 0:
            return freq
        if self.timestamps and (time.time() - self.timestamps[-1]) <= 2.0 and self.intervals:
            avg_ms = sum(list(self.intervals)[-10:]) / min(len(self.intervals), 10)
            if avg_ms > 0:
                return 1000.0 / avg_ms
        return 0.0

    @property
    def logical_freq(self) -> float:
        """Calculates logical (reassembled) update frequency (Hz) for sliced streams."""
        return self._windowed_freq(self.logical_timestamps)

    @property
    def display_freq(self) -> float:
        """Frequency to show the user: logical update rate if recorded, else raw current_freq."""
        return self.logical_freq if self.logical_timestamps else self.current_freq

    @property
    def avg_interval_ms(self) -> float:
        """Average arrival delay between consecutive packets (ms)."""
        return (sum(self.intervals) / len(self.intervals)) if self.intervals else 0.0

    @property
    def jitter_ms(self) -> float:
        """Arrival jitter variation (ms)."""
        if not self.intervals:
            return 0.0
        return abs(max(self.intervals) - min(self.intervals)) / 2.0

    @property
    def bandwidth_kb_s(self) -> float:
        """Instantaneous bandwidth throughput (KB/s)."""
        now = time.time()
        recent_count = len([t for t in self.timestamps if (now - t) <= 1.0])
        return (recent_count * self.last_size) / 1024.0

    def reset(self) -> None:
        """Resets all counters and historical metrics."""
        self.count = 0
        self.bytes_total = 0
        self.timestamps.clear()
        self.intervals.clear()
        self.logical_timestamps.clear()
        self.last_timestamp = 0.0
        self.last_size = 0
