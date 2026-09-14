# isimotor-pulse-client (Rust)

Typed ZeroMQ clients for the isiMotor Pulse wire protocol - one dedicated client
type per outbound packet type, decoding straight into the
[`isimotor-pulse-schemas`](../isimotor-pulse-schemas) FlatBuffer types.

The Pulse plugin publishes one FlatBuffer-encoded packet type per ZeroMQ PUB port,
at `tcp://<host>:<base_port + offset>` (default host `127.0.0.1`, default base
port `5000`), with **no framing or header** - the ZeroMQ message body IS the raw
FlatBuffer buffer (see `isimotor-pulse-plugin/src/main.cpp`,
`kOutboundPacketTypes` / `SendFlatBuffer`).

| Client | Packet type | Port offset | FlatBuffer root type |
|---|---|---|---|
| `TelemInfoClient` | 1 | +1 | `TelemInfo` |
| `CompactScoringClient` | 2 | +2 | `CompactScoring` |
| `SystemEventClient` | 3 | +3 | `SystemEvent` |
| `FullScoringClient` | 4 | +4 | `FullScoringSession` |
| `WeatherClient` | 7 | +7 | `WeatherControl` |
| `ExtendedStateClient` | 8 | +8 | `ExtendedState` |
| `ForceFeedbackClient` | 9 | +9 | `ForceFeedback` |
| `GraphicsClient` | 10 | +10 | `Graphics` |

These offsets are centralized in `PACKET_TYPE_OFFSETS` so no client hardcodes a
magic port number.

## Usage

```toml
[dependencies]
isimotor-pulse-client = { git = "https://github.com/marcgardent/isiMotor-Pulse-Plugin", tag = "v0.6.2" }
tokio = { version = "1", features = ["rt-multi-thread", "macros"] }
```

```rust
use isimotor_pulse_client::TelemInfoClient;

#[tokio::main]
async fn main() -> Result<(), isimotor_pulse_client::Error> {
    let mut client = TelemInfoClient::connect("127.0.0.1", 5000).await?;
    loop {
        let telem = client.recv().await?;
        println!("speed: {:?} rpm: {:?}", telem.local_vel, telem.engine_rpm);
    }
}
```

Every `XxxClient::connect(host, base_port)` computes its own real port from
`base_port` and its packet type's offset, then connects and subscribes a ZeroMQ
`SubSocket`. Every `XxxClient::recv()` receives the next message, verifies/reads
it as the corresponding FlatBuffer root type via `planus`, and returns the owned,
decoded Rust struct - never raw bytes.

## Testing

Unit tests cover the port-offset table and FlatBuffer decoding (buffers built
in-process with the `planus` builder, no live publisher needed):

```sh
cargo test
```

An optional integration test requires a real Pulse publisher (the plugin, or a
mock) running on `127.0.0.1:5001`:

```sh
cargo test --test live_telem_info -- --ignored
```
