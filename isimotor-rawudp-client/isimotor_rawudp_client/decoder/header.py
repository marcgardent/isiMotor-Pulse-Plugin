"""
Standardized SIMP packet header decoder and encoder.
"""

import struct

from ..constants import HEADER_SIZE, HEADER_STRUCT
from ..models import RawUdpHeader


def decode_header(data: bytes) -> RawUdpHeader | None:
    """Decodes 24-byte standardized SIMP protocol header."""
    if len(data) < HEADER_SIZE or not data.startswith(b"SIMP"):
        return None

    magic, ver, pkt_type, payload_sz, seq, session_et, chunk_idx, total_chunks, sub_id = struct.unpack_from(
        HEADER_STRUCT, data, 0
    )
    return RawUdpHeader(
        magic=magic,
        protocol_version=ver,
        packet_type=pkt_type,
        payload_size=payload_sz,
        sequence_number=seq,
        session_et=session_et,
        chunk_index=chunk_idx,
        total_chunks=total_chunks,
        sub_type_or_id=sub_id,
    )


def encode_header(
    packet_type: int,
    payload_size: int,
    sequence_number: int = 0,
    session_et: float = 0.0,
    chunk_index: int = 0,
    total_chunks: int = 1,
    sub_type_or_id: int = 0,
) -> bytes:
    """Encodes a standard 24-byte SIMP protocol header."""
    return struct.pack(
        HEADER_STRUCT,
        b"SIMP",
        1,  # protocol_version
        packet_type,
        payload_size,
        sequence_number,
        session_et,
        chunk_index,
        total_chunks,
        sub_type_or_id,
    )
