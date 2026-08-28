# Feature Request: FR-01 — Protocol Standardization, Unified Header & Packet Framing

- **Status**: 📝 Planned
- **Priority**: High (Foundational)
- **Target Standard**: [rF2SharedMemoryMapPlugin v3.7.x](TARGET.md) (Weak Synchronization, Versioning & Buffer Masks)

---

## 1. Context & Motivation

In `rF2SharedMemoryMapPlugin`, shared memory buffers use weak synchronization via version variables (`mVersionUpdateBegin` / `mVersionUpdateEnd`) and a global configuration mask (`UnsubscribedBuffersMask`) to prevent reading torn frames and avoid redundant memory writes.

In a pure UDP binary architecture:
1. **Packet Identification & Stream Demuxing**: Each binary stream must be identifiable by a standardized, zero-overhead packet header.
2. **Packet Loss & Out-of-Order Detection**: Monotonic per-channel sequence numbers allow clients (Python, SimHub, C#) to detect dropped or reordered packets.
3. **Payload Slicing (MTU Management)**: Larger payloads (such as full 128-vehicle scoring matrices exceeding 40 KB) cannot be sent in a single UDP datagram without risking IP fragmentation or packet drop over Wi-Fi/routers. A zero-allocation slicing mechanism (`chunkIndex` / `totalChunks`) is required.

---

## 2. Technical Specification

### 2.1 Standardized Binary Header (`RawUdpHeader`)

All transmitted packets will prepend a fixed 24-byte header aligned with `#pragma pack(push, 4)`.

```cpp
#pragma pack(push, 4)

struct RawUdpHeader {
    char          magic[4];          // Magic identifier: "SIMP" (isiMotor Protocol)
    unsigned char protocolVersion;   // Protocol schema version (starts at 1)
    unsigned char packetType;        // Stream identifier (see enum below)
    unsigned short payloadSize;      // Byte length of payload immediately following header
    unsigned int  sequenceNumber;    // Monotonic sequence counter per stream
    double        sessionET;         // Current session elapsed time in seconds
    unsigned char chunkIndex;        // 0 if unfragmented, or index 0..(totalChunks-1)
    unsigned char totalChunks;       // 1 if unfragmented, or total chunk count
    unsigned short subTypeOrId;      // Contextual ID (e.g., vehicle ID, rule sub-event)
};

#pragma pack(pop)
```

### 2.2 Packet Type Identifiers (`PacketTypeEnum`)

| Packet Type ID | Name | Direction | Payload Size | Default Frequency |
|:---:|---|:---:|---|---|
| `1` | `TelemInfoV01` (Raw Telemetry) | Outbound | 1888 B | 60–100 Hz (Raw) |
| `2` | `CompactScoring` | Outbound | 168 B | 5 Hz |
| `3` | `SystemEvent` | Outbound | 2 B | On event |
| `4` | `FullScoring` (Multi-Vehicle) | Outbound | Variable (Sliced) | 5 Hz |
| `5` | `TrackRules` (Flags & Safety Car)| Outbound | ~1–2 KB | 3 Hz |
| `6` | `PitMenu` (Pit Info Buffer) | Outbound | ~320 B | 100 Hz |
| `7` | `Weather` (Ambient & Track) | Outbound | ~120 B | 1 Hz |
| `8` | `Extended` (Damage & Options) | Outbound | ~512 B | 5 Hz |
| `9` | `ForceFeedback` (FFB Torque) | Outbound | 16 B | 400 Hz |
| `10`| `Graphics` (Camera & Views) | Outbound | ~256 B | 100–400 Hz |
| `100`| `HWControlInput` | Inbound | 32 B | 50–100 Hz |
| `101`| `WeatherControlInput` | Inbound | 64 B | 1–5 Hz |

### 2.3 Server-Side Stream Control (`isiMotor_RawUDP.ini` is Master)

To maintain full deterministic Multicast and Broadcast compatibility (where N clients listen to a single stream without interfering with each other), the **`isiMotor_RawUDP.ini` configuration file is the sole master** governing stream emission and CPU/network overhead.

Client applications filter streams locally using the fixed 24-byte `RawUdpHeader` (`packetType` field, < 1 ns overhead) without dynamic network unsubscription commands.

In addition to granular frequency keys (`Telemetry=100Hz`, `FullScoring=5Hz`, `ForceFeedback=off`), the INI supports the standard `UnsubscribedBuffersMask` bitmask for static boot-time disabling:

```ini
[Streams]
; Bitmask: Telemetry=1, Scoring=2, Rules=4, MultiRules=8, ForceFeedback=16, Graphics=32, PitInfo=64, Weather=128
UnsubscribedBuffersMask=0
```

---

## 3. Zero-Allocation Packet Slicing Design

For multi-car scoring (FR-02) exceeding standard MTU (~1400 bytes):
- The C++ transmitter slices the struct into fixed chunks (e.g. 1024 bytes payload + 24 bytes header).
- No dynamic memory allocation (`malloc`, `new`, `std::vector`) is used. Slicing uses static stack buffers or direct pointer offsets during `sendto()`.

```cpp
void SendSlicedPacket(unsigned char packetType, const void* data, size_t totalSize, size_t maxChunkSize = 1200) {
    const char* src = reinterpret_cast<const char*>(data);
    size_t offset = 0;
    unsigned char totalChunks = static_cast<unsigned char>((totalSize + maxChunkSize - 1) / maxChunkSize);
    unsigned char chunkIdx = 0;

    while (offset < totalSize) {
        size_t currentChunkSize = (totalSize - offset > maxChunkSize) ? maxChunkSize : (totalSize - offset);
        
        RawUdpHeader hdr{};
        hdr.magic[0] = 'S'; hdr.magic[1] = 'I'; hdr.magic[2] = 'M'; hdr.magic[3] = 'P';
        hdr.protocolVersion = 1;
        hdr.packetType = packetType;
        hdr.payloadSize = static_cast<unsigned short>(currentChunkSize);
        hdr.sequenceNumber = ++m_seqCounter[packetType];
        hdr.sessionET = m_currentET;
        hdr.chunkIndex = chunkIdx++;
        hdr.totalChunks = totalChunks;

        // Send header + chunk via WSASend or dual scatter buffer
        // Zero-copy or 1 small stack buffer copy
        ...
        offset += currentChunkSize;
    }
}
```

---

## 4. Python Client Integration (`isimotor-rawudp-client`)

- Python client parses the 24-byte `RawUdpHeader` systematically.
- Sliced packet reassembly buffer indexed by `(packetType, sequenceNumber)` to assemble multipart payloads before calling event callbacks.

---

## 5. Acceptance Criteria & Definition of Done

- [ ] `RawUdpHeader` struct defined and verified for 24-byte size and 4-byte packing alignment.
- [ ] Sequence numbers increment monotonically per stream.
- [ ] Telemetry, Compact Scoring, and System Events migrated to use the unified header without regressions.
- [ ] Zero heap allocations measured during packet header formatting and transmission.
- [ ] Integration tests in `tests/test_golden_truth.py` asserting header decoding and chunk reassembly.
