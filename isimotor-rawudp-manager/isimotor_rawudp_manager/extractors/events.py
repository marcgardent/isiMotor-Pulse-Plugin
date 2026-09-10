"""
System event packet row extractor.
"""

import time
from typing import Any

from isimotor_rawudp_types import SystemEvent

from ..engine.stats import PacketStats
from .base import BaseExtractor, TableRow, format_value, model_to_clean_dict


def extract_event_rows(
    ev: SystemEvent | None, st: PacketStats | None = None, event_time: float = 0.0
) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for SystemEvent packet."""
    rows: list[TableRow] = []

    if st is not None:
        rows.extend(
            [
                (
                    "_channel.packets_count",
                    st.count,
                    f"{st.count:,}",
                    "Total SystemEvent packets received on this channel",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for SystemEvent stream",
                ),
            ]
        )

    if ev is None:
        rows.append(
            (
                "status",
                "Waiting for events",
                "[dim]No SystemEvent packet received yet[/dim]",
                "System events are triggered on state transitions (Enter/Exit Realtime, Session start/end)",
            )
        )
        return rows

    ev_time_str = time.strftime("%H:%M:%S", time.localtime(event_time)) if event_time > 0 else "-"

    rows.extend(
        [
            (
                "event_id",
                ev.event_id,
                format_value(ev.event_id),
                "System event numeric code (1=EnterRealtime, 2=ExitRealtime, 3=StartSession, 4=EndSession)",
            ),
            ("name", ev.name, f"[bold #58a6ff]{ev.name}[/]", "Decoded human-readable event name"),
            (
                "in_realtime",
                ev.in_realtime,
                format_value(ev.in_realtime),
                "Whether event switches driving state to active real-time",
            ),
            ("timestamp", event_time, format_value(ev_time_str), "Local system receipt timestamp of the event"),
        ]
    )

    return rows


class EventExtractor(BaseExtractor):
    """System events presentation extractor."""

    def extract(self, ev: SystemEvent | None, st: PacketStats | None = None, event_time: float = 0.0) -> list[TableRow]:
        return extract_event_rows(ev, st, event_time)

    def to_dict(self, ev: SystemEvent | None, st: PacketStats | None = None, event_time: float = 0.0) -> dict[str, Any]:
        if ev is None:
            return {"status": "No SystemEvent packet received yet"}
        d = model_to_clean_dict(ev)
        d["name"] = ev.name
        d["timestamp"] = event_time
        if st is not None:
            d["_channel_diagnostics"] = {
                "packets_count": st.count,
                "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
            }
        return d
