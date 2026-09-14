//! Client for packet type 9: `ForceFeedback`.

use isimotor_pulse_schemas::isimotor::fbs::{ForceFeedback, ForceFeedbackRef};
use planus::ReadAsRoot;

use crate::client::{port_for, RawSubClient};
use crate::error::{Error, Result};
use crate::PACKET_TYPE_OFFSETS;

/// ZeroMQ SUB client for the `ForceFeedback` packet (packet type 9),
/// connected to `tcp://<host>:<base_port + 9>`.
pub struct ForceFeedbackClient {
    inner: RawSubClient,
}

impl ForceFeedbackClient {
    /// Connects to the `ForceFeedback` port derived from `base_port`.
    pub async fn connect(host: &str, base_port: u16) -> Result<Self> {
        let port = port_for(base_port, PACKET_TYPE_OFFSETS.force_feedback);
        Ok(Self { inner: RawSubClient::connect(host, port).await? })
    }

    /// Receives and decodes the next `ForceFeedback` FlatBuffer message.
    pub async fn recv(&mut self) -> Result<ForceFeedback> {
        let bytes = self.inner.recv_bytes().await?;
        let r: ForceFeedbackRef = ReadAsRoot::read_as_root(&bytes).map_err(Error::Decode)?;
        ForceFeedback::try_from(r).map_err(Error::Decode)
    }
}
