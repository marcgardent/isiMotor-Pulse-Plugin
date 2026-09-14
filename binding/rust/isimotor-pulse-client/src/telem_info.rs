//! Client for packet type 1: `TelemInfo` (per-tick vehicle telemetry).

use isimotor_pulse_schemas::isimotor::fbs::{TelemInfo, TelemInfoRef};
use planus::ReadAsRoot;

use crate::client::{port_for, RawSubClient};
use crate::error::{Error, Result};
use crate::PACKET_TYPE_OFFSETS;

/// ZeroMQ SUB client for the `TelemInfo` packet (packet type 1), connected
/// to `tcp://<host>:<base_port + 1>`.
pub struct TelemInfoClient {
    inner: RawSubClient,
}

impl TelemInfoClient {
    /// Connects to the `TelemInfo` port derived from `base_port`.
    pub async fn connect(host: &str, base_port: u16) -> Result<Self> {
        let port = port_for(base_port, PACKET_TYPE_OFFSETS.telem_info);
        Ok(Self { inner: RawSubClient::connect(host, port).await? })
    }

    /// Receives and decodes the next `TelemInfo` FlatBuffer message.
    pub async fn recv(&mut self) -> Result<TelemInfo> {
        let bytes = self.inner.recv_bytes().await?;
        let r: TelemInfoRef = ReadAsRoot::read_as_root(&bytes).map_err(Error::Decode)?;
        TelemInfo::try_from(r).map_err(Error::Decode)
    }
}
