"""
Extended game state, physics options, and damage decoder.

Wire format: FlatBuffers (schemas/extended_state.fbs), one message per packet
type 8 (its own ZeroMQ port), no header/framing.
"""

from isimotor_pulse_types import ExtendedState, PhysicsOptions

from .fbs_codec import decode_extended_state_fbs


def decode_extended_state(data: bytes, offset: int = 0) -> ExtendedState | None:
    """Decodes an ExtendedState FlatBuffer payload (packet type 8)."""
    fields = decode_extended_state_fbs(data[offset:] if offset else data)
    if fields is None:
        return None
    physics = PhysicsOptions(**fields["physics"])
    return ExtendedState(
        physics=physics,
        max_impact_magnitude=fields["max_impact_magnitude"],
        accumulated_impact_magnitude=fields["accumulated_impact_magnitude"],
        in_realtime_fc=fields["in_realtime_fc"],
        session_started=fields["session_started"],
        session=fields["session"],
        current_pit_speed_limit=fields["current_pit_speed_limit"],
    )
