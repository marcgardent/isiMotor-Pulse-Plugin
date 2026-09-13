"""
Graphics rendering and camera viewpoint packet decoder.

Wire format: FlatBuffers (schemas/graphics.fbs), one message per packet
type 10 (its own ZeroMQ port), no header/framing.
"""

from isimotor_rawudp_types import Graphics, TelemVect3

from .fbs_codec import decode_graphics_fbs


def decode_graphics(data: bytes, offset: int = 0) -> Graphics | None:
    """Decodes a Graphics FlatBuffer payload (packet type 10)."""
    fields = decode_graphics_fbs(data[offset:] if offset else data)
    if fields is None:
        return None

    cam_pos = TelemVect3(*fields["cam_pos"])
    o0, o1, o2 = fields["cam_ori"]
    cam_ori = (TelemVect3(*o0), TelemVect3(*o1), TelemVect3(*o2))

    return Graphics(
        cam_pos=cam_pos,
        cam_ori=cam_ori,
        ambient_rgb=fields["ambient_rgb"],
        slot_id=fields["slot_id"],
        camera_type=fields["camera_type"],
    )
