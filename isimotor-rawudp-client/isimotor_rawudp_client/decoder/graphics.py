"""
Graphics rendering and camera viewpoint packet decoder.
"""

import struct

from isimotor_rawudp_types import Graphics, TelemVect3

from ..constants import GRAPHICS_SIZE, GRAPHICS_STRUCT


def decode_graphics(data: bytes, offset: int = 0) -> Graphics | None:
    """Decodes a 128-byte Graphics packet (Type 10)."""
    if len(data) - offset < GRAPHICS_SIZE:
        return None

    unpacked = struct.unpack_from(GRAPHICS_STRUCT, data, offset)
    cam_pos = TelemVect3(unpacked[0], unpacked[1], unpacked[2])
    cam_ori = (
        TelemVect3(unpacked[3], unpacked[4], unpacked[5]),
        TelemVect3(unpacked[6], unpacked[7], unpacked[8]),
        TelemVect3(unpacked[9], unpacked[10], unpacked[11]),
    )
    ambient_rgb = (unpacked[12], unpacked[13], unpacked[14])
    slot_id = unpacked[15]
    camera_type = unpacked[16]

    return Graphics(
        cam_pos=cam_pos,
        cam_ori=cam_ori,
        ambient_rgb=ambient_rgb,
        slot_id=slot_id,
        camera_type=camera_type,
    )
