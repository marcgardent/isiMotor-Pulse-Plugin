# isimotor-pulse-types

Shared, dependency-free dataclasses describing the isiMotor Pulse packet formats
(telemetry, scoring, graphics, weather, force-feedback, ECU, LMU extensions, commands,
system events, and the common packet header/vector types).

This package exists so that both
[`isimotor-pulse-client`](../isimotor-pulse-client) (binary decoder, transport, state
store) and [`isimotor-pulse-manager`](../isimotor-pulse-manager) (Textual UI, telemetry
extractors) can depend on the same packet type definitions without either one pulling in
the other's runtime dependencies.

## Usage

```python
from isimotor_pulse_types import TelemInfo, RawUdpHeader, CompactScoring
```

See `isimotor-pulse-client`'s README for the full UDP protocol documentation — this
package only holds the Python data model, not the binary decoder.
