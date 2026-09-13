# isimotor-pulse-schemas (C++)

Generated C++ [FlatBuffers](https://flatbuffers.dev/) headers for the isiMotor Pulse wire
protocol (telemetry, scoring, graphics, weather, force-feedback, system events, inbound
commands) - the raw codec only, with no plugin/SDK integration code.

- [`fbs/`](fbs) - symlinks into the repo's [`schemas/*.fbs`](../../../schemas) (Git tracks
  symlinks natively; both directories always see the exact same schema content).
- `include/` - `*_generated.h` headers produced by `flatc --cpp --gen-object-api` from
  those schemas. Checked into the repo (regenerate with `make generate-schemas` from the
  repo root after editing a `.fbs` file - requires `flatc` installed locally).

## Usage

Header-only: add `include/` to your include path, plus the (header-only) upstream
[`flatbuffers`](https://github.com/google/flatbuffers) runtime headers, and include the
generated header(s) you need:

```cpp
#include "telemetry_generated.h"

const isimotor::fbs::TelemInfo* info = isimotor::fbs::GetTelemInfo(buf);
float rpm = info->engine_rpm();
```

[`isimotor-pulse-plugin`](../../../isimotor-pulse-plugin) (the actual game plugin - SDK
integration, ZeroMQ transport, build system) consumes this directory as an include path;
see its `CMakeLists.txt`.

## Versioning: FlatBuffers `file_identifier`

Each root table in the schemas declares a 4-character `file_identifier` ("magic value"),
FlatBuffers' native wire-format identification mechanism - embedded on every buffer
written by `Finish(root, "TELE")` etc. See [`schemas/`](../../../schemas) for the full
`root_type -> file_identifier` table.
