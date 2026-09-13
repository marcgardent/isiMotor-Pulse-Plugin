"""
Base binary decoding utilities.
"""


def _decode_string(raw_bytes: bytes) -> str:
    """Decodes null-terminated C string."""
    return raw_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
