"""
Weather packet row extractor and presentation builder.
"""

from typing import Any

from isimotor_rawudp_types import WeatherControl

from ..engine.stats import PacketStats
from .base import BaseExtractor, TableRow, model_to_clean_dict


def extract_weather_rows(w: WeatherControl | None, st: PacketStats | None = None) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for WeatherControl packet."""
    rows: list[TableRow] = []

    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                ("_channel.frequency_hz", st.current_freq, freq_str, "Real-time reception frequency of Weather stream"),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total Weather packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between Weather packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for Weather stream",
                ),
            ]
        )

    if w is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No Weather packet received yet[/dim]",
                "Environmental conditions streamed @ 1Hz",
            )
        )
        return rows

    rows.extend(
        [
            ("weather.et", w.et, f"{w.et:.3f} s", "Session time when weather takes effect"),
            (
                "weather.cloudiness",
                w.cloudiness,
                f"{w.cloudiness * 100:.1f} %",
                "General cloud cover (0% clear, 100% dark overcast)",
            ),
            (
                "weather.ambient_temp_c",
                w.ambient_temp_c,
                f"[bold #e3b341]{w.ambient_temp_c:.1f} °C[/]",
                "Ambient air temperature (Celsius)",
            ),
            (
                "weather.ambient_temp_k",
                w.ambient_temp_k,
                f"{w.ambient_temp_k:.2f} K",
                "Ambient air temperature (Kelvin)",
            ),
            (
                "weather.origin_raining",
                w.origin_raining,
                f"[bold {'#58a6ff' if w.origin_raining > 0.05 else '#3fb950'}]{w.origin_raining * 100:.1f} %[/]",
                "Instantaneous precipitation / rain rate at origin (0% dry, 100% storm)",
            ),
            (
                "weather.wind_max_speed",
                w.wind_max_speed,
                f"{w.wind_max_speed:.2f} m/s ({w.wind_max_speed * 3.6:.1f} km/h)",
                "Atmospheric maximum wind velocity",
            ),
            (
                "weather.apply_cloudiness_instantly",
                w.apply_cloudiness_instantly,
                "True" if w.apply_cloudiness_instantly else "False",
                "Flag indicating instant cloud cover transition",
            ),
        ]
    )

    return rows


class WeatherExtractor(BaseExtractor):
    """Weather packet presentation extractor."""

    def extract(self, w: WeatherControl | None, st: PacketStats | None = None) -> list[TableRow]:
        return extract_weather_rows(w, st)

    def to_dict(self, w: WeatherControl | None, st: PacketStats | None = None) -> dict[str, Any]:
        if w is None:
            return {"status": "No Weather packet received yet"}
        d = model_to_clean_dict(w)
        if st is not None:
            d["_channel_diagnostics"] = {
                "frequency_hz": round(st.current_freq, 2),
                "packets_count": st.count,
                "avg_delay_ms": round(st.avg_interval_ms, 2),
                "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
            }
        return d
