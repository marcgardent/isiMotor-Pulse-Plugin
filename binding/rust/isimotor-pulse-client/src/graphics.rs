//! Client for packet type 10: `Graphics`.

use isimotor_pulse_schemas::isimotor::fbs::{Graphics, GraphicsRef};
use planus::ReadAsRoot;

use crate::client::{port_for, RawSubClient};
use crate::error::{Error, Result};
use crate::PACKET_TYPE_OFFSETS;

/// ZeroMQ SUB client for the `Graphics` packet (packet type 10), connected
/// to `tcp://<host>:<base_port + 10>`.
pub struct GraphicsClient {
    inner: RawSubClient,
}

impl GraphicsClient {
    /// Connects to the `Graphics` port derived from `base_port`.
    pub async fn connect(host: &str, base_port: u16) -> Result<Self> {
        let port = port_for(base_port, PACKET_TYPE_OFFSETS.graphics);
        Ok(Self { inner: RawSubClient::connect(host, port).await? })
    }

    /// Receives and decodes the next `Graphics` FlatBuffer message.
    pub async fn recv(&mut self) -> Result<Graphics> {
        let bytes = self.inner.recv_bytes().await?;
        let r: GraphicsRef = ReadAsRoot::read_as_root(&bytes).map_err(Error::Decode)?;
        Graphics::try_from(r).map_err(Error::Decode)
    }
}
