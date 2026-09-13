//! Rust FlatBuffers bindings for the isiMotor Pulse wire protocol
//! (telemetry, scoring, graphics, weather, force-feedback, system events,
//! inbound commands), generated at build time from `fbs/*.fbs` by
//! [`build.rs`](../build.rs) - see that crate's `README.md` for usage.

#![allow(clippy::all)]

include!(concat!(env!("OUT_DIR"), "/schema.rs"));
