//! Client for packet type 7: `WeatherControl` (the outbound weather-status
//! FlatBuffer - despite the port's "Weather" name in
//! `kOutboundPacketTypes`/the plugin, the root FlatBuffer table is named
//! `WeatherControl` in `schemas/weather.fbs`).

use isimotor_pulse_schemas::isimotor::fbs::{WeatherControl, WeatherControlRef};
use planus::ReadAsRoot;

use crate::client::{port_for, RawSubClient};
use crate::error::{Error, Result};
use crate::PACKET_TYPE_OFFSETS;

/// ZeroMQ SUB client for the `WeatherControl` packet (packet type 7),
/// connected to `tcp://<host>:<base_port + 7>`.
pub struct WeatherClient {
    inner: RawSubClient,
}

impl WeatherClient {
    /// Connects to the `WeatherControl` port derived from `base_port`.
    pub async fn connect(host: &str, base_port: u16) -> Result<Self> {
        let port = port_for(base_port, PACKET_TYPE_OFFSETS.weather);
        Ok(Self { inner: RawSubClient::connect(host, port).await? })
    }

    /// Receives and decodes the next `WeatherControl` FlatBuffer message.
    pub async fn recv(&mut self) -> Result<WeatherControl> {
        let bytes = self.inner.recv_bytes().await?;
        let r: WeatherControlRef = ReadAsRoot::read_as_root(&bytes).map_err(Error::Decode)?;
        WeatherControl::try_from(r).map_err(Error::Decode)
    }
}
