"""
Telemetry packet row extractor and presentation builder for TelemInfo.
"""

from typing import Any

from isimotor_rawudp_client.models import TelemInfo

from ..engine.stats import PacketStats
from .base import BaseExtractor, TableRow, format_value, model_to_clean_dict


def extract_telemetry_rows(t: TelemInfo | None, st: PacketStats | None = None) -> list[TableRow]:
    """Returns list of (key, raw_value, formatted_string, description) for TelemInfo packet."""
    rows: list[TableRow] = []

    # Channel / Stream Diagnostics
    if st is not None:
        freq_str = f"[bold #e3b341]{st.current_freq:5.1f} Hz[/]"
        delay_str = f"{st.avg_interval_ms:4.1f} ms" if st.intervals else "-"
        jitter_str = f"±{st.jitter_ms:3.1f} ms" if st.intervals else "-"
        rows.extend(
            [
                (
                    "_channel.frequency_hz",
                    st.current_freq,
                    freq_str,
                    "Real-time reception frequency of TelemInfo packet stream",
                ),
                (
                    "_channel.packets_count",
                    st.count,
                    f"{st.count:,}",
                    "Total TelemInfo packets received on this channel",
                ),
                (
                    "_channel.avg_delay_ms",
                    st.avg_interval_ms,
                    delay_str,
                    "Average arrival delay between consecutive TelemInfo packets",
                ),
                ("_channel.jitter_ms", st.jitter_ms, jitter_str, "TelemInfo packet arrival jitter variation"),
                (
                    "_channel.bandwidth_kb_s",
                    st.bandwidth_kb_s,
                    f"{st.bandwidth_kb_s:5.1f} KB/s",
                    "Instantaneous bandwidth for TelemInfo stream",
                ),
            ]
        )

    if t is None:
        rows.append(
            (
                "status",
                "Waiting for packets",
                "[dim]No TelemInfo packet received yet[/dim]",
                "Start game or launch native isi_mock_host",
            )
        )
        return rows

    rows.extend(
        [
            # Session & Identity
            ("slot_id", t.slot_id, format_value(t.slot_id), "Player vehicle slot index in session / multiplayer"),
            ("delta_time", t.delta_time, f"{t.delta_time:.4f} s", "Time since last physics update (seconds)"),
            ("elapsed_time", t.elapsed_time, f"{t.elapsed_time:.3f} s", "Total game session elapsed time (seconds)"),
            ("lap_number", t.lap_number, format_value(t.lap_number), "Current lap number"),
            (
                "lap_start_et",
                t.lap_start_et,
                f"{t.lap_start_et:.3f} s",
                "Session time when current lap began (seconds)",
            ),
            ("vehicle_name", t.vehicle_name, format_value(t.vehicle_name), "Vehicle / car model identification string"),
            ("track_name", t.track_name, format_value(t.track_name), "Track / circuit identification string"),
            # Kinematics & Position
            ("pos.x", t.pos.x, f"{t.pos.x:.3f} m", "World X position (meters, left-handed)"),
            ("pos.y", t.pos.y, f"{t.pos.y:.3f} m", "World Y position / elevation (meters, +y up)"),
            ("pos.z", t.pos.z, f"{t.pos.z:.3f} m", "World Z position (meters, +z rear)"),
            ("local_vel.x", t.local_vel.x, f"{t.local_vel.x:.3f} m/s", "Local lateral velocity (+x left, m/s)"),
            ("local_vel.y", t.local_vel.y, f"{t.local_vel.y:.3f} m/s", "Local vertical velocity (+y up, m/s)"),
            ("local_vel.z", t.local_vel.z, f"{t.local_vel.z:.3f} m/s", "Local longitudinal velocity (+z rear, m/s)"),
            ("speed_mps", t.speed_mps, f"{t.speed_mps:.3f} m/s", "Calculated 3D absolute vehicle speed (m/s)"),
            ("speed_kmh", t.speed_kmh, f"{t.speed_kmh:.2f} km/h", "Calculated 3D absolute vehicle speed (km/h)"),
            (
                "forward_speed_mps",
                t.forward_speed_mps,
                f"{t.forward_speed_mps:.3f} m/s",
                "Forward speed along vehicle axis (ISO +x = isiMotor -z, m/s)",
            ),
            (
                "forward_speed_kmh",
                t.forward_speed_kmh,
                f"{t.forward_speed_kmh:.2f} km/h",
                "Forward speed along vehicle axis (km/h)",
            ),
            ("local_accel.x", t.local_accel.x, f"{t.local_accel.x:.3f} m/s²", "Local lateral acceleration (m/s²)"),
            ("local_accel.y", t.local_accel.y, f"{t.local_accel.y:.3f} m/s²", "Local vertical acceleration (m/s²)"),
            ("local_accel.z", t.local_accel.z, f"{t.local_accel.z:.3f} m/s²", "Local longitudinal acceleration (m/s²)"),
            ("local_rot.x", t.local_rot.x, f"{t.local_rot.x:.4f} rad/s", "Pitch rate (+x pitch up, rad/s)"),
            ("local_rot.y", t.local_rot.y, f"{t.local_rot.y:.4f} rad/s", "Yaw rate (+y yaw right, rad/s)"),
            ("local_rot.z", t.local_rot.z, f"{t.local_rot.z:.4f} rad/s", "Roll rate (+z roll right, rad/s)"),
            (
                "local_rot_accel.x",
                t.local_rot_accel.x,
                f"{t.local_rot_accel.x:.4f} rad/s²",
                "Pitch angular acceleration (rad/s²)",
            ),
            (
                "local_rot_accel.y",
                t.local_rot_accel.y,
                f"{t.local_rot_accel.y:.4f} rad/s²",
                "Yaw angular acceleration (rad/s²)",
            ),
            (
                "local_rot_accel.z",
                t.local_rot_accel.z,
                f"{t.local_rot_accel.z:.4f} rad/s²",
                "Roll angular acceleration (rad/s²)",
            ),
            (
                "ori[0]",
                t.ori[0].as_tuple(),
                format_value(t.ori[0].as_tuple()),
                "Orientation matrix row 0 (lateral axis vector)",
            ),
            (
                "ori[1]",
                t.ori[1].as_tuple(),
                format_value(t.ori[1].as_tuple()),
                "Orientation matrix row 1 (vertical axis vector)",
            ),
            (
                "ori[2]",
                t.ori[2].as_tuple(),
                format_value(t.ori[2].as_tuple()),
                "Orientation matrix row 2 (longitudinal axis vector)",
            ),
            # Engine & Drivetrain
            ("gear", t.gear, format_value(t.gear), "Transmission gear index (-1=Reverse, 0=Neutral, 1+=Forward)"),
            (
                "gear_str",
                t.gear_str,
                f"[bold #f1e05a]{t.gear_str}[/]",
                "Human-readable gear label ('R', 'N', '1', '2'...)",
            ),
            ("engine_rpm", t.engine_rpm, f"{t.engine_rpm:.1f} RPM", "Engine crankshaft rotational speed (RPM)"),
            ("engine_max_rpm", t.engine_max_rpm, f"{t.engine_max_rpm:.1f} RPM", "Engine redline maximum limit (RPM)"),
            (
                "engine_water_temp",
                t.engine_water_temp,
                f"{t.engine_water_temp:.1f} °C",
                "Engine coolant / water temperature",
            ),
            ("engine_oil_temp", t.engine_oil_temp, f"{t.engine_oil_temp:.1f} °C", "Engine lubricant oil temperature"),
            ("clutch_rpm", t.clutch_rpm, f"{t.clutch_rpm:.1f} RPM", "Clutch input shaft speed (RPM)"),
            # Driver Controls & Inputs
            (
                "unfiltered_throttle",
                t.unfiltered_throttle,
                f"{t.unfiltered_throttle * 100:.1f} %",
                "Raw throttle pedal position (0-100%)",
            ),
            (
                "unfiltered_brake",
                t.unfiltered_brake,
                f"{t.unfiltered_brake * 100:.1f} %",
                "Raw brake pedal position (0-100%)",
            ),
            (
                "unfiltered_steering",
                t.unfiltered_steering,
                f"{t.unfiltered_steering * 100:+.1f} %",
                "Raw steering wheel angle (-100% to +100%)",
            ),
            (
                "unfiltered_clutch",
                t.unfiltered_clutch,
                f"{t.unfiltered_clutch * 100:.1f} %",
                "Raw clutch pedal position (0-100%)",
            ),
            (
                "filtered_throttle",
                t.filtered_throttle,
                f"{t.filtered_throttle * 100:.1f} %",
                "Filtered throttle input sent to physics (0-100%)",
            ),
            (
                "filtered_brake",
                t.filtered_brake,
                f"{t.filtered_brake * 100:.1f} %",
                "Filtered brake input sent to physics (0-100%)",
            ),
            (
                "filtered_steering",
                t.filtered_steering,
                f"{t.filtered_steering * 100:+.1f} %",
                "Filtered steering input sent to physics (-100% to +100%)",
            ),
            (
                "filtered_clutch",
                t.filtered_clutch,
                f"{t.filtered_clutch * 100:.1f} %",
                "Filtered clutch input sent to physics (0-100%)",
            ),
            (
                "steering_shaft_torque",
                t.steering_shaft_torque,
                f"{t.steering_shaft_torque:+.3f} N·m",
                "Direct force-feedback steering shaft torque (N·m)",
            ),
            # Aerodynamics & Aero Surfaces
            (
                "front_wing_height",
                t.front_wing_height,
                f"{t.front_wing_height * 1000:.1f} mm",
                "Front wing ground ride height",
            ),
            (
                "front_ride_height",
                t.front_ride_height,
                f"{t.front_ride_height * 1000:.1f} mm",
                "Front chassis ground clearance",
            ),
            (
                "rear_ride_height",
                t.rear_ride_height,
                f"{t.rear_ride_height * 1000:.1f} mm",
                "Rear chassis ground clearance",
            ),
            (
                "drag",
                t.drag,
                f"{t.drag:.1f} N",
                "Total aerodynamic drag force opposing vehicle motion",
            ),
            (
                "front_downforce",
                t.front_downforce,
                f"{t.front_downforce:.1f} N",
                "Total aerodynamic downforce over front axle",
            ),
            (
                "rear_downforce",
                t.rear_downforce,
                f"{t.rear_downforce:.1f} N",
                "Total aerodynamic downforce over rear axle",
            ),
            # Vehicle Status & Health
            ("fuel", t.fuel, f"{t.fuel:.2f} L", "Current onboard fuel volume remaining"),
            ("fuel_capacity", t.fuel_capacity, f"{t.fuel_capacity:.1f} L", "Maximum fuel tank capacity"),
            (
                "overheating",
                bool(t.overheating),
                format_value(bool(t.overheating)),
                "Engine temperature critically high warning",
            ),
            (
                "dent_severity",
                list(t.dent_severity),
                format_value(list(t.dent_severity)),
                "Bodywork dent deformation scale (8 sectors, 0-255)",
            ),
        ]
    )

    # 4 Wheels Diagnostics
    wheel_specs = [(0, "fl", "Front Left"), (1, "fr", "Front Right"), (2, "rl", "Rear Left"), (3, "rr", "Rear Right")]
    for idx, code, lbl in wheel_specs:
        w = t.wheels[idx]
        rows.extend(
            [
                (
                    f"wheels.{code}.rotation",
                    w.rotation,
                    f"{w.rotation:.2f} rad/s",
                    f"{lbl} wheel rotational speed (rad/s)",
                ),
                (
                    f"wheels.{code}.suspension_deflection",
                    w.suspension_deflection,
                    f"{w.suspension_deflection * 1000:.2f} mm",
                    f"{lbl} suspension spring travel / deflection (mm)",
                ),
                (
                    f"wheels.{code}.ride_height",
                    w.ride_height,
                    f"{w.ride_height * 1000:.2f} mm",
                    f"{lbl} local under-floor ride height (mm)",
                ),
                (
                    f"wheels.{code}.tire_load",
                    w.tire_load,
                    f"{w.tire_load:.1f} N",
                    f"{lbl} vertical tire normal contact load (N)",
                ),
                (
                    f"wheels.{code}.lateral_force",
                    w.lateral_force,
                    f"{w.lateral_force:+.1f} N",
                    f"{lbl} cornering lateral friction force (N)",
                ),
                (
                    f"wheels.{code}.longitudinal_force",
                    w.longitudinal_force,
                    f"{w.longitudinal_force:+.1f} N",
                    f"{lbl} tractive / braking longitudinal force (N)",
                ),
                (
                    f"wheels.{code}.brake_temp",
                    w.brake_temp,
                    f"{w.brake_temp:.1f} °C",
                    f"{lbl} brake rotor / disc temperature (°C)",
                ),
                (
                    f"wheels.{code}.tire_pressure",
                    w.pressure,
                    f"{w.pressure:.1f} kPa",
                    f"{lbl} internal pneumatic tire pressure (kPa)",
                ),
                (
                    f"wheels.{code}.temperature",
                    w.temperature,
                    f"L:{w.temperature[0]:.1f}  M:{w.temperature[1]:.1f}  R:{w.temperature[2]:.1f} °C",
                    f"{lbl} tire carcass temperature: Left / Middle / Right (°C)",
                ),
                (
                    f"wheels.{code}.wear",
                    w.wear,
                    f"{w.wear * 100:.1f} %",
                    f"{lbl} tire tread remaining (100%=New, 0%=Worn)",
                ),
                (
                    f"wheels.{code}.grip_fraction",
                    w.grip_fraction,
                    f"{w.grip_fraction * 100:.1f} %",
                    f"{lbl} available tire adhesion / grip fraction remaining",
                ),
                (
                    f"wheels.{code}.camber",
                    w.camber,
                    f"{w.camber:.3f} rad",
                    f"{lbl} dynamic wheel camber angle to road (radians)",
                ),
                (
                    f"wheels.{code}.vertical_tire_deflection",
                    w.vertical_tire_deflection,
                    f"{w.vertical_tire_deflection * 1000:.2f} mm",
                    f"{lbl} vertical tire carcass compression (mm)",
                ),
            ]
        )

    return rows


class TelemetryExtractor(BaseExtractor):
    """Telemetry packet presentation extractor."""

    def extract(self, t: TelemInfo | None, st: PacketStats | None = None) -> list[TableRow]:
        return extract_telemetry_rows(t, st)

    def to_dict(self, t: TelemInfo | None, st: PacketStats | None = None) -> dict[str, Any]:
        if t is None:
            return {"status": "No TelemInfo packet received yet"}
        d = model_to_clean_dict(t)
        if st is not None:
            d["_channel_diagnostics"] = {
                "frequency_hz": round(st.current_freq, 2),
                "packets_count": st.count,
                "avg_delay_ms": round(st.avg_interval_ms, 2),
                "jitter_ms": round(st.jitter_ms, 2),
                "bandwidth_kb_s": round(st.bandwidth_kb_s, 2),
            }
        d["_computed"] = {
            "speed_kmh": t.speed_kmh,
            "forward_speed_kmh": t.forward_speed_kmh,
            "gear_str": t.gear_str,
        }
        return d
