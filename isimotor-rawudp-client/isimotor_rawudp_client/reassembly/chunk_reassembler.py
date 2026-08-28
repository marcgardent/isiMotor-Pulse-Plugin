"""
Multipart / sliced UDP packet chunk reassembler.
Handles SIMP protocol chunk joining and stale chunk eviction.
"""

from typing import Optional, Dict, Tuple, Union, Any
from ..constants import HEADER_SIZE, PKT_TYPE_FULL_SCORING, PKT_TYPE_TRACK_RULES
from ..models import FullScoringSession, TrackRulesSession
from ..decoder.header import decode_header
from ..decoder.scoring import decode_full_scoring
from ..decoder.rules import decode_track_rules

ReassembledSession = Union[FullScoringSession, TrackRulesSession]


class ChunkReassembler:
    """
    Thread-safe buffer for reassembling multi-chunk SIMP packets (e.g. Type 4 Full Scoring & Type 5 Track Rules).
    """

    def __init__(self, timeout_seconds: float = 1.0, cleanup_interval_seconds: float = 0.5) -> None:
        self.timeout_seconds = timeout_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._buffers: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self._last_cleanup: float = 0.0

    def process(self, data: bytes, now: float) -> Optional[ReassembledSession]:
        """
        Processes a raw UDP frame. If it is a multipart chunk, buffers it and returns
        the decoded fully reassembled session when all chunks have arrived.
        If it is a single-chunk packet, decodes and returns it directly.
        Returns None if chunk is buffered or packet is not a chunked session packet.
        """
        self.cleanup_stale(now)

        if len(data) < HEADER_SIZE:
            return None

        hdr = decode_header(data)
        if not hdr:
            return None

        payload = data[HEADER_SIZE : HEADER_SIZE + hdr.payload_size]

        # Single-chunk packet
        if hdr.total_chunks == 1:
            if hdr.packet_type == PKT_TYPE_FULL_SCORING:
                return decode_full_scoring(payload)
            elif hdr.packet_type == PKT_TYPE_TRACK_RULES:
                return decode_track_rules(payload)
            return None

        # Multi-chunk packet
        key = (hdr.packet_type, hdr.sequence_number)
        if key not in self._buffers:
            self._buffers[key] = {
                "total_chunks": hdr.total_chunks,
                "chunks": {},
                "timestamp": now,
            }

        buf = self._buffers[key]
        buf["chunks"][hdr.chunk_index] = payload

        # Check if all chunks received
        if len(buf["chunks"]) == buf["total_chunks"]:
            ordered_slices = [
                buf["chunks"][i]
                for i in range(buf["total_chunks"])
                if i in buf["chunks"]
            ]
            del self._buffers[key]
            assembled_payload = b"".join(ordered_slices)

            if hdr.packet_type == PKT_TYPE_FULL_SCORING:
                return decode_full_scoring(assembled_payload)
            elif hdr.packet_type == PKT_TYPE_TRACK_RULES:
                return decode_track_rules(assembled_payload)

        return None

    def cleanup_stale(self, now: float) -> None:
        """Prunes incomplete multipart frames older than timeout."""
        if now - self._last_cleanup < self.cleanup_interval_seconds:
            return
        self._last_cleanup = now
        stale_keys = [
            k
            for k, v in self._buffers.items()
            if now - v.get("timestamp", 0) > self.timeout_seconds
        ]
        for k in stale_keys:
            del self._buffers[k]

    def reset(self) -> None:
        """Clears all pending reassembly buffers."""
        self._buffers.clear()
        self._last_cleanup = 0.0
