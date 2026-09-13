//! zmq-bench — Hz and jitter benchmark for the isiMotor Pulse ZeroMQ transport.
//!
//! Same measurement methodology and report shape as `tools/udp-bench` (the
//! RawUDP-era sibling of this tool), adapted to the Pulse plugin's
//! transport: one PUB socket per packet type, bound on `tcp://host:(base_port
//! + packet_type)`, carrying a single unframed FlatBuffer message per send
//! (see `isimotor-pulse-plugin/src/main.cpp`, `SendFlatBuffer`). There is no
//! header, no chunking, and no sequence number in the wire payload, so unlike
//! `udp-bench` this tool cannot report a sequence-gap-based loss estimate;
//! it reports a "stall" count instead (see `record_frame` below).
//!
//! ## Design
//!
//! - **One OS thread per port**, matching `udp-bench`. Each thread runs its
//!   own single-threaded Tokio runtime (the `zeromq` crate is async-only;
//!   there is no libzmq dependency here — `zeromq` is pure Rust, so this
//!   tool builds with just `cargo`, same rationale as the
//!   `isimotor-pulse-schemas` crate using `planus` instead of `flatc`), which
//!   connects a `SubSocket` to `tcp://<host>:<base_port + packet_type>`,
//!   subscribes to everything, and receives in a loop.
//! - Each received message is timestamped with `std::time::Instant`
//!   (monotonic) and forwarded (packet_type, timestamp, byte length) to the
//!   main thread over an `mpsc` channel. The main thread owns all
//!   `PortStats` state single-threaded, so there's no locking on the hot
//!   path — same as `udp-bench`.
//! - Message *content* (the FlatBuffer payload) is not decoded: Hz and
//!   jitter only need arrival timestamps, and decoding would require
//!   depending on `isimotor-pulse-schemas` for a value this tool doesn't
//!   otherwise use.

use std::collections::BTreeMap;
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

use zeromq::{Socket, SocketRecv, SubSocket};

/// Outbound packet types the Pulse plugin publishes, and their FlatBuffer
/// table name — mirrors `kOutboundPacketTypes` / the `SendFlatBuffer(N, ...)`
/// call sites in `isimotor-pulse-plugin/src/main.cpp`.
fn default_packet_types() -> Vec<(u8, &'static str)> {
    vec![
        (1, "TelemInfo"),
        (2, "CompactScoring"),
        (3, "SystemEvent"),
        (4, "FullScoringSession"),
        (7, "Weather"),
        (8, "ExtendedState"),
        (9, "ForceFeedback"),
        (10, "Graphics"),
    ]
}

struct Args {
    host: String,
    base_port: u16,
    packet_types: Vec<u8>,
    duration_secs: u64,
    json: bool,
}

fn parse_args() -> Result<Args, String> {
    let mut host = "127.0.0.1".to_string();
    let mut base_port: u16 = 5000;
    let mut packet_types: Option<Vec<u8>> = None;
    let mut duration_secs: u64 = 30;
    let mut json = false;

    let raw: Vec<String> = std::env::args().skip(1).collect();
    let mut i = 0;
    while i < raw.len() {
        match raw[i].as_str() {
            "--host" => {
                i += 1;
                host = raw.get(i).ok_or("--host needs a value")?.clone();
            }
            "--base-port" => {
                i += 1;
                base_port = raw
                    .get(i)
                    .ok_or("--base-port needs a value")?
                    .parse()
                    .map_err(|_| "--base-port must be a u16")?;
            }
            "--packet-types" => {
                i += 1;
                let raw_list = raw.get(i).ok_or("--packet-types needs a value")?;
                let mut list = Vec::new();
                for part in raw_list.split(',') {
                    let n: u8 = part
                        .trim()
                        .parse()
                        .map_err(|_| format!("invalid packet type '{part}'"))?;
                    list.push(n);
                }
                packet_types = Some(list);
            }
            "--duration-secs" => {
                i += 1;
                duration_secs = raw
                    .get(i)
                    .ok_or("--duration-secs needs a value")?
                    .parse()
                    .map_err(|_| "--duration-secs must be a non-negative integer")?;
            }
            "--json" => json = true,
            "-h" | "--help" => return Err("help".to_string()),
            other => return Err(format!("unknown argument '{other}'")),
        }
        i += 1;
    }

    let known = default_packet_types();
    let packet_types = packet_types.unwrap_or_else(|| known.iter().map(|(n, _)| *n).collect());

    if packet_types.is_empty() {
        return Err("--packet-types list is empty".to_string());
    }
    let mut seen = std::collections::HashSet::new();
    for pt in &packet_types {
        if !seen.insert(*pt) {
            return Err(format!("duplicate packet type {pt} in --packet-types"));
        }
    }

    Ok(Args {
        host,
        base_port,
        packet_types,
        duration_secs,
        json,
    })
}

fn print_usage() {
    eprintln!("usage: zmq-bench [--host 127.0.0.1] [--base-port 5000] [--packet-types 1,2,3,4,7,8,9,10] [--duration-secs 30] [--json]");
    eprintln!();
    eprintln!("Connects a ZeroMQ SUB socket per packet type to tcp://<host>:<base_port + packet_type>");
    eprintln!("(one dedicated OS thread each) and reports Hz / jitter once the run ends.");
}

/// A timestamped arrival forwarded from a listener thread to the aggregator.
struct Arrival {
    packet_type: u8,
    at: Instant,
    bytes: usize,
}

/// Per-port running stats, owned single-threaded by the aggregator — same
/// shape as `udp-bench`'s `PortStats`, minus frame/datagram distinction
/// (ZeroMQ delivers whole messages, no chunking) and minus the sequence-gap
/// loss estimate (the wire payload carries no sequence number here).
struct PortStats {
    packet_type: u8,
    name: &'static str,
    frames: u64,
    bytes_total: u64,
    start: Option<Instant>,
    last: Option<Instant>,
    // Streaming mean/variance of inter-arrival deltas (Welford).
    mean: f64,
    m2: f64,
    min: f64,
    max: f64,
    prev_delta: Option<f64>,
    // RFC 3550 §6.4.1 smoothed mean-absolute-jitter estimator.
    rfc3550_j: f64,
    // Heuristic stall count: intervals more than 3x the running mean once
    // the mean has stabilized (>=8 samples) — a substitute for udp-bench's
    // sequence-gap loss count, which this transport's payload can't provide.
    stalls: u64,
}

impl PortStats {
    fn new(packet_type: u8, name: &'static str) -> Self {
        PortStats {
            packet_type,
            name,
            frames: 0,
            bytes_total: 0,
            start: None,
            last: None,
            mean: 0.0,
            m2: 0.0,
            min: f64::INFINITY,
            max: 0.0,
            prev_delta: None,
            rfc3550_j: 0.0,
            stalls: 0,
        }
    }

    fn record(&mut self, at: Instant, bytes: usize) {
        self.frames += 1;
        self.bytes_total += bytes as u64;
        if self.start.is_none() {
            self.start = Some(at);
        }
        if let Some(prev) = self.last {
            let dt = at.duration_since(prev).as_secs_f64();
            let n = (self.frames - 1) as f64;
            let delta = dt - self.mean;
            self.mean += delta / n;
            let delta2 = dt - self.mean;
            self.m2 += delta * delta2;
            if dt < self.min {
                self.min = dt;
            }
            if dt > self.max {
                self.max = dt;
            }
            if n >= 8.0 && dt > 3.0 * self.mean {
                self.stalls += 1;
            }
            if let Some(prev_delta) = self.prev_delta {
                let d = dt - prev_delta;
                self.rfc3550_j += (d.abs() - self.rfc3550_j) / 16.0;
            }
            self.prev_delta = Some(dt);
        }
        self.last = Some(at);
    }

    fn stddev(&self) -> f64 {
        let n = self.frames.saturating_sub(1);
        if n < 2 {
            0.0
        } else {
            (self.m2 / (n - 1) as f64).sqrt()
        }
    }

    fn hz_avg(&self) -> f64 {
        match (self.start, self.last) {
            (Some(s), Some(l)) if self.frames > 1 => {
                let elapsed = l.duration_since(s).as_secs_f64();
                if elapsed > 0.0 {
                    (self.frames - 1) as f64 / elapsed
                } else {
                    0.0
                }
            }
            _ => 0.0,
        }
    }
}

/// Listener thread body: connects a SUB socket to one port and forwards
/// every received message's timestamp+length to `tx` until told to stop.
async fn listen(host: String, port: u16, packet_type: u8, tx: mpsc::Sender<Arrival>) {
    let endpoint = format!("tcp://{host}:{port}");
    let mut sock = SubSocket::new();
    if let Err(e) = sock.connect(&endpoint).await {
        eprintln!("[packet_type {packet_type}] connect to {endpoint} failed: {e}");
        return;
    }
    if let Err(e) = sock.subscribe("").await {
        eprintln!("[packet_type {packet_type}] subscribe failed: {e}");
        return;
    }
    loop {
        match sock.recv().await {
            Ok(msg) => {
                let at = Instant::now();
                let bytes: usize = msg.iter().map(|f| f.len()).sum();
                if tx.send(Arrival { packet_type, at, bytes }).is_err() {
                    return; // aggregator has shut down
                }
            }
            Err(e) => {
                eprintln!("[packet_type {packet_type}] recv error: {e}");
                return;
            }
        }
    }
}

fn print_table(stats: &BTreeMap<u8, PortStats>, base_port: u16) {
    println!(
        "{:<6} {:<4} {:<20} {:>8} {:>10} {:>10} {:>10} {:>10} {:>16} {:>8}",
        "Port", "Type", "Name", "Frames", "Hz(avg)", "Jit-min", "Jit-mean", "Jit-max", "Jit-rfc3550(ms)", "Stalls"
    );
    for s in stats.values() {
        println!(
            "{:<6} {:<4} {:<20} {:>8} {:>10.2} {:>10.3} {:>10.3} {:>10.3} {:>16.3} {:>8}",
            base_port as u32 + s.packet_type as u32,
            s.packet_type,
            s.name,
            s.frames,
            s.hz_avg(),
            if s.min.is_finite() { s.min * 1000.0 } else { 0.0 },
            s.mean * 1000.0,
            s.max * 1000.0,
            s.rfc3550_j * 1000.0,
            s.stalls,
        );
    }
}

fn print_json(stats: &BTreeMap<u8, PortStats>, base_port: u16) {
    #[derive(serde::Serialize)]
    struct Row {
        port: u16,
        packet_type: u8,
        name: &'static str,
        frames: u64,
        bytes_total: u64,
        hz_avg: f64,
        jitter_min_ms: f64,
        jitter_mean_ms: f64,
        jitter_max_ms: f64,
        jitter_stddev_ms: f64,
        jitter_rfc3550_ms: f64,
        stalls: u64,
    }
    let rows: Vec<Row> = stats
        .values()
        .map(|s| Row {
            port: base_port + s.packet_type as u16,
            packet_type: s.packet_type,
            name: s.name,
            frames: s.frames,
            bytes_total: s.bytes_total,
            hz_avg: s.hz_avg(),
            jitter_min_ms: if s.min.is_finite() { s.min * 1000.0 } else { 0.0 },
            jitter_mean_ms: s.mean * 1000.0,
            jitter_max_ms: s.max * 1000.0,
            jitter_stddev_ms: s.stddev() * 1000.0,
            jitter_rfc3550_ms: s.rfc3550_j * 1000.0,
            stalls: s.stalls,
        })
        .collect();
    println!("{}", serde_json::to_string_pretty(&rows).unwrap());
}

fn main() {
    let args = match parse_args() {
        Ok(a) => a,
        Err(e) => {
            if e != "help" {
                eprintln!("error: {e}");
            }
            print_usage();
            std::process::exit(if e == "help" { 0 } else { 2 });
        }
    };

    let known = default_packet_types();
    let name_for = |pt: u8| -> &'static str {
        known.iter().find(|(n, _)| *n == pt).map(|(_, name)| *name).unwrap_or("Unknown")
    };

    let (tx, rx) = mpsc::channel::<Arrival>();
    let mut handles = Vec::new();
    for &pt in &args.packet_types {
        let host = args.host.clone();
        let port = args.base_port + pt as u16;
        let tx = tx.clone();
        handles.push(thread::spawn(move || {
            let rt = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .expect("failed to build per-port Tokio runtime");
            rt.block_on(listen(host, port, pt, tx));
        }));
    }
    drop(tx); // aggregator's rx ends once every listener thread's clone is dropped

    println!(
        "zmq-bench: subscribing to {} port(s) on {} (base_port={}), running for {}",
        args.packet_types.len(),
        args.host,
        args.base_port,
        if args.duration_secs == 0 {
            "until Ctrl+C".to_string()
        } else {
            format!("{}s", args.duration_secs)
        }
    );

    let mut stats: BTreeMap<u8, PortStats> = args
        .packet_types
        .iter()
        .map(|&pt| (pt, PortStats::new(pt, name_for(pt))))
        .collect();

    let deadline = if args.duration_secs == 0 {
        None
    } else {
        Some(Instant::now() + Duration::from_secs(args.duration_secs))
    };

    loop {
        let timeout = match deadline {
            Some(d) => match d.checked_duration_since(Instant::now()) {
                Some(remaining) if !remaining.is_zero() => remaining.min(Duration::from_millis(200)),
                _ => break,
            },
            None => Duration::from_millis(200),
        };
        match rx.recv_timeout(timeout) {
            Ok(arrival) => {
                if let Some(s) = stats.get_mut(&arrival.packet_type) {
                    s.record(arrival.at, arrival.bytes);
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }

    println!();
    print_table(&stats, args.base_port);
    if args.json {
        print_json(&stats, args.base_port);
    }

    // Listener threads are daemon-ish (blocked in recv().await on a socket
    // that nothing will close from this side); the process exit reaps them,
    // so we deliberately don't join here.
    let _ = handles;
}
