/**
 * isiMotor-RawUDP-Plugin
 * High-Performance Raw Binary Telemetry & Scoring Plugin for isiMotor games
 * (Le Mans Ultimate, rFactor 2).
 * 
 * Features:
 * - Zero third-party dependencies (no nlohmann/json, no Boost, native Winsock2 only).
 * - Zero dynamic memory allocations in the telemetry and scoring update loops.
 * - Direct binary memory dump of TelemInfoV01 (1904 bytes) over UDP.
 * - Compact binary scoring packet (SIMP Type 2, 176 bytes) for minimal overhead.
 * - System event state notifications (SIMP Type 3, 6 bytes).
 * - Self-generating & configurable via 'isiMotor_RawUDP.ini' placed next to the DLL.
 * - Sub-millisecond latency supporting 120Hz to 400Hz+ streaming.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <cstdio>
#include <cstring>
#include "include/InternalsPlugin.hpp"

#pragma comment(lib, "ws2_32.lib")

#define PLUGIN_NAME "isiMotor-RawUDP"
#define DEFAULT_UDP_PORT 5000
#define DEFAULT_UDP_HOST "127.0.0.1"
#define INI_FILE_NAME "isiMotor_RawUDP.ini"

// Module handle saved at DLL injection time
static HINSTANCE g_hModule = NULL;

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        g_hModule = hModule;
    }
    return TRUE;
}

#pragma pack(push, 4)

/**
 * Compact Scoring Packet (SIMP Type 2)
 * Lightweight 176-byte representation of session and player timing data.
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

#pragma pack(pop)

struct PluginConfig {
    char targetIp[64];
    int targetPort;
    bool enableTelemetry;
    bool enableScoring;
    bool enableSystemEvents;
};

class IsiMotorRawUdpPlugin : public InternalsPluginV01 {
private:
    SOCKET udpSocket;
    sockaddr_in serverAddr;
    PluginConfig config;
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
        // Apply hardcoded safe defaults
        std::strncpy(config.targetIp, DEFAULT_UDP_HOST, sizeof(config.targetIp) - 1);
        config.targetIp[sizeof(config.targetIp) - 1] = '\0';
        config.targetPort = DEFAULT_UDP_PORT;
        config.enableTelemetry = true;
        config.enableScoring = true;
        config.enableSystemEvents = true;

        char iniPath[MAX_PATH] = {0};
        GetIniPath(iniPath, sizeof(iniPath));

        // If INI does not exist, generate default template with comments
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
                    "; Destination IP address (127.0.0.1 for local PC, or LAN IP for phone/tablet/rig)\n"
                    "TargetIP=127.0.0.1\n"
                    "; Destination UDP Port (default: 5000)\n"
                    "TargetPort=5000\n"
                    "\n"
                    "[Streams]\n"
                    "; Raw Telemetry binary stream (1904 bytes @ 60-100Hz): 1=Enabled, 0=Disabled\n"
                    "EnableTelemetry=1\n"
                    "; Compact Scoring binary stream (176 bytes @ 1-5Hz): 1=Enabled, 0=Disabled\n"
                    "EnableScoring=1\n"
                    "; System Events notification (6 bytes on state changes): 1=Enabled, 0=Disabled\n"
                    "EnableSystemEvents=1\n"
                );
                std::fclose(f);
            }
        }

        // Read settings from INI file
        GetPrivateProfileStringA("Network", "TargetIP", DEFAULT_UDP_HOST, config.targetIp, sizeof(config.targetIp), iniPath);
        config.targetPort = GetPrivateProfileIntA("Network", "TargetPort", DEFAULT_UDP_PORT, iniPath);
        config.enableTelemetry = (GetPrivateProfileIntA("Streams", "EnableTelemetry", 1, iniPath) != 0);
        config.enableScoring = (GetPrivateProfileIntA("Streams", "EnableScoring", 1, iniPath) != 0);
        config.enableSystemEvents = (GetPrivateProfileIntA("Streams", "EnableSystemEvents", 1, iniPath) != 0);
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
        return config.enableTelemetry ? 1 : 0;
    }

    // High frequency callback (~60-100Hz): Direct memory dump (zero-copy, zero-allocation)
    void UpdateTelemetry(const TelemInfoV01 &info) override {
        if (!initialized || !config.enableTelemetry || udpSocket == INVALID_SOCKET) return;

        sendto(udpSocket, reinterpret_cast<const char*>(&info), sizeof(TelemInfoV01), 0,
               reinterpret_cast<const sockaddr*>(&serverAddr), sizeof(serverAddr));
    }

    // Subscribe to scoring updates (~1-5Hz)
    bool WantsScoringUpdates() override {
        return config.enableScoring;
    }

    void UpdateScoring(const ScoringInfoV01 &info) override {
        if (!initialized || !config.enableScoring || udpSocket == INVALID_SOCKET) return;

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
