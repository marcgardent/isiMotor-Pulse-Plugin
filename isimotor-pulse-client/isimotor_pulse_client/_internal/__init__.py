"""
Internal implementation details of isimotor_pulse_client.

Everything under this package is plumbing (transport, decoding, dispatching,
state caching, and the single-packet-type client classes) composed by the
public API (`IsiMotorClient`, the `*SinglePacketClientFactory` classes, and
the top-level `decode_*`/`encode_*` functions). No compatibility guarantee is
made for anything imported from here directly - import from
`isimotor_pulse_client` instead.
"""
