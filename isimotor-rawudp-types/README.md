# isimotor-rawudp-types

Shared, dependency-free dataclasses describing the isiMotor RawUDP packet formats
(telemetry, scoring, graphics, weather, force-feedback, ECU, LMU extensions, commands,
system events, and the common packet header/vector types).

This package exists so that both
[`isimotor-rawudp-client`](../isimotor-rawudp-client) (binary decoder, transport, state
store) and [`isimotor-rawudp-manager`](../isimotor-rawudp-manager) (Textual UI, telemetry
extractors) can depend on the same packet type definitions without either one pulling in
the other's runtime dependencies.

## Usage

```python
from isimotor_rawudp_types import TelemInfo, RawUdpHeader, CompactScoring
```

See `isimotor-rawudp-client`'s README for the full UDP protocol documentation — this
package only holds the Python data model, not the binary decoder.
