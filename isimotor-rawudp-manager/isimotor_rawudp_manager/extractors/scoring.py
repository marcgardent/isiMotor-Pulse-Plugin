"""
Scoring and multi-vehicle grid packet row extractor.
"""

from typing import Any

from isimotor_rawudp_client.models import CompactScoring, FullScoringSession

from ..engine.stats import PacketStats
from .base import BaseExtractor, TableRow, format_value, model_to_clean_dict


def extract_scoring_rows(
    s: CompactScoring | None,
    fs: FullScoringSession | None = None,
    st: PacketStats | None = None,
) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for CompactScoring and FullScoringSession streams."""
    rows: list[TableRow] = []

    # Channel / Stream Diagnostics
    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of Scoring stream"),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total Scoring packets received on this channel"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between consecutive Scoring packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for Scoring stream",
                ),
            ]
        )

    session_names = {
        0: "Test Day",
        1: "Practice 1",
        2: "Practice 2",
        3: "Practice 3",
        4: "Practice 4",
        5: "Qualifying 1",
        6: "Qualifying 2",
        7: "Qualifying 3",
        8: "Qualifying 4",
        9: "Warmup",
        10: "Race 1",
        11: "Race 2",
        12: "Race 3",
        13: "Race 4",
    }

    # 1. Full Multi-Car Grid Scoring (SIMP Type 4)
    if fs is not None:
        session_label = session_names.get(fs.session, f"Session({fs.session})")
        rows.extend(
            [
                (
                    "grid.track_name",
                    fs.track_name,
                    format_value(fs.track_name),
                    "Track / circuit identification string",
                ),
                ("grid.session_type", session_label, f"[bold #58a6ff]{session_label}[/]", "Current session type"),
                (
                    "grid.game_phase",
                    fs.game_phase_str,
                    f"[bold #3fb950]{fs.game_phase_str}[/]",
                    "Session game phase (Garage, Warmup, GreenFlag, FCY...)",
                ),
                ("grid.current_et", fs.current_et, f"{fs.current_et:.3f} s", "Session elapsed time"),
                ("grid.end_et", fs.end_et, f"{fs.end_et:.1f} s", "Session end elapsed time"),
                (
                    "grid.num_vehicles",
                    fs.num_vehicles,
                    f"[bold #f1e05a]{fs.num_vehicles}[/]",
                    "Active vehicles in session / grid",
                ),
                ("grid.ambient_temp", fs.ambient_temp, f"{fs.ambient_temp:.1f} °C", "Ambient air temperature"),
                ("grid.track_temp", fs.track_temp, f"{fs.track_temp:.1f} °C", "Track surface temperature"),
                ("grid.raining", fs.raining, f"{fs.raining * 100:.1f} %", "Rain intensity"),
                ("grid.dark_cloud", fs.dark_cloud, f"{fs.dark_cloud * 100:.1f} %", "Cloud cover darkness"),
            ]
        )

        # Leaderboard entries
        for rank, v in enumerate(fs.leaderboard, start=1):
            tag = f"car[{rank:02d}]"
            player_marker = " [bold #3fb950](PLAYER)[/]" if v.is_player else ""
            pit_str = f" [bold #f85149][PIT - {v.pit_state_str}][/]" if v.in_pits else ""
            gap_str = (
                f"+{v.time_behind_leader:.3f} s"
                if (v.time_behind_leader > 0 and rank > 1)
                else ("LEADER" if rank == 1 else "-")
            )
            best_lap_str = f"{v.best_lap_time:.3f} s" if v.best_lap_time > 0 else "-"
            last_lap_str = f"{v.last_lap_time:.3f} s" if v.last_lap_time > 0 else "-"

            rows.extend(
                [
                    (
                        f"{tag}.driver",
                        v.driver_name,
                        f"[bold]{v.driver_name}[/]{player_marker}{pit_str}",
                        f"P{v.place} | {v.vehicle_name} ({v.vehicle_class})",
                    ),
                    (f"{tag}.position", v.place, f"P{v.place}", "Current race position"),
                    (f"{tag}.laps", v.total_laps, format_value(v.total_laps), f"Completed laps | Sector {v.sector}"),
                    (f"{tag}.gap_leader", v.time_behind_leader, gap_str, "Gap to session leader (seconds)"),
                    (f"{tag}.best_lap", v.best_lap_time, best_lap_str, "Personal best lap time"),
                    (f"{tag}.last_lap", v.last_lap_time, last_lap_str, "Last completed lap time"),
                ]
            )
        return rows

    # 2. Compact Scoring Fallback (SIMP Type 2)
    if s is not None:
        session_label = session_names.get(s.session, f"Session({s.session})")
        rows.extend(
            [
                ("track_name", s.track_name, format_value(s.track_name), "Track / circuit identification string"),
                ("session", s.session, format_value(s.session), "Session numeric code"),
                ("session_type", session_label, f"[bold #58a6ff]{session_label}[/]", "Decoded session type"),
                ("current_et", s.current_et, f"{s.current_et:.3f} s", "Current session elapsed time (seconds)"),
                ("lap_dist", s.lap_dist, f"{s.lap_dist:.1f} m", "Total circuit lap distance (meters)"),
                ("max_laps", s.max_laps, format_value(s.max_laps), "Session scheduled lap limit"),
                ("in_realtime", s.in_realtime, format_value(s.in_realtime), "Real-time driving active state on track"),
                ("total_laps", s.total_laps, format_value(s.total_laps), "Completed lap count for player vehicle"),
                ("sector", s.sector, format_value(s.sector), "Current active sector"),
                (
                    "in_garage_stall",
                    s.in_garage_stall,
                    format_value(s.in_garage_stall),
                    "Vehicle inside pit garage stall flag",
                ),
                ("count_lap_flag", s.count_lap_flag, format_value(s.count_lap_flag), "Lap validity flag"),
                (
                    "cur_sector1",
                    s.cur_sector1,
                    f"{s.cur_sector1:.3f} s" if s.cur_sector1 > 0 else "[dim]-[/dim]",
                    "Current lap S1 split time",
                ),
                (
                    "cur_sector2",
                    s.cur_sector2,
                    f"{s.cur_sector2:.3f} s" if s.cur_sector2 > 0 else "[dim]-[/dim]",
                    "Current lap S2 split time",
                ),
                (
                    "last_lap_time",
                    s.last_lap_time,
                    f"[bold #3fb950]{s.last_lap_time:.3f} s[/]" if s.last_lap_time > 0 else "[dim]-[/dim]",
                    "Last lap total time",
                ),
                (
                    "best_lap_time",
                    s.best_lap_time,
                    f"[bold #bc8cff]{s.best_lap_time:.3f} s[/]" if s.best_lap_time > 0 else "[dim]-[/dim]",
                    "Personal best lap time",
                ),
            ]
        )
        return rows

    rows.append(
        (
            "status",
            "Waiting for packets",
            "[dim]No Scoring packet received yet[/dim]",
            "Scoring packets are streamed at 1-5 Hz",
        )
    )
    return rows


class ScoringExtractor(BaseExtractor):
    """Scoring packet presentation extractor."""

    def extract(
        self,
        s: CompactScoring | None,
        fs: FullScoringSession | None = None,
        st: PacketStats | None = None,
    ) -> list[TableRow]:
        return extract_scoring_rows(s, fs, st)

    def to_dict(
        self,
        s: CompactScoring | None,
        fs: FullScoringSession | None = None,
        st: PacketStats | None = None,
    ) -> dict[str, Any]:
        if fs is not None:
            d = model_to_clean_dict(fs)
            if st is not None:
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
            return d
        elif s is not None:
            d = model_to_clean_dict(s)
            if st is not None:
                d["_channel_diagnostics"] = {
                    "frequency_hz": round(st.current_freq, 2),
                    "packets_count": st.count,
                    "avg_delay_ms": round(st.avg_interval_ms, 2),
                    "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
                }
            return d
        return {"status": "No Scoring packet received yet"}
