"""
Overall connection statistics and bandwidth extractor.
"""

import time
from typing import Any

from ..engine.telemetry_engine import TelemetryEngine
from .base import BaseExtractor, TableRow


def extract_stats_rows(engine: TelemetryEngine) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for overall stream statistics."""
    elapsed = time.time() - engine.start_time
    total_mb = engine.total_bytes / (1024.0 * 1024.0)

    rows: list[TableRow] = [
        (
            "connection.endpoint",
            f"{engine.host}:{engine.port}",
            f"[bold #58a6ff]{engine.host}:{engine.port}[/]",
            "UDP socket listening endpoint",
        ),
        (
            "connection.elapsed_time",
            elapsed,
            f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d} s",
            "Total benchmark session elapsed time",
        ),
        (
            "connection.total_packets",
            engine.total_packets,
            f"{engine.total_packets:,}",
            "Total packets received across all streams",
        ),
        (
            "connection.total_bytes",
            engine.total_bytes,
            f"{total_mb:.2f} MB ({engine.total_bytes:,} bytes)",
            "Total payload volume received",
        ),
    ]

    for st_name, st in engine.stats.items():
        prefix = st_name.split()[0].lower()
        rows.extend(
            [
                (f"{prefix}.packets_count", st.count, f"{st.count:,}", f"{st.name} total packets received"),
                (
                    f"{prefix}.frequency_hz",
                    st.display_freq,
                    f"[bold #e3b341]{st.display_freq:5.1f} Hz[/]",
                    f"{st.name} live packet frequency (1s window)",
                ),
                (
                    f"{prefix}.avg_delay_ms",
                    st.avg_interval_ms,
                    f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-",
                    f"{st.name} average inter-packet arrival delay",
                ),
                (
                    f"{prefix}.jitter_ms",
                    st.jitter_ms,
                    f"±{st.jitter_ms:3.1f} ms" if st.intervals else "-",
                    f"{st.name} packet jitter variation",
                ),
                (
                    f"{prefix}.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    f"{st.name} throughput bandwidth",
                ),
            ]
        )

    return rows


class StatsExtractor(BaseExtractor):
    """Overall engine and streams stats presentation extractor."""

    def extract(self, engine: TelemetryEngine) -> list[TableRow]:
        return extract_stats_rows(engine)

    def to_dict(self, engine: TelemetryEngine) -> dict[str, Any]:
        rows = extract_stats_rows(engine)
        return {k: raw for k, raw, _, _ in rows}
