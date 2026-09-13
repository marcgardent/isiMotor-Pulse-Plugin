"""
Force feedback packet row extractor and presentation builder.
"""

from typing import Any

from isimotor_pulse_types import ForceFeedback

from ..engine.stats import PacketStats
from .base import BaseExtractor, TableRow, format_value, model_to_clean_dict


def extract_ffb_rows(ffb: ForceFeedback | None, st: PacketStats | None = None) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for ForceFeedback packet."""
    rows: list[TableRow] = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.2f} ms" if st.intervals else "-"
        jitter_str = f"±{st.jitter_ms:3.2f} ms" if st.intervals else "-"
        rows.extend(
            [
                (
                    "_channel.frequency_hz",
                    st.current_freq,
                    freq_str,
                    "Real-time reception frequency of Ultra-High FFB stream (up to 400Hz)",
                ),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total ForceFeedback packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival interval (target: 2.5ms @ 400Hz)",
                ),
                ("_channel.jitter_ms", st.jitter_ms, jitter_str, "FFB packet arrival jitter variation"),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for FFB stream",
                ),
            ]
        )

    if ffb is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No ForceFeedback packet received yet[/dim]",
                "Direct steering shaft torque from physics engine",
            )
        )
        return rows

    # Visual force gauge
    pct = ffb.percentage
    abs_pct = abs(pct)
    bars_total = 20
    filled = int((abs_pct / 100.0) * bars_total)
    filled = min(bars_total, max(0, filled))
    bar_color = "#f85149" if abs_pct >= 98.0 else ("#e3b341" if abs_pct >= 85.0 else "#3fb950")
    gauge = f"[{bar_color}]{'█' * filled}[/][#30363d]{'░' * (bars_total - filled)}[/]"

    rows.extend(
        [
            (
                "ffb.force_value",
                ffb.force_value,
                f"[bold #58a6ff]{ffb.force_value:+.4f}[/]",
                "Normalized steering shaft torque (-1.0 to +1.0)",
            ),
            (
                "ffb.percentage",
                ffb.percentage,
                f"[bold {bar_color}]{pct:+6.1f} %[/] {gauge}",
                "Steering shaft torque percentage with real-time bar gauge",
            ),
            (
                "ffb.is_clipping",
                abs_pct >= 99.0,
                format_value(abs_pct >= 99.0),
                "True if force exceeds 99% causing direct-drive motor clipping",
            ),
        ]
    )

    return rows


class FeedbackExtractor(BaseExtractor):
    """Force Feedback packet presentation extractor."""

    def extract(self, ffb: ForceFeedback | None, st: PacketStats | None = None) -> list[TableRow]:
        return extract_ffb_rows(ffb, st)

    def to_dict(self, ffb: ForceFeedback | None, st: PacketStats | None = None) -> dict[str, Any]:
        if ffb is None:
            return {"status": "No ForceFeedback packet received yet"}
        d = model_to_clean_dict(ffb)
        d["percentage"] = ffb.percentage
        if st is not None:
            d["_channel_diagnostics"] = {
                "frequency_hz": round(st.current_freq, 2),
                "packets_count": st.count,
                "avg_delay_ms": round(st.avg_interval_ms, 2),
                "jitter_ms": round(st.jitter_ms, 2),
                "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
            }
        return d
