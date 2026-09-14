"""
High-frequency vehicle telemetry (TelemInfo) decoder.

TelemInfo (packet type 1) is a FlatBuffer (schemas/telemetry.fbs) with no
RawUdpHeader/chunking: the ZMQ message IS the FlatBuffer, decoded directly.
"""

from isimotor_pulse_types import TelemInfo

from .fbs_codec import decode_telemetry_fbs


def decode_telemetry(data: bytes, offset: int = 0) -> TelemInfo | None:
    """Decodes a TelemInfo FlatBuffer payload (packet type 1)."""
    return decode_telemetry_fbs(data[offset:] if offset else data)
