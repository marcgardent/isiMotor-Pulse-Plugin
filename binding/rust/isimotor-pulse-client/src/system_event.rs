//! Client for packet type 3: `SystemEvent`.

use isimotor_pulse_schemas::isimotor::fbs::{SystemEvent, SystemEventRef};
use planus::ReadAsRoot;

use crate::client::{port_for, RawSubClient};
use crate::error::{Error, Result};
use crate::PACKET_TYPE_OFFSETS;

/// ZeroMQ SUB client for the `SystemEvent` packet (packet type 3),
/// connected to `tcp://<host>:<base_port + 3>`.
pub struct SystemEventClient {
    inner: RawSubClient,
}

impl SystemEventClient {
    /// Connects to the `SystemEvent` port derived from `base_port`.
    pub async fn connect(host: &str, base_port: u16) -> Result<Self> {
        let port = port_for(base_port, PACKET_TYPE_OFFSETS.system_event);
        Ok(Self { inner: RawSubClient::connect(host, port).await? })
    }

    /// Receives and decodes the next `SystemEvent` FlatBuffer message.
    pub async fn recv(&mut self) -> Result<SystemEvent> {
        let bytes = self.inner.recv_bytes().await?;
        let r: SystemEventRef = ReadAsRoot::read_as_root(&bytes).map_err(Error::Decode)?;
        SystemEvent::try_from(r).map_err(Error::Decode)
    }
}
