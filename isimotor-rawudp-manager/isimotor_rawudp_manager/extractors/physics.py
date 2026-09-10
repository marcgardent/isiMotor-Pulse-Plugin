"""
Extended state, driving aids, physics multipliers & damage row extractor.
"""

from typing import Any

from isimotor_rawudp_types import ExtendedState

from ..engine.stats import PacketStats
from .base import BaseExtractor, TableRow, format_value, model_to_clean_dict


def extract_physics_rows(ext: ExtendedState | None, st: PacketStats | None = None) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for ExtendedState packet."""
    rows: list[TableRow] = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                (
                    "_channel.frequency_hz",
                    st.current_freq,
                    freq_str,
                    "Real-time reception frequency of ExtendedState stream (5Hz)",
                ),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total ExtendedState packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between ExtendedState packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for ExtendedState stream",
                ),
            ]
        )

    if ext is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No ExtendedState packet received yet[/dim]",
                "Driving aids, multipliers & accumulated impact damage",
            )
        )
        return rows

    p = ext.physics
    rows.extend(
        [
            # Driving Aids
            (
                "physics.traction_control",
                p.traction_control_str,
                f"[bold #58a6ff]{p.traction_control_str}[/] [dim]({p.traction_control})[/dim]",
                "Traction Control assistance level (0=Off, 1=Low, 2=Med, 3=High)",
            ),
            (
                "physics.anti_lock_brakes",
                p.anti_lock_brakes_str,
                f"[bold #58a6ff]{p.anti_lock_brakes_str}[/] [dim]({p.anti_lock_brakes})[/dim]",
                "ABS assistance level (0=Off, 1=Low, 2=High)",
            ),
            (
                "physics.stability_control",
                p.stability_control_str,
                f"[bold #58a6ff]{p.stability_control_str}[/] [dim]({p.stability_control})[/dim]",
                "Electronic Stability Control (ESC) level",
            ),
            (
                "physics.auto_shift",
                p.auto_shift_str,
                f"[bold #58a6ff]{p.auto_shift_str}[/] [dim]({p.auto_shift})[/dim]",
                "Automatic transmission shifting mode",
            ),
            (
                "physics.auto_clutch",
                bool(p.auto_clutch),
                format_value(bool(p.auto_clutch)),
                "Automatic clutch aid enabled",
            ),
            ("physics.auto_blip", bool(p.auto_blip), format_value(bool(p.auto_blip)), "Throttle blip on downshift aid"),
            ("physics.auto_lift", bool(p.auto_lift), format_value(bool(p.auto_lift)), "Throttle lift on upshift aid"),
            (
                "physics.opposite_lock",
                bool(p.opposite_lock),
                format_value(bool(p.opposite_lock)),
                "Counter-steering / opposite lock aid",
            ),
            ("physics.steering_help", p.steering_help, format_value(p.steering_help), "Steering help assist (0-3)"),
            ("physics.braking_help", p.braking_help, format_value(p.braking_help), "Braking help assist (0-2)"),
            (
                "physics.spin_recovery",
                bool(p.spin_recovery),
                format_value(bool(p.spin_recovery)),
                "Spin recovery assist",
            ),
            (
                "physics.auto_pit",
                bool(p.auto_pit),
                format_value(bool(p.auto_pit)),
                "Auto pit drive / speed control aid",
            ),
            (
                "physics.invulnerable",
                bool(p.invulnerable),
                format_value(bool(p.invulnerable)),
                "Invulnerability / no damage cheat active",
            ),
            (
                "physics.ai_control",
                bool(p.ai_control),
                format_value(bool(p.ai_control)),
                "AI driving active (0=Human player, 1=AI takeover)",
            ),
            # Multipliers
            ("physics.fuel_mult", p.fuel_mult, f"{p.fuel_mult}x", "Fuel consumption multiplier rate"),
            ("physics.tire_mult", p.tire_mult, f"{p.tire_mult}x", "Tire wear degradation rate multiplier"),
            (
                "physics.mech_fail",
                p.mech_fail,
                format_value(p.mech_fail),
                "Mechanical failures mode (0=Off, 1=Normal, 2=Time-scaled)",
            ),
            # Steering & Controls Sensitivity
            (
                "physics.speed_sensitive_steering",
                p.speed_sensitive_steering,
                format_value(p.speed_sensitive_steering),
                "Speed-sensitive steering attenuation (0.0 to 1.0)",
            ),
            (
                "physics.steer_ratio_speed",
                p.steer_ratio_speed,
                f"{p.steer_ratio_speed:.1f} m/s",
                "Speed below which steering lock expands",
            ),
            (
                "physics.manual_shift_override_time",
                p.manual_shift_override_time,
                f"{p.manual_shift_override_time:.2f} s",
                "Override timeout before auto-shift can resume",
            ),
            # Damage Tracking
            (
                "damage.max_impact_magnitude",
                ext.max_impact_magnitude,
                f"[bold {'#f85149' if ext.max_impact_magnitude > 5000 else '#e3b341'}]{ext.max_impact_magnitude:,.1f} N[/]",
                "Peak collision impact force recorded in current session",
            ),
            (
                "damage.accumulated_impact_magnitude",
                ext.accumulated_impact_magnitude,
                f"[bold {'#f85149' if ext.accumulated_impact_magnitude > 10000 else '#58a6ff'}]{ext.accumulated_impact_magnitude:,.1f} N·s[/]",
                "Cumulative crash impact damage energy",
            ),
            # Session Status
            (
                "session.in_realtime_fc",
                ext.in_realtime_fc,
                format_value(ext.in_realtime_fc),
                "Real-time cockpit driving mode flag",
            ),
            ("session.session_started", ext.session_started, format_value(ext.session_started), "Session started flag"),
            ("session.session_index", ext.session, format_value(ext.session), "Session type index"),
            (
                "session.pit_speed_limit",
                ext.current_pit_speed_limit_kmh,
                f"[bold #e3b341]{ext.current_pit_speed_limit_kmh:.1f} km/h[/] [dim]({ext.current_pit_speed_limit:.2f} m/s)[/dim]",
                "Speed limit enforced in pit lane",
            ),
        ]
    )

    return rows


class PhysicsExtractor(BaseExtractor):
    """Physics & driving aids presentation extractor."""

    def extract(self, ext: ExtendedState | None, st: PacketStats | None = None) -> list[TableRow]:
        return extract_physics_rows(ext, st)

    def to_dict(self, ext: ExtendedState | None, st: PacketStats | None = None) -> dict[str, Any]:
        if ext is None:
            return {"status": "No ExtendedState packet received yet"}
        d = model_to_clean_dict(ext)
        d["pit_speed_limit_kmh"] = ext.current_pit_speed_limit_kmh
        if st is not None:
            d["_channel_diagnostics"] = {
                "frequency_hz": round(st.current_freq, 2),
                "packets_count": st.count,
                "avg_delay_ms": round(st.avg_interval_ms, 2),
                "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
            }
        return d
