//! Client for packet type 2: `CompactScoring`.

use isimotor_pulse_schemas::isimotor::fbs::{CompactScoring, CompactScoringRef};
use planus::ReadAsRoot;

use crate::client::{port_for, RawSubClient};
use crate::error::{Error, Result};
use crate::PACKET_TYPE_OFFSETS;

/// ZeroMQ SUB client for the `CompactScoring` packet (packet type 2),
/// connected to `tcp://<host>:<base_port + 2>`.
pub struct CompactScoringClient {
    inner: RawSubClient,
}

impl CompactScoringClient {
    /// Connects to the `CompactScoring` port derived from `base_port`.
    pub async fn connect(host: &str, base_port: u16) -> Result<Self> {
        let port = port_for(base_port, PACKET_TYPE_OFFSETS.compact_scoring);
        Ok(Self { inner: RawSubClient::connect(host, port).await? })
    }

    /// Receives and decodes the next `CompactScoring` FlatBuffer message.
    pub async fn recv(&mut self) -> Result<CompactScoring> {
        let bytes = self.inner.recv_bytes().await?;
        let r: CompactScoringRef = ReadAsRoot::read_as_root(&bytes).map_err(Error::Decode)?;
        CompactScoring::try_from(r).map_err(Error::Decode)
    }
}
