# isimotor-pulse-schemas (Rust)

Rust [FlatBuffers](https://flatbuffers.dev/) bindings for the isiMotor Pulse wire protocol
(telemetry, scoring, graphics, weather, force-feedback, system events, inbound commands),
generated at **build time** from [`fbs/*.fbs`](fbs) - symlinks into the repo's
[`schemas/*.fbs`](../../../schemas) (Git tracks symlinks natively, so there is nothing to keep
in sync: both directories always see the exact same schema content).

Ready off-the-shelf: `build.rs` uses the pure-Rust [`planus`](https://docs.rs/planus)
compiler, so `cargo build` generates the bindings on its own - no external `flatc`
binary, no C++ toolchain, no separate codegen step to run.

## Usage

Not published to crates.io - add it as a **Git dependency** pinned to a release tag,
which is also this repo's version source of truth (`make bump`/`verify-version`):

```toml
[dependencies]
isimotor-pulse-schemas = { git = "https://github.com/marcgardent/isiMotor-RawUDP-Plugin", tag = "v0.6.2" }
```

```rust
use isimotor_pulse_schemas::isimotor::fbs::{TelemInfoRef, SystemEventRef};

fn handle_telemetry(buf: &[u8]) -> Result<(), planus::Error> {
    let info: TelemInfoRef = planus::ReadAsRoot::read_as_root(buf)?;
    println!("speed: {:?} rpm: {:?}", info.local_vel()?, info.engine_rpm()?);
    Ok(())
}
```

See `isimotor-pulse-client`'s README for the full ZeroMQ transport documentation - this
crate only holds the generated wire types.

> **Windows note:** `fbs/*.fbs` are real Git symlinks. Git for Windows only checks them
> out as actual symlinks when symlink support is enabled (`git config --global
> core.symlinks true`, plus Developer Mode or an elevated shell) - otherwise they land as
> small text files containing the target path, and `build.rs` will fail to find the
> schemas. Enable that setting before cloning if you consume this crate on Windows.

## Versioning: FlatBuffers `file_identifier`

Each root table in the schemas declares a 4-character `file_identifier` ("magic value"),
FlatBuffers' native wire-format identification mechanism - embedded by the C++ plugin and
Python client on every buffer they write (`Finish(root, "TELE")`, etc.), see
[`schemas/`](../../../schemas) for the full `root_type -> file_identifier` table.

**Caveat:** `planus` (this crate's codegen/runtime) doesn't currently expose an API to
read or write that identifier - reading buffers produced by the C++/Python side works
unaffected (the identifier is just 4 bytes ahead of the root table that a `planus` reader
never looks at), but if you build an *encoder* in Rust and want the outgoing buffer to
carry the identifier too (e.g. for a strict verifier on the receiving end), you must
prepend/patch those 4 bytes yourself, or fall back to the official `flatbuffers` crate
+ `flatc`-generated bindings for that direction.
