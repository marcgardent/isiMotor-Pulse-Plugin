"""
Scoring, timing, and multi-vehicle leaderboard decoders.

CompactScoring (packet type 2) and FullScoringSession (packet type 4,
including all its embedded VehicleScoring records) are FlatBuffers with no
RawUdpHeader/chunking: the ZMQ message IS the FlatBuffer, decoded directly.
"""

from isimotor_rawudp_types import CompactScoring, FullScoringSession

from .fbs_codec import decode_compact_scoring_fbs, decode_full_scoring_fbs


def decode_compact_scoring(data: bytes, offset: int = 0) -> CompactScoring | None:
    """Decodes a CompactScoring FlatBuffer payload (packet type 2)."""
    fields = decode_compact_scoring_fbs(data[offset:] if offset else data)
    if fields is None:
        return None
    return CompactScoring(**fields)


def decode_full_scoring(data: bytes, offset: int = 0) -> FullScoringSession | None:
    """Decodes a FullScoringSession FlatBuffer payload (packet type 4), including all embedded vehicles."""
    return decode_full_scoring_fbs(data[offset:] if offset else data)
