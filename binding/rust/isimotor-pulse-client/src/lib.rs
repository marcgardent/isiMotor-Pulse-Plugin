//! Typed ZeroMQ clients for the isiMotor Pulse wire protocol.
//!
//! The Pulse plugin publishes one FlatBuffer-encoded packet type per ZeroMQ
//! PUB port, at `tcp://<host>:<base_port + offset>` (default host
//! `127.0.0.1`, default base port `5000`), with **no framing or header** -
//! the ZeroMQ message body IS the raw FlatBuffer buffer (see
//! `isimotor-pulse-plugin/src/main.cpp`, `kOutboundPacketTypes` /
//! `SendFlatBuffer`).
//!
//! This crate exposes one dedicated client type per packet type, each of
//! which connects to its own port and decodes straight into the
//! corresponding [`isimotor_pulse_schemas`] FlatBuffer type - no generic
//! "give me a client for packet type N" API, and no raw-bytes API.
//!
//! ```no_run
//! # async fn example() -> Result<(), isimotor_pulse_client::Error> {
//! use isimotor_pulse_client::TelemInfoClient;
//!
//! let mut client = TelemInfoClient::connect("127.0.0.1", 5000).await?;
//! let telem = client.recv().await?;
//! println!("{telem:?}");
//! # Ok(())
//! # }
//! ```

mod client;
mod compact_scoring;
mod error;
mod extended_state;
mod force_feedback;
mod full_scoring;
mod graphics;
mod system_event;
mod telem_info;
mod weather;

pub use compact_scoring::CompactScoringClient;
pub use error::{Error, Result};
pub use extended_state::ExtendedStateClient;
pub use force_feedback::ForceFeedbackClient;
pub use full_scoring::FullScoringClient;
pub use graphics::GraphicsClient;
pub use system_event::SystemEventClient;
pub use telem_info::TelemInfoClient;
pub use weather::WeatherClient;

/// Port offsets for every outbound Pulse packet type, added to a
/// `base_port` to get the real TCP port - mirrors `kOutboundPacketTypes` in
/// `isimotor-pulse-plugin/src/main.cpp`. Centralized here so no offset is
/// duplicated as a magic number across the `XxxClient` modules.
pub struct PacketTypeOffsets {
    pub telem_info: u16,
    pub compact_scoring: u16,
    pub system_event: u16,
    pub full_scoring: u16,
    pub weather: u16,
    pub extended_state: u16,
    pub force_feedback: u16,
    pub graphics: u16,
}

/// The single source of truth for packet-type -> port-offset mapping used
/// by every `XxxClient::connect`.
pub const PACKET_TYPE_OFFSETS: PacketTypeOffsets = PacketTypeOffsets {
    telem_info: 1,
    compact_scoring: 2,
    system_event: 3,
    full_scoring: 4,
    weather: 7,
    extended_state: 8,
    force_feedback: 9,
    graphics: 10,
};

/// The Pulse plugin's default ZeroMQ host (`DEFAULT_ZMQ_HOST` in
/// `isimotor-pulse-plugin/src/main.cpp`).
pub const DEFAULT_HOST: &str = "127.0.0.1";

/// The Pulse plugin's default ZeroMQ base port (`DEFAULT_ZMQ_PORT` in
/// `isimotor-pulse-plugin/src/main.cpp`).
pub const DEFAULT_BASE_PORT: u16 = 5000;

#[cfg(test)]
mod tests {
    use super::*;
    use isimotor_pulse_schemas::isimotor::fbs::SystemEvent;
    use planus::{Builder, ReadAsRoot};

    #[test]
    fn port_offsets_add_to_base_port() {
        assert_eq!(DEFAULT_BASE_PORT + PACKET_TYPE_OFFSETS.telem_info, 5001);
        assert_eq!(DEFAULT_BASE_PORT + PACKET_TYPE_OFFSETS.compact_scoring, 5002);
        assert_eq!(DEFAULT_BASE_PORT + PACKET_TYPE_OFFSETS.system_event, 5003);
        assert_eq!(DEFAULT_BASE_PORT + PACKET_TYPE_OFFSETS.full_scoring, 5004);
        assert_eq!(DEFAULT_BASE_PORT + PACKET_TYPE_OFFSETS.weather, 5007);
        assert_eq!(DEFAULT_BASE_PORT + PACKET_TYPE_OFFSETS.extended_state, 5008);
        assert_eq!(DEFAULT_BASE_PORT + PACKET_TYPE_OFFSETS.force_feedback, 5009);
        assert_eq!(DEFAULT_BASE_PORT + PACKET_TYPE_OFFSETS.graphics, 5010);
    }

    #[test]
    fn port_offsets_match_k_outbound_packet_types() {
        // Mirrors `kOutboundPacketTypes` in isimotor-pulse-plugin/src/main.cpp.
        let mut offsets = [
            PACKET_TYPE_OFFSETS.telem_info,
            PACKET_TYPE_OFFSETS.compact_scoring,
            PACKET_TYPE_OFFSETS.system_event,
            PACKET_TYPE_OFFSETS.full_scoring,
            PACKET_TYPE_OFFSETS.weather,
            PACKET_TYPE_OFFSETS.extended_state,
            PACKET_TYPE_OFFSETS.force_feedback,
            PACKET_TYPE_OFFSETS.graphics,
        ];
        offsets.sort_unstable();
        assert_eq!(offsets, [1, 2, 3, 4, 7, 8, 9, 10]);
    }

    #[test]
    fn decodes_a_flatbuffer_buffer_built_with_planus() {
        // Build a minimal SystemEvent buffer with the planus builder, the
        // same way the C++/Python side would, then confirm our client-side
        // decode path (ReadAsRoot -> TryFrom<Ref> -> owned type) round-trips it.
        let mut builder = Builder::new();
        let event = SystemEvent { event_type: 3 };
        let bytes = builder.finish(&event, None);

        let r: isimotor_pulse_schemas::isimotor::fbs::SystemEventRef =
            ReadAsRoot::read_as_root(bytes).expect("valid FlatBuffer buffer");
        let decoded = SystemEvent::try_from(r).expect("decodes into owned SystemEvent");

        assert_eq!(decoded.event_type, 3);
    }
}
