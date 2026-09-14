//! Client for packet type 4: `FullScoringSession`.

use isimotor_pulse_schemas::isimotor::fbs::{FullScoringSession, FullScoringSessionRef};
use planus::ReadAsRoot;

use crate::client::{port_for, RawSubClient};
use crate::error::{Error, Result};
use crate::PACKET_TYPE_OFFSETS;

/// ZeroMQ SUB client for the `FullScoringSession` packet (packet type 4),
/// connected to `tcp://<host>:<base_port + 4>`.
pub struct FullScoringClient {
    inner: RawSubClient,
}

impl FullScoringClient {
    /// Connects to the `FullScoringSession` port derived from `base_port`.
    pub async fn connect(host: &str, base_port: u16) -> Result<Self> {
        let port = port_for(base_port, PACKET_TYPE_OFFSETS.full_scoring);
        Ok(Self { inner: RawSubClient::connect(host, port).await? })
    }

    /// Receives and decodes the next `FullScoringSession` FlatBuffer message.
    pub async fn recv(&mut self) -> Result<FullScoringSession> {
        let bytes = self.inner.recv_bytes().await?;
        let r: FullScoringSessionRef = ReadAsRoot::read_as_root(&bytes).map_err(Error::Decode)?;
        FullScoringSession::try_from(r).map_err(Error::Decode)
    }
}
