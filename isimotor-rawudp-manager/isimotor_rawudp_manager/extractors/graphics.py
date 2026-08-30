"""
Graphics & camera viewpoints packet row extractor.
"""

from typing import Any

from isimotor_rawudp_client.models import Graphics

from ..engine.stats import PacketStats
from .base import BaseExtractor, TableRow, format_value, model_to_clean_dict


def extract_graphics_rows(gfx: Graphics | None, st: PacketStats | None = None) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for Graphics packet."""
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
                    "Real-time reception frequency of Graphics stream (60-100Hz)",
                ),
                ("_channel.packets_count", st.count, f"{st.count:,}", "Total Graphics packets received"),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between Graphics packets",
                ),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for Graphics stream",
                ),
            ]
        )

    if gfx is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No Graphics packet received yet[/dim]",
                "Camera 3D position, orientation & ambient lighting",
            )
        )
        return rows

    rows.extend(
        [
            (
                "camera.type",
                gfx.camera_type_str,
                f"[bold #58a6ff]{gfx.camera_type_str}[/] [dim](id: {gfx.camera_type})[/dim]",
                "Active camera perspective viewpoint",
            ),
            (
                "camera.is_cockpit",
                gfx.is_cockpit_view,
                format_value(gfx.is_cockpit_view),
                "True if active camera is inside driver cockpit",
            ),
            (
                "camera.slot_id",
                gfx.slot_id,
                format_value(gfx.slot_id),
                "Vehicle slot index currently tracked/viewed by camera (-1 = none)",
            ),
            (
                "camera.pos",
                gfx.cam_pos.as_tuple(),
                f"X:{gfx.cam_pos.x:8.2f}  Y:{gfx.cam_pos.y:8.2f}  Z:{gfx.cam_pos.z:8.2f} m",
                "World 3D coordinates of camera viewpoint",
            ),
            (
                "ambient.rgb",
                gfx.ambient_rgb,
                f"R:{gfx.ambient_rgb[0]:.3f}  G:{gfx.ambient_rgb[1]:.3f}  B:{gfx.ambient_rgb[2]:.3f}",
                "Track ambient environment light RGB intensity",
            ),
            (
                "camera.ori_matrix[0]",
                gfx.cam_ori[0].as_tuple(),
                format_value(gfx.cam_ori[0].as_tuple()),
                "Camera orientation matrix Row 0 (Pitch/Yaw/Roll)",
            ),
            (
                "camera.ori_matrix[1]",
                gfx.cam_ori[1].as_tuple(),
                format_value(gfx.cam_ori[1].as_tuple()),
                "Camera orientation matrix Row 1",
            ),
            (
                "camera.ori_matrix[2]",
                gfx.cam_ori[2].as_tuple(),
                format_value(gfx.cam_ori[2].as_tuple()),
                "Camera orientation matrix Row 2",
            ),
        ]
    )

    return rows


class GraphicsExtractor(BaseExtractor):
    """Graphics packet presentation extractor."""

    def extract(self, gfx: Graphics | None, st: PacketStats | None = None) -> list[TableRow]:
        return extract_graphics_rows(gfx, st)

    def to_dict(self, gfx: Graphics | None, st: PacketStats | None = None) -> dict[str, Any]:
        if gfx is None:
            return {"status": "No Graphics packet received yet"}
        d = model_to_clean_dict(gfx)
        d["camera_type_str"] = gfx.camera_type_str
        d["is_cockpit_view"] = gfx.is_cockpit_view
        if st is not None:
            d["_channel_diagnostics"] = {
                "frequency_hz": round(st.current_freq, 2),
                "packets_count": st.count,
                "avg_delay_ms": round(st.avg_interval_ms, 2),
                "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
            }
        return d
