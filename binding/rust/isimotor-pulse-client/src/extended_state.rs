//! Client for packet type 8: `ExtendedState`.

use isimotor_pulse_schemas::isimotor::fbs::{ExtendedState, ExtendedStateRef};
use planus::ReadAsRoot;

use crate::client::{port_for, RawSubClient};
use crate::error::{Error, Result};
use crate::PACKET_TYPE_OFFSETS;

/// ZeroMQ SUB client for the `ExtendedState` packet (packet type 8),
/// connected to `tcp://<host>:<base_port + 8>`.
pub struct ExtendedStateClient {
    inner: RawSubClient,
}

impl ExtendedStateClient {
    /// Connects to the `ExtendedState` port derived from `base_port`.
    pub async fn connect(host: &str, base_port: u16) -> Result<Self> {
        let port = port_for(base_port, PACKET_TYPE_OFFSETS.extended_state);
        Ok(Self { inner: RawSubClient::connect(host, port).await? })
    }

    /// Receives and decodes the next `ExtendedState` FlatBuffer message.
    pub async fn recv(&mut self) -> Result<ExtendedState> {
        let bytes = self.inner.recv_bytes().await?;
        let r: ExtendedStateRef = ReadAsRoot::read_as_root(&bytes).map_err(Error::Decode)?;
        ExtendedState::try_from(r).map_err(Error::Decode)
    }
}
