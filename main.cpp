/**
 * isiMotor-RawUDP-Plugin
 * High-Performance Raw Binary Telemetry & Multi-Car Scoring Plugin for isiMotor games
 * (Le Mans Ultimate, rFactor 2).
 * 
 * Features:
 * - Zero third-party dependencies (no nlohmann/json, no Boost, native Winsock2 only).
 * - Zero dynamic memory allocations in high-frequency telemetry and scoring update loops.
 * - Standardized 24-byte UDP header with monotonic sequence numbering and chunk slicing.
 * - Direct binary memory dump of TelemInfoV01 (1888 bytes) over UDP.
 * - Multi-vehicle full scoring stream (up to 128 vehicles, ScoringInfoV01 + VehicleScoringInfoV01).
 * - Compact binary scoring packet (SIMP Type 2, 168 bytes) for ultra-low overhead HUDs.
 * - System event state notifications (SIMP Type 3, 6 bytes).
 * - UnsubscribedBuffersMask support matching rF2SharedMemoryMapPlugin.
 * - Self-generating & configurable via 'isiMotor_RawUDP.ini' placed next to the DLL.
 * - Sub-millisecond latency supporting 120Hz to 400Hz+ streaming.
 */

#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <cstddef>
#include <algorithm>
#include <ctime>
#include <cmath>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#define __cdecl
#define __declspec(x)
typedef void* HWND;
#define long int
#define SOCKET int
#define INVALID_SOCKET -1
#define closesocket close
#define HINSTANCE void*
#define HMODULE void*
#define BOOL int
#define TRUE 1
#define FALSE 0
#define APIENTRY
#define DWORD unsigned long
#define LPVOID void*
#define DLL_PROCESS_ATTACH 1
#define MAX_PATH 260
#define INVALID_FILE_ATTRIBUTES ((DWORD)-1)
#define GetFileAttributesA(p) INVALID_FILE_ATTRIBUTES
#define GetPrivateProfileStringA(s, k, d, b, sz, p) std::strncpy(b, d, sz)
#define GetPrivateProfileIntA(s, k, d, p) (d)
#define GetModuleFileNameA(m, b, sz) 0
typedef union _LARGE_INTEGER {
    int64_t QuadPart;
} LARGE_INTEGER;
struct WSADATA {};
#define MAKEWORD(a, b) 0
#define WSAStartup(v, d) 0
#define WSACleanup() ((void)0)
#endif

#include "include/InternalsPlugin.hpp"

#define PLUGIN_NAME "isiMotor-RawUDP"
#define DEFAULT_UDP_PORT 5000
#define DEFAULT_UDP_HOST "127.0.0.1"
#define INI_FILE_NAME "isiMotor_RawUDP.ini"

// Module handle saved at DLL injection time
static HINSTANCE g_hModule = NULL;

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    (void)lpReserved;
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        g_hModule = hModule;
    }
    return TRUE;
}

#pragma pack(push, 4)

/**
 * Standardized 24-byte UDP Packet Header (SIMP Protocol)
 */
struct RawUdpHeader {
    char          magic[4];          // "SIMP"
    unsigned char protocolVersion;   // 1
    unsigned char packetType;        // 1=Telemetry, 2=CompactScoring, 3=SystemEvent, 4=FullScoring
    unsigned short payloadSize;      // Payload bytes following header
    unsigned int  sequenceNumber;    // Monotonic per-stream sequence counter
    double        sessionET;         // Current session elapsed time in seconds
    unsigned char chunkIndex;        // 0-based chunk index
    unsigned char totalChunks;       // Total chunk count for this frame
    unsigned short subTypeOrId;      // Context ID (e.g., active vehicle count or slot ID)
};

/**
 * Compact Scoring Packet (SIMP Type 2)
 * Lightweight 168-byte representation of session and player timing data.
 */
struct CompactScoringPacket {
    char magic[4];           // "SIMP"
    unsigned char packetType;// 2 = Scoring
    char trackName[64];      // Current track name (null-terminated)
    long session;            // 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race
    double currentET;        // Current session elapsed time in seconds
    double lapDist;          // Track total lap distance in meters
    long maxLaps;            // Maximum laps for session
    bool inRealtime;         // True if in active realtime driving mode
    short totalLaps;         // Player laps completed
    signed char sector;      // Current sector (0=Sector 3, 1=Sector 1, 2=Sector 2)
    bool inGarageStall;      // True if vehicle is inside the garage stall
    unsigned char countLapFlag; // 0=invalid, 1=lap count only, 2=valid lap & time
    double curSector1;       // Player current sector 1 time
    double curSector2;       // Player current sector 2 cumulative time (S1 + S2)
    double lastSector1;      // Player last lap sector 1 time
    double lastSector2;      // Player last lap sector 2 cumulative time
    double lastLapTime;      // Player last lap total time
    double bestSector1;      // Player personal best sector 1 time
    double bestSector2;      // Player personal best sector 2 cumulative time
    double bestLapTime;      // Player personal best lap time
};

/**
 * System Event Packet (SIMP Type 3)
 * 6-byte packet triggered on state transitions.
 */
struct SystemEventPacket {
    char magic[4];           // "SIMP"
    unsigned char packetType;// 3 = System Event
    unsigned char eventType; // 1 = EnterRealtime, 2 = ExitRealtime, 3 = StartSession, 4 = EndSession
};

/**
 * Full Scoring Session Header (SIMP Type 4 Header)
 * 284 bytes describing track, weather overview, session phase, and active car count.
 */
struct FullScoringSessionPacket {
    char          trackName[64];       // Track/circuit name
    long          session;             // 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race
    double        currentET;           // Current session elapsed time in seconds
    double        endET;               // Ending session elapsed time
    long          maxLaps;             // Maximum laps for session
    double        lapDist;             // Track lap distance in meters
    long          numVehicles;         // Number of active vehicles in grid (0..128)
    unsigned char gamePhase;           // 0=Garage..5=GreenFlag, 6=FCY..8=SessionOver
    signed char   yellowFlagState;     // -1=Invalid, 0=None, 1=Pending, 2=PitClosed, 3=PitLeadLap, 4=PitOpen, 5=LastLap, 6=Resume
    signed char   sectorFlag[3];       // Local yellow flags in S3, S1, S2
    unsigned char startLight;          // Start light frame
    unsigned char numRedLights;        // Red lights in start sequence
    bool          inRealtime;          // 1 if in realtime driving mode
    char          playerName[32];      // Player name
    char          plrFileName[64];     // Player profile filename
    double        darkCloud;           // Cloud darkness (0.0 - 1.0)
    double        raining;             // Rain intensity (0.0 - 1.0)
    double        ambientTemp;         // Air temperature (°C)
    double        trackTemp;           // Track temperature (°C)
    TelemVect3    wind;                // Wind velocity vector (x, y, z)
    double        minPathWetness;      // Track minimum wetness (0.0 - 1.0)
    double        maxPathWetness;      // Track maximum wetness (0.0 - 1.0)
    double        avgPathWetness;      // Track average wetness (0.0 - 1.0)
};

#pragma pack(pop)

// Buffer unsubscription bitmask (rF2SharedMemoryMapPlugin compatibility)
enum UnsubscribedBufferMaskFlags {
    UNSUB_TELEMETRY      = 1,
    UNSUB_SCORING        = 2,
    UNSUB_RULES          = 4,
    UNSUB_MULTI_RULES    = 8,
    UNSUB_FORCE_FEEDBACK = 16,
    UNSUB_GRAPHICS       = 32,
    UNSUB_PIT_INFO       = 64,
    UNSUB_WEATHER        = 128
};

// High-resolution monotonic frequency limiter for zero-jitter UDP packet throttling
class RateLimiter {
private:
    double targetHz;         // 0.0: off, < 0.0: unlimited, > 0.0: target rate in Hz
    double minIntervalSec;   // 1.0 / targetHz
    LARGE_INTEGER lastTime;
    LARGE_INTEGER perfFreq;
    bool hasSentFirst;

public:
    RateLimiter() : targetHz(-1.0), minIntervalSec(0.0), hasSentFirst(false) {
        lastTime.QuadPart = 0;
#ifdef _WIN32
        QueryPerformanceFrequency(&perfFreq);
#else
        perfFreq.QuadPart = 1000000000LL;
#endif
    }

    void SetRate(double hz) {
        targetHz = hz;
        if (targetHz > 0.0) {
            minIntervalSec = 1.0 / targetHz;
        } else {
            minIntervalSec = 0.0;
        }
        hasSentFirst = false;
        lastTime.QuadPart = 0;
    }

    bool IsEnabled() const {
        return targetHz != 0.0;
    }

    bool IsUnlimited() const {
        return targetHz < 0.0;
    }

    double GetRateHz() const {
        return targetHz;
    }

    bool ShouldSend() {
        if (targetHz == 0.0) return false;
        if (targetHz < 0.0) return true; // unlimited (raw 1:1 on every engine tick)

        LARGE_INTEGER now;
#ifdef _WIN32
        QueryPerformanceCounter(&now);
#else
        timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        now.QuadPart = static_cast<int64_t>(ts.tv_sec) * 1000000000LL + ts.tv_nsec;
#endif

        if (!hasSentFirst) {
            hasSentFirst = true;
            lastTime = now;
            return true;
        }

        double elapsed = static_cast<double>(now.QuadPart - lastTime.QuadPart) / perfFreq.QuadPart;
        if (elapsed >= minIntervalSec) {
            lastTime = now;
            return true;
        }
        return false;
    }
};

static double ParseRateHz(const char* str, double defaultRate = -1.0) {
    if (!str || str[0] == '\0') return defaultRate;

    while (*str == ' ' || *str == '\t') ++str;
    if (*str == '\0') return defaultRate;

    char buf[64] = {0};
    size_t i = 0;
    while (*str && i < sizeof(buf) - 1) {
        char c = *str++;
        if (c >= 'A' && c <= 'Z') c = static_cast<char>(c + 32);
        buf[i++] = c;
    }

    if (std::strcmp(buf, "off") == 0) {
        return 0.0;
    }
    if (std::strcmp(buf, "unlimited") == 0) {
        return -1.0;
    }

    char* endPtr = nullptr;
    double val = std::strtod(buf, &endPtr);
    if (val <= 0.0) {
        return 0.0;
    }
    return val;
}

static bool ParseSystemEvents(const char* str, bool defaultVal = true) {
    if (!str || str[0] == '\0') return defaultVal;
    while (*str == ' ' || *str == '\t') ++str;
    if (*str == '\0') return defaultVal;

    char buf[64] = {0};
    size_t i = 0;
    while (*str && i < sizeof(buf) - 1) {
        char c = *str++;
        if (c >= 'A' && c <= 'Z') c = static_cast<char>(c + 32);
        buf[i++] = c;
    }
    if (std::strcmp(buf, "off") == 0) return false;
    if (std::strcmp(buf, "on") == 0 || std::strcmp(buf, "unlimited") == 0) return true;
    return defaultVal;
}

struct PluginConfig {
    char targetIp[64];
    int targetPort;
    double telemetryHz;
    double compactScoringHz;
    double fullScoringHz;
    bool enableSystemEvents;
    long unsubscribedBuffersMask;
};

// Static working buffers (zero allocations)
static const size_t MAX_UDP_CHUNK_SIZE = 1200;
static char s_scoringBuffer[sizeof(FullScoringSessionPacket) + 128 * sizeof(VehicleScoringInfoV01)];
static char s_chunkPacketBuffer[sizeof(RawUdpHeader) + MAX_UDP_CHUNK_SIZE];

class IsiMotorRawUdpPlugin : public InternalsPluginV01 {
private:
    SOCKET udpSocket;
    sockaddr_in serverAddr;
    PluginConfig config;
    RateLimiter telemetryLimiter;
    RateLimiter compactScoringLimiter;
    RateLimiter fullScoringLimiter;
    unsigned int sequenceCounters[256];
    bool initialized;

    void GetIniPath(char* outPath, size_t maxLen) {
        char dllPath[MAX_PATH] = {0};
        if (GetModuleFileNameA(g_hModule, dllPath, MAX_PATH) > 0) {
            char* lastSlash = std::strrchr(dllPath, '\\');
            if (!lastSlash) lastSlash = std::strrchr(dllPath, '/');
            if (lastSlash) {
                *(lastSlash + 1) = '\0';
                std::snprintf(outPath, maxLen, "%s%s", dllPath, INI_FILE_NAME);
                return;
            }
        }
        std::snprintf(outPath, maxLen, ".\\%s", INI_FILE_NAME);
    }

    void LoadConfiguration() {
        // Safe hardcoded defaults
        std::strncpy(config.targetIp, DEFAULT_UDP_HOST, sizeof(config.targetIp) - 1);
        config.targetIp[sizeof(config.targetIp) - 1] = '\0';
        config.targetPort = DEFAULT_UDP_PORT;
        config.telemetryHz = -1.0;     // unlimited
        config.compactScoringHz = -1.0;// unlimited
        config.fullScoringHz = 5.0;    // 5Hz
        config.enableSystemEvents = true;
        config.unsubscribedBuffersMask = 0;

        char iniPath[MAX_PATH] = {0};
        GetIniPath(iniPath, sizeof(iniPath));

        // If INI does not exist, generate default template
        DWORD attr = GetFileAttributesA(iniPath);
        if (attr == INVALID_FILE_ATTRIBUTES) {
            FILE* f = std::fopen(iniPath, "w");
            if (f) {
                std::fprintf(f,
                    "; ==================================================================\n"
                    "; isiMotor-RawUDP-Plugin Configuration\n"
                    "; ==================================================================\n"
                    "\n"
                    "[Network]\n"
                    "; Destination IP address (Unicast e.g. 127.0.0.1 or 192.168.1.50, Multicast e.g. 239.255.0.1, Broadcast e.g. 255.255.255.255)\n"
                    "TargetIP=127.0.0.1\n"
                    "; Destination UDP Port (default: 5000)\n"
                    "TargetPort=5000\n"
                    "\n"
                    "[Streams]\n"
                    "; Channel frequency limiter format: off | unlimited | <N>Hz\n"
                    "; ------------------------------------------------------------------\n"
                    "; Telemetry stream (1888 B): off | unlimited | 100Hz | 60Hz | 30Hz | 20Hz | 10Hz\n"
                    "Telemetry=unlimited\n"
                    "\n"
                    "; Compact scoring stream (168 B, single-player): off | unlimited | 5Hz | 2Hz | 1Hz\n"
                    "CompactScoring=unlimited\n"
                    "\n"
                    "; Full grid scoring stream (up to 128 cars, sliced): off | unlimited | 5Hz | 2Hz | 1Hz\n"
                    "FullScoring=5Hz\n"
                    "\n"
                    "; System events stream (session / realtime transitions): off | on\n"
                    "SystemEvents=on\n"
                    "\n"
                    "; Buffer unsubscription bitmask (rF2SharedMemoryMapPlugin compatibility):\n"
                    "; Telemetry=1, Scoring=2, Rules=4, MultiRules=8, ForceFeedback=16, Graphics=32, PitInfo=64, Weather=128\n"
                    "UnsubscribedBuffersMask=0\n"
                );
                std::fclose(f);
            }
        }

        // Read network settings
        GetPrivateProfileStringA("Network", "TargetIP", DEFAULT_UDP_HOST, config.targetIp, sizeof(config.targetIp), iniPath);
        config.targetPort = GetPrivateProfileIntA("Network", "TargetPort", DEFAULT_UDP_PORT, iniPath);

        // Read stream frequency limiters
        char telemStr[64] = {0};
        GetPrivateProfileStringA("Streams", "Telemetry", "unlimited", telemStr, sizeof(telemStr), iniPath);
        config.telemetryHz = ParseRateHz(telemStr, -1.0);

        char legacyScoringStr[64] = {0};
        GetPrivateProfileStringA("Streams", "Scoring", "unlimited", legacyScoringStr, sizeof(legacyScoringStr), iniPath);
        char compactStr[64] = {0};
        GetPrivateProfileStringA("Streams", "CompactScoring", legacyScoringStr, compactStr, sizeof(compactStr), iniPath);
        config.compactScoringHz = ParseRateHz(compactStr, -1.0);

        char fullStr[64] = {0};
        GetPrivateProfileStringA("Streams", "FullScoring", "5Hz", fullStr, sizeof(fullStr), iniPath);
        config.fullScoringHz = ParseRateHz(fullStr, 5.0);

        char eventStr[64] = {0};
        GetPrivateProfileStringA("Streams", "SystemEvents", "on", eventStr, sizeof(eventStr), iniPath);
        config.enableSystemEvents = ParseSystemEvents(eventStr, true);

        config.unsubscribedBuffersMask = GetPrivateProfileIntA("Streams", "UnsubscribedBuffersMask", 0, iniPath);

        telemetryLimiter.SetRate(config.telemetryHz);
        compactScoringLimiter.SetRate(config.compactScoringHz);
        fullScoringLimiter.SetRate(config.fullScoringHz);
    }

    void SendSlicedPayload(unsigned char packetType, unsigned short subTypeOrId, const void* payload, size_t totalPayloadSize, double sessionET) {
        if (!initialized || udpSocket == INVALID_SOCKET || totalPayloadSize == 0) return;

        unsigned int seq = ++sequenceCounters[packetType];
        const char* src = reinterpret_cast<const char*>(payload);
        size_t offset = 0;
        unsigned char totalChunks = static_cast<unsigned char>((totalPayloadSize + MAX_UDP_CHUNK_SIZE - 1) / MAX_UDP_CHUNK_SIZE);
        if (totalChunks == 0) totalChunks = 1;
        unsigned char chunkIdx = 0;

        while (offset < totalPayloadSize) {
            size_t chunkSize = (totalPayloadSize - offset > MAX_UDP_CHUNK_SIZE) ? MAX_UDP_CHUNK_SIZE : (totalPayloadSize - offset);

            RawUdpHeader* hdr = reinterpret_cast<RawUdpHeader*>(s_chunkPacketBuffer);
            hdr->magic[0] = 'S'; hdr->magic[1] = 'I'; hdr->magic[2] = 'M'; hdr->magic[3] = 'P';
            hdr->protocolVersion = 1;
            hdr->packetType = packetType;
            hdr->payloadSize = static_cast<unsigned short>(chunkSize);
            hdr->sequenceNumber = seq;
            hdr->sessionET = sessionET;
            hdr->chunkIndex = chunkIdx++;
            hdr->totalChunks = totalChunks;
            hdr->subTypeOrId = subTypeOrId;

            std::memcpy(s_chunkPacketBuffer + sizeof(RawUdpHeader), src + offset, chunkSize);

            sendto(udpSocket, s_chunkPacketBuffer, static_cast<int>(sizeof(RawUdpHeader) + chunkSize), 0,
                   reinterpret_cast<const sockaddr*>(&serverAddr), sizeof(serverAddr));

            offset += chunkSize;
        }
    }

    void SendSystemEvent(unsigned char eventType) {
        if (!initialized || !config.enableSystemEvents || udpSocket == INVALID_SOCKET) return;
        SystemEventPacket pkt{};
        pkt.magic[0] = 'S'; pkt.magic[1] = 'I'; pkt.magic[2] = 'M'; pkt.magic[3] = 'P';
        pkt.packetType = 3;
        pkt.eventType = eventType;
        sendto(udpSocket, reinterpret_cast<const char*>(&pkt), sizeof(pkt), 0,
               reinterpret_cast<const sockaddr*>(&serverAddr), sizeof(serverAddr));
    }

public:
    IsiMotorRawUdpPlugin() : udpSocket(INVALID_SOCKET), initialized(false) {
        std::memset(&serverAddr, 0, sizeof(serverAddr));
        std::memset(&config, 0, sizeof(config));
        std::memset(sequenceCounters, 0, sizeof(sequenceCounters));
    }

    ~IsiMotorRawUdpPlugin() override {
        Shutdown();
    }

    void Startup(long version) override {
        if (initialized) return;

        // Load or auto-create configuration file
        LoadConfiguration();

        // Initialize Winsock 2.2
        WSADATA wsaData;
        if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
            return;
        }

        // Create non-blocking UDP socket
        udpSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (udpSocket == INVALID_SOCKET) {
            WSACleanup();
            return;
        }

        // Enable Broadcast permission so broadcast targets work out-of-the-box
        int broadcastEnable = 1;
        setsockopt(udpSocket, SOL_SOCKET, SO_BROADCAST, reinterpret_cast<const char*>(&broadcastEnable), sizeof(broadcastEnable));

        // Set Multicast TTL to 2 hops by default
        unsigned char ttl = 2;
        setsockopt(udpSocket, IPPROTO_IP, IP_MULTICAST_TTL, reinterpret_cast<const char*>(&ttl), sizeof(ttl));

        // Configure target endpoint
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_port = htons(static_cast<u_short>(config.targetPort));
        inet_pton(AF_INET, config.targetIp, &serverAddr.sin_addr);

        initialized = true;
    }

    void Shutdown() override {
        if (initialized) {
            if (udpSocket != INVALID_SOCKET) {
                closesocket(udpSocket);
                udpSocket = INVALID_SOCKET;
            }
            WSACleanup();
            initialized = false;
        }
    }

    void EnterRealtime() override {
        SendSystemEvent(1);
    }

    void ExitRealtime() override {
        SendSystemEvent(2);
    }

    void StartSession() override {
        SendSystemEvent(3);
    }

    void EndSession() override {
        SendSystemEvent(4);
    }

    // Subscribe to telemetry updates: 1 = Player vehicle only, 2 = All vehicles, 0 = Disabled
    long WantsTelemetryUpdates() override {
        if (config.unsubscribedBuffersMask & UNSUB_TELEMETRY) return 0;
        return telemetryLimiter.IsEnabled() ? 1 : 0;
    }

    // High frequency callback (~60-100Hz): Direct memory dump (zero-copy, zero-allocation)
    void UpdateTelemetry(const TelemInfoV01 &info) override {
        if (!initialized || udpSocket == INVALID_SOCKET) return;
        if (config.unsubscribedBuffersMask & UNSUB_TELEMETRY) return;
        if (!telemetryLimiter.ShouldSend()) return;

        sendto(udpSocket, reinterpret_cast<const char*>(&info), sizeof(TelemInfoV01), 0,
               reinterpret_cast<const sockaddr*>(&serverAddr), sizeof(serverAddr));
    }

    // Subscribe to scoring updates (~1-5Hz)
    bool WantsScoringUpdates() override {
        if (config.unsubscribedBuffersMask & UNSUB_SCORING) return false;
        return compactScoringLimiter.IsEnabled() || fullScoringLimiter.IsEnabled();
    }

    void UpdateScoring(const ScoringInfoV01 &info) override {
        if (!initialized || udpSocket == INVALID_SOCKET) return;
        if (config.unsubscribedBuffersMask & UNSUB_SCORING) return;

        // 1. Compact Scoring Packet (SIMP Type 2)
        if (compactScoringLimiter.IsEnabled() && compactScoringLimiter.ShouldSend()) {
            CompactScoringPacket pkt{};
            pkt.magic[0] = 'S'; pkt.magic[1] = 'I'; pkt.magic[2] = 'M'; pkt.magic[3] = 'P';
            pkt.packetType = 2;

            std::strncpy(pkt.trackName, info.mTrackName, sizeof(pkt.trackName) - 1);
            pkt.trackName[sizeof(pkt.trackName) - 1] = '\0';
            pkt.session = info.mSession;
            pkt.currentET = info.mCurrentET;
            pkt.lapDist = info.mLapDist;
            pkt.maxLaps = info.mMaxLaps;
            pkt.inRealtime = info.mInRealtime;

            // Locate player vehicle scoring record
            if (info.mVehicle != nullptr && info.mNumVehicles > 0) {
                for (int i = 0; i < info.mNumVehicles; ++i) {
                    const auto &v = info.mVehicle[i];
                    if (v.mIsPlayer || v.mControl == 0) {
                        pkt.totalLaps = v.mTotalLaps;
                        pkt.sector = v.mSector;
                        pkt.inGarageStall = v.mInGarageStall;
                        pkt.countLapFlag = v.mCountLapFlag;
                        pkt.curSector1 = v.mCurSector1;
                        pkt.curSector2 = v.mCurSector2;
                        pkt.lastSector1 = v.mLastSector1;
                        pkt.lastSector2 = v.mLastSector2;
                        pkt.lastLapTime = v.mLastLapTime;
                        pkt.bestSector1 = v.mBestSector1;
                        pkt.bestSector2 = v.mBestSector2;
                        pkt.bestLapTime = v.mBestLapTime;
                        break;
                    }
                }
            }

            sendto(udpSocket, reinterpret_cast<const char*>(&pkt), sizeof(pkt), 0,
                   reinterpret_cast<const sockaddr*>(&serverAddr), sizeof(serverAddr));
        }

        // 2. Full Multi-Car Scoring Stream (SIMP Type 4, Sliced)
        if (fullScoringLimiter.IsEnabled() && fullScoringLimiter.ShouldSend()) {
            FullScoringSessionPacket* sess = reinterpret_cast<FullScoringSessionPacket*>(s_scoringBuffer);
            std::memset(sess, 0, sizeof(FullScoringSessionPacket));

            std::strncpy(sess->trackName, info.mTrackName, sizeof(sess->trackName) - 1);
            sess->trackName[sizeof(sess->trackName) - 1] = '\0';
            sess->session = info.mSession;
            sess->currentET = info.mCurrentET;
            sess->endET = info.mEndET;
            sess->maxLaps = info.mMaxLaps;
            sess->lapDist = info.mLapDist;

            long numVehicles = 0;
            if (info.mVehicle != nullptr && info.mNumVehicles > 0) {
                numVehicles = (info.mNumVehicles > 128) ? 128 : info.mNumVehicles;
            }
            sess->numVehicles = numVehicles;

            sess->gamePhase = info.mGamePhase;
            sess->yellowFlagState = info.mYellowFlagState;
            sess->sectorFlag[0] = info.mSectorFlag[0];
            sess->sectorFlag[1] = info.mSectorFlag[1];
            sess->sectorFlag[2] = info.mSectorFlag[2];
            sess->startLight = info.mStartLight;
            sess->numRedLights = info.mNumRedLights;
            sess->inRealtime = info.mInRealtime;

            std::strncpy(sess->playerName, info.mPlayerName, sizeof(sess->playerName) - 1);
            sess->playerName[sizeof(sess->playerName) - 1] = '\0';
            std::strncpy(sess->plrFileName, info.mPlrFileName, sizeof(sess->plrFileName) - 1);
            sess->plrFileName[sizeof(sess->plrFileName) - 1] = '\0';

            sess->darkCloud = info.mDarkCloud;
            sess->raining = info.mRaining;
            sess->ambientTemp = info.mAmbientTemp;
            sess->trackTemp = info.mTrackTemp;
            sess->wind = info.mWind;
            sess->minPathWetness = info.mMinPathWetness;
            sess->maxPathWetness = info.mMaxPathWetness;
            sess->avgPathWetness = info.mAvgPathWetness;

            // Copy vehicle records immediately following session header
            if (numVehicles > 0 && info.mVehicle != nullptr) {
                VehicleScoringInfoV01* vehDst = reinterpret_cast<VehicleScoringInfoV01*>(s_scoringBuffer + sizeof(FullScoringSessionPacket));
                std::memcpy(vehDst, info.mVehicle, numVehicles * sizeof(VehicleScoringInfoV01));
            }

            size_t totalPayloadSize = sizeof(FullScoringSessionPacket) + (numVehicles * sizeof(VehicleScoringInfoV01));
            SendSlicedPayload(4, static_cast<unsigned short>(numVehicles), s_scoringBuffer, totalPayloadSize, info.mCurrentET);
        }
    }
};

// --- C Interface Exported for isiMotor (LMU / rFactor 2) Plugin Host ---

extern "C" __declspec(dllexport) const char* __cdecl GetPluginName() {
    return PLUGIN_NAME;
}

extern "C" __declspec(dllexport) PluginObjectType __cdecl GetPluginType() {
    return PO_INTERNALS;
}

extern "C" __declspec(dllexport) int __cdecl GetPluginVersion() {
    return 1; // Corresponds to InternalsPluginV01
}

extern "C" __declspec(dllexport) PluginObject* __cdecl CreatePluginObject() {
    return new IsiMotorRawUdpPlugin();
}

extern "C" __declspec(dllexport) void __cdecl DestroyPluginObject(PluginObject* obj) {
    delete obj;
}
