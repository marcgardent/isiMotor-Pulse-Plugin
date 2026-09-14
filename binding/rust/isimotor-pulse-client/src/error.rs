//! Error type shared by every `XxxClient`.

/// Errors that can occur while connecting to or receiving from a Pulse
/// ZeroMQ publisher.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// Failed to connect the underlying ZeroMQ `SubSocket`.
    #[error("failed to connect to {endpoint}: {source}")]
    Connect {
        endpoint: String,
        #[source]
        source: zeromq::ZmqError,
    },

    /// Failed to subscribe the underlying ZeroMQ `SubSocket` to all topics.
    #[error("failed to subscribe on {endpoint}: {source}")]
    Subscribe {
        endpoint: String,
        #[source]
        source: zeromq::ZmqError,
    },

    /// The `SubSocket` returned an error while receiving a message.
    #[error("recv error: {0}")]
    Recv(#[source] zeromq::ZmqError),

    /// The received message decoded to zero frames (should not happen with
    /// this transport, which sends one unframed FlatBuffer per message).
    #[error("received a message with no frames")]
    EmptyMessage,

    /// The received buffer failed to decode as the expected FlatBuffer type.
    #[error("failed to decode FlatBuffer payload: {0}")]
    Decode(#[source] planus::Error),
}

pub type Result<T> = std::result::Result<T, Error>;
