//! Internal helper shared by every `XxxClient`: connect a ZeroMQ `SubSocket`
//! to `tcp://<host>:<port>`, subscribe to everything, and receive raw
//! FlatBuffer payloads. Not public API - each packet-type module wraps this
//! in a dedicated type that decodes into its own FlatBuffer root type.

use zeromq::{Socket, SocketRecv, SubSocket};

use crate::error::{Error, Result};

/// A connected ZeroMQ SUB socket for one Pulse packet-type port, yielding
/// raw (still-encoded) FlatBuffer buffers.
pub(crate) struct RawSubClient {
    socket: SubSocket,
}

impl RawSubClient {
    /// Connects to `tcp://<host>:<port>` and subscribes to all topics (the
    /// Pulse transport sends one unframed FlatBuffer per message with no
    /// topic prefix, so an empty-string subscription receives everything).
    pub(crate) async fn connect(host: &str, port: u16) -> Result<Self> {
        let endpoint = format!("tcp://{host}:{port}");
        let mut socket = SubSocket::new();
        socket
            .connect(&endpoint)
            .await
            .map_err(|source| Error::Connect { endpoint: endpoint.clone(), source })?;
        socket
            .subscribe("")
            .await
            .map_err(|source| Error::Subscribe { endpoint, source })?;
        Ok(Self { socket })
    }

    /// Receives the next message and returns its payload bytes. The Pulse
    /// wire protocol has no framing/header: the ZeroMQ message body IS the
    /// raw FlatBuffer buffer, carried as a single frame.
    pub(crate) async fn recv_bytes(&mut self) -> Result<Vec<u8>> {
        let msg = self.socket.recv().await.map_err(Error::Recv)?;
        let frame = msg.get(0).ok_or(Error::EmptyMessage)?;
        Ok(frame.to_vec())
    }
}

/// Computes the real TCP port for a packet type from its base port and
/// offset, mirroring the Pulse plugin's `TcpBasePort + packetType` mapping
/// (see `isimotor-pulse-plugin/src/main.cpp`, `kOutboundPacketTypes`).
pub(crate) fn port_for(base_port: u16, offset: u16) -> u16 {
    base_port + offset
}
