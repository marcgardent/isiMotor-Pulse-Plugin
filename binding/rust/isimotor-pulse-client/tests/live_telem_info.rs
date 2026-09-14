//! Optional integration test: requires a real Pulse publisher (the plugin,
//! or a mock) running on 127.0.0.1:5001 (TelemInfo, base_port 5000 + offset
//! 1). Not run by default:
//!
//! ```sh
//! cargo test --test live_telem_info -- --ignored
//! ```

use isimotor_pulse_client::{TelemInfoClient, DEFAULT_BASE_PORT, DEFAULT_HOST};

#[tokio::test]
#[ignore = "requires a live Pulse publisher on 127.0.0.1:5001"]
async fn receives_a_telem_info_packet() {
    let mut client = TelemInfoClient::connect(DEFAULT_HOST, DEFAULT_BASE_PORT)
        .await
        .expect("failed to connect to a live TelemInfo publisher");
    let telem = client.recv().await.expect("failed to receive/decode a TelemInfo packet");
    println!("{telem:?}");
}
