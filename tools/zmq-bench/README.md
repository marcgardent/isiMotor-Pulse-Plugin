# zmq-bench

A standalone Rust benchmark that measures **Hz and jitter per ZeroMQ PUB port**
for the isiMotor Pulse transport — the ZeroMQ/FlatBuffers sibling of
`tools/udp-bench` (which measured the older RawUDP transport), reporting at
the same level of detail.

## Why

The Pulse plugin (`isimotor-pulse-plugin/src/main.cpp`) publishes each
outbound packet type on its **own ZeroMQ PUB socket**, bound on
`tcp://<TargetIp>:(TcpBasePort + packetType)`, with no header, no chunking —
the ZeroMQ message *is* the FlatBuffer payload. This tool connects a SUB
socket per port and quantifies real-world cadence and jitter per stream, most
importantly for `ForceFeedback` (packet type 9, up to 400Hz — the
tightest-latency stream in the protocol).

## What it measures, per port

- **Hz (avg)**: `(frames - 1) / (time between first and last frame)`. A
  "frame" here is one ZeroMQ message — unlike `udp-bench`, there is no
  chunking to account for, since ZeroMQ messages aren't bounded by UDP's MTU.
- **Jitter**: computed on the inter-arrival time between consecutive frames
  (in ms): min / mean / max / stddev, plus the same RFC 3550 §6.4.1-style
  smoothed mean-absolute-jitter estimator `udp-bench` uses
  (`J += (|D_i| - J) / 16`).
- **Stalls**: a heuristic substitute for `udp-bench`'s sequence-gap loss
  count. The Pulse wire payload carries **no sequence number** (see
  `schemas/*.fbs`), so gap-based loss can't be computed here; instead, once a
  port's running mean interval has stabilized (8+ samples), any interval more
  than 3x that mean is counted as a stall. This is a proxy, not an exact loss
  count — most `sndhwm`-bound sockets (see `main.cpp`, `zmq::sockopt::sndhwm`)
  drop silently under backpressure rather than stalling, so a low stall count
  does not guarantee zero drops.

## Design

- **One OS thread per port**, matching `udp-bench`. The `zeromq` crate is
  async-only, so each thread runs its own single-threaded Tokio runtime
  around one `SubSocket`. `zeromq` is pure Rust (no libzmq system dependency),
  so this tool builds with just `cargo` — same rationale as
  `isimotor-pulse-schemas` using `planus` instead of requiring `flatc`.
- Each thread timestamps every received message with `std::time::Instant`
  (monotonic) and forwards `(packet_type, timestamp, byte_len)` to the main
  thread over an `mpsc` channel, which owns all `PortStats` single-threaded —
  no locking on the hot path.
- Message *content* is not decoded: Hz/jitter only need arrival timestamps,
  so this tool doesn't depend on `isimotor-pulse-schemas`.

## Running it

```sh
cargo run --release -- --base-port 5000 --duration-secs 30
```

Point `--host` at the machine running the plugin and set the plugin's
`TcpHost`/`TcpBasePort` config to match (default base port `5000`, matching
`DEFAULT_ZMQ_PORT` in `main.cpp`).

### CLI options

| Flag | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Host to connect SUB sockets to |
| `--base-port` | `5000` | Each packet type connects to `base_port + packet_type` |
| `--packet-types` | `1,2,3,4,7,8,9,10` | Comma-separated list of packet types (see `kOutboundPacketTypes` in `main.cpp`) |
| `--duration-secs` | `30` | Run duration; `0` runs until Ctrl+C |
| `--json` | off | Also print a machine-readable JSON summary after the table |

Duplicate or empty `--packet-types` lists are rejected before any sockets are
connected.

### Testing without the game

Any ZeroMQ PUB socket bound on `tcp://127.0.0.1:<base_port + packet_type>`
works for a smoke test — the message payload's *content* is irrelevant here,
only its arrival timing matters. A minimal pyzmq script binding one PUB per
type and sending fixed-size dummy payloads at a steady rate is enough; there
is currently no mock sender checked into this tool (same gap noted in
`tools/udp-bench`'s README, and a natural shared follow-up).

## Output

```
Port   Type Name                   Frames    Hz(avg)    Jit-min   Jit-mean    Jit-max  Jit-rfc3550(ms)   Stalls
5001   1    TelemInfo                 1868      62.31      0.310      0.420      1.980            0.381        0
5009   9    ForceFeedback            11998     399.94      0.021      0.052      0.410            0.061        2
```

With `--json`, a JSON array of per-port objects follows the table (same
fields, plus `jitter_stddev_ms` and `bytes_total`).
