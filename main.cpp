/**
 * isiMotor-RawUDP-Plugin
 * High-Performance Raw Binary Telemetry & Multi-Car Scoring Plugin for isiMotor games
 * (Le Mans Ultimate, rFactor 2).
 * 
 * Copyright 2026 Marc GARDENT
 * Licensed under the Apache License, Version 2.0.
 * 
 * Features:
 * - Zero third-party dependencies (no nlohmann/json, no Boost, native Winsock2 only).
 * - Zero dynamic memory allocations in high-frequency telemetry and scoring update loops.
 * - Standardized 24-byte UDP header with monotonic sequence numbering and chunk slicing.
 * - Direct binary memory dump of TelemInfoV01 (1888 bytes) over UDP.
 * - Multi-vehicle full scoring stream (up to 128 vehicles, ScoringInfoV01 + VehicleScoringInfoV01).
 * - Track rules, flags, and Safety Car / FCY stream (TrackRulesV01, Type 5).
 * - Pit Menu navigation & strategy stream (PitMenuV01, Type 6 @ 100Hz).
 * - Weather & ambient conditions stream (WeatherControlInfoV01, Type 7 @ 1Hz).
 * - Compact binary scoring packet (SIMP Type 2, 168 bytes) for ultra-low overhead HUDs.
 * - System event state notifications (SIMP Type 3, 6 bytes).
 * - UnsubscribedBuffersMask support matching rF2SharedMemoryMapPlugin.
 * - Standard isiMotor configuration via CustomPluginVariables.JSON (InternalsPluginV07).
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
#include <fcntl.h>
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
    unsigned char packetType;        // 1=Telem, 2=CompactScoring, 3=Event, 4=FullScoring, 5=Rules, 6=PitMenu, 7=Weather
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

/**
 * Track Rules Participant (SIMP Type 5 Participant, 140 bytes)
 */
struct TrackRulesParticipantPacket {
    long          id;                        // Slot ID
    short         frozenOrder;               // 0-based place when caution was called
    short         place;                     // 1-based place
    float         yellowSeverity;            // Rating of yellow flag contribution
    double        currentRelativeDistance;   // Distance relative to track start/SC
    long          relativeLaps;              // Laps relative to safety car
    long          columnAssignment;          // 0=left, 1=midleft, 2=middle, 3=midright, 4=right, 5=invalid, 6=freechoice, 7=pending
    long          positionAssignment;        // 0-based position within column (-1=invalid)
    unsigned char pitsOpen;                  // 0=closed, 1=open, 2=false, 3=true
    bool          upToSpeed;                 // Vehicle can be followed
    unsigned char pad[2];
    double        goalRelativeDistance;      // Target distance behind leader
    char          message[96];               // Participant message
};

/**
 * Track Rules Session Header (SIMP Type 5 Header, 192 bytes)
 */
struct TrackRulesSessionPacket {
    double        currentET;                 // Current session time
    long          stage;                     // 0=formation_init, 1=formation_update, 2=normal, 3=caution_init, 4=caution_update
    long          poleColumn;                // 0=left..4=right
    long          numActions;                // Recent actions count
    long          numParticipants;           // Active participant count (0..128)
    bool          yellowFlagDetected;        // Caution requested or threshold exceeded
    unsigned char yellowFlagLapsWasOverridden; // Admin override flag
    bool          safetyCarExists;           // SC exists
    bool          safetyCarActive;           // SC on track
    long          safetyCarLaps;             // SC laps count
    float         safetyCarThreshold;        // SC yellow threshold
    double        safetyCarLapDist;          // SC current track lap distance
    float         safetyCarLapDistAtStart;   // SC start position
    float         pitLaneStartDist;          // Pit entrance dist
    float         teleportLapDist;           // Green flag reference dist
    signed char   yellowFlagState;           // Yellow flag state
    short         yellowFlagLaps;            // Caution laps count
    unsigned char pad1;
    long          safetyCarInstruction;      // 0=none, 1=active, 2=head for pits
    float         safetyCarSpeed;            // Max SC speed m/s
    float         safetyCarMinimumSpacing;   // SC min spacing
    float         safetyCarMaximumSpacing;   // SC max spacing
    float         minimumColumnSpacing;      // Column min spacing
    float         maximumColumnSpacing;      // Column max spacing
    float         minimumSpeed;              // Min speed
    float         maximumSpeed;              // Max speed
    char          message[96];               // Global session message
};

/**
 * Pit Menu State Packet (SIMP Type 6, 76 bytes)
 */
struct PitMenuPacket {
    long          categoryIndex;             // Current category index
    char          categoryName[32];          // Category name (e.g. "Tires", "Fuel")
    long          choiceIndex;               // Current choice index
    char          choiceString[32];          // Choice string (e.g. "Soft Slick", "+35 L")
    long          numChoices;                // Total available choices in category
};

/**
 * Weather Conditions Packet (SIMP Type 7, 108 bytes)
 */
struct WeatherPacket {
    double        et;                        // Effective session ET
    double        raining[3][3];             // Rain intensity grid
    double        cloudiness;                // Cloud cover (0.0 - 1.0)
    double        ambientTempK;              // Ambient temperature (Kelvin)
    double        windMaxSpeed;              // Wind speed (m/s)
    bool          applyCloudinessInstantly;  // Instant cloud application flag
    unsigned char pad[3];
};

/**
 * Extended State Packet (SIMP Type 8, 68 bytes)
 * Driving aids, physics multipliers, accumulated damage & session state.
 */
struct ExtendedStatePacket {
    // Physics options (40 bytes)
    unsigned char tractionControl;          // 0 (off) - 3 (high)
    unsigned char antiLockBrakes;           // 0 (off) - 2 (high)
    unsigned char stabilityControl;         // 0 (off) - 2 (high)
    unsigned char autoShift;                // 0 (off), 1 (upshifts), 2 (downshifts), 3 (all)
    unsigned char autoClutch;               // 0 (off), 1 (on)
    unsigned char invulnerable;             // 0 (off), 1 (on)
    unsigned char oppositeLock;             // 0 (off), 1 (on)
    unsigned char steeringHelp;             // 0 (off) - 3 (high)
    unsigned char brakingHelp;              // 0 (off) - 2 (high)
    unsigned char spinRecovery;             // 0 (off), 1 (on)
    unsigned char autoPit;                  // 0 (off), 1 (on)
    unsigned char autoLift;                 // 0 (off), 1 (on)
    unsigned char autoBlip;                 // 0 (off), 1 (on)
    unsigned char fuelMult;                 // fuel multiplier (0x-7x)
    unsigned char tireMult;                 // tire wear multiplier (0x-7x)
    unsigned char mechFail;                 // mechanical failure (0=off, 1=normal, 2=timescaled)
    unsigned char allowPitcrewPush;         // 0 (off), 1 (on)
    unsigned char repeatShifts;             // accidental repeat shift prevention (0-5)
    unsigned char holdClutch;               // 0 (off), 1 (on)
    unsigned char autoReverse;              // 0 (off), 1 (on)
    unsigned char alternateNeutral;         // 0 (off), 1 (on)
    unsigned char aiControl;                // 0 (player), 1 (AI)
    unsigned char pad1[2];
    float         manualShiftOverrideTime;  // time before auto-shift can resume
    float         autoShiftOverrideTime;    // time before manual shift can resume
    float         speedSensitiveSteering;   // 0.0 (off) - 1.0
    float         steerRatioSpeed;          // speed (m/s) under which lock expands
    
    // Accumulated damage tracking (16 bytes)
    double        maxImpactMagnitude;       // Max collision impact recorded in session
    double        accumulatedImpactMagnitude;// Cumulative collision damage energy

    // Session status & transitions (12 bytes)
    bool          inRealtimeFC;             // In realtime cockpit mode
    bool          sessionStarted;           // Session started flag
    unsigned char pad2[2];
    long          session;                  // Current session index
    float         currentPitSpeedLimit;     // Pit speed limit m/s
};

/**
 * Force Feedback Packet (SIMP Type 9, 8 bytes)
 * Ultra-high frequency steering shaft force feedback torque.
 */
struct ForceFeedbackPacket {
    double forceValue;                     // Steering shaft torque value
};

/**
 * Graphics & Camera Packet (SIMP Type 10, 128 bytes)
 * Camera world position, orientation matrix & ambient lighting.
 */
struct GraphicsPacket {
    TelemVect3 camPos;                     // Camera 3D world position
    TelemVect3 camOri[3];                  // Camera 3x3 orientation matrix
    double     ambientRed;                 // Ambient light RGB
    double     ambientGreen;
    double     ambientBlue;
    long       slotId;                     // Slot ID being viewed (-1 if none)
    long       cameraType;                 // Camera viewpoint type
};

/**
 * Hardware & Pit Menu Control Command (SIMP Type 100, 44 bytes padded)
 * Inbound UDP command to trigger car/cockpit/pit menu inputs.
 */
struct HWControlCommandPacket {
    char          controlName[32];       // Control name (e.g. "PitMenuUp", "PitMenuSelect", "TCIncrease")
    double        controlValue;          // 1.0 = press/on, 0.0 = release/off, or analog value
    unsigned short durationMs;           // Pulse duration in ms (e.g. 50ms)
    unsigned char pad[2];                // Explicit 4-byte struct padding
};

/**
 * Dynamic Weather Control Injection (SIMP Type 101, 64 bytes)
 * Inbound UDP command to inject ambient weather into live session.
 */
struct WeatherControlCommandPacket {
    double        ambientTemp;           // Air temp in °C
    double        trackTemp;             // Track surface temp in °C
    double        darkCloud;             // 0.0 to 1.0
    double        raining;               // 0.0 to 1.0
    double        windSpeed;             // Wind speed in m/s
    double        windDirection;         // Wind direction in radians
    double        minPathWetness;        // 0.0 to 1.0
    double        maxPathWetness;        // 0.0 to 1.0
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

struct PluginConfig {
    char targetIp[64];
    int targetPort;
    int inboundPort;
    bool enableInboundControl;
    double telemetryHz;
    double compactScoringHz;
    double fullScoringHz;
    double trackRulesHz;
    double pitMenuHz;
    double weatherHz;
    double extendedStateHz;
    double forceFeedbackHz;
    double graphicsHz;
    bool enableSystemEvents;
    long unsubscribedBuffersMask;
};

// Static working buffers (zero dynamic allocations)
static const size_t MAX_UDP_CHUNK_SIZE = 1200;
static char s_scoringBuffer[sizeof(FullScoringSessionPacket) + 128 * sizeof(VehicleScoringInfoV01)];
static char s_trackRulesBuffer[sizeof(TrackRulesSessionPacket) + 128 * sizeof(TrackRulesParticipantPacket)];
static char s_chunkPacketBuffer[sizeof(RawUdpHeader) + MAX_UDP_CHUNK_SIZE];

class IsiMotorRawUdpPlugin : public InternalsPluginV07 {
private:
    SOCKET udpSocket;
    SOCKET inboundSocket;
    sockaddr_in serverAddr;
    sockaddr_in inboundAddr;
    PluginConfig config;
    RateLimiter telemetryLimiter;
    RateLimiter compactScoringLimiter;
    RateLimiter fullScoringLimiter;
    RateLimiter trackRulesLimiter;
    RateLimiter pitMenuLimiter;
    RateLimiter weatherLimiter;
    RateLimiter extendedStateLimiter;
    RateLimiter forceFeedbackLimiter;
    RateLimiter graphicsLimiter;
    unsigned int sequenceCounters[256];
    bool initialized;

    // Inbound Hardware & Pit Menu Controls (FR-07)
    struct ActiveHWControl {
        char controlName[32];
        double value;
        double remainingTimeSec;
        bool active;
    };
    static const int MAX_ACTIVE_HW_CONTROLS = 32;
    ActiveHWControl activeControls[MAX_ACTIVE_HW_CONTROLS];

    // Inbound Dynamic Weather Override (FR-07)
    struct WeatherOverrideState {
        bool active;
        WeatherControlCommandPacket data;
    };
    WeatherOverrideState weatherOverride;

    // Tracked state for ExtendedStatePacket (FR-05)
    PhysicsOptionsV01 cachedPhysics;
    double maxImpactMagnitude;
    double accumulatedImpactMagnitude;
    bool inRealtimeFC;
    bool sessionStarted;
    long currentSession;
    float currentPitSpeedLimit;

    // -------------------------------------------------------------------------
    // Custom Plugin Variables Table & Metadata (InternalsPluginV07 String Standard API)
    // -------------------------------------------------------------------------
    struct CustomVarDef {
        const char* caption;
        const char* defaultValue;
    };

    static inline void TrimString(const char* src, char* dst, size_t maxLen) {
        if (!src || !dst || maxLen == 0) return;
        while (*src == ' ' || *src == '\t' || *src == '\r' || *src == '\n' || *src == '"') ++src;
        size_t i = 0;
        while (*src && i < maxLen - 1) {
            char c = *src++;
            if (c == '"' || c == '\r' || c == '\n') break;
            dst[i++] = c;
        }
        while (i > 0 && (dst[i - 1] == ' ' || dst[i - 1] == '\t' || dst[i - 1] == '"')) {
            --i;
        }
        dst[i] = '\0';
    }

    static inline double ParseRateString(const char* str, double defaultRate) {
        if (!str || str[0] == '\0') return defaultRate;
        char clean[64] = {0};
        TrimString(str, clean, sizeof(clean));
        if (clean[0] == '\0') return defaultRate;

        char lower[64] = {0};
        for (size_t i = 0; i < sizeof(lower) - 1 && clean[i] != '\0'; ++i) {
            char c = clean[i];
            if (c >= 'A' && c <= 'Z') c = static_cast<char>(c + 32);
            lower[i] = c;
        }

        if (std::strcmp(lower, "off") == 0 || std::strcmp(lower, "disabled") == 0 || std::strcmp(lower, "0") == 0 || std::strcmp(lower, "0hz") == 0) {
            return 0.0;
        }
        if (std::strcmp(lower, "unlimited") == 0 || std::strcmp(lower, "raw") == 0 || std::strcmp(lower, "max") == 0 || std::strcmp(lower, "-1") == 0) {
            return -1.0;
        }

        char* endPtr = nullptr;
        double val = std::strtod(lower, &endPtr);
        if (val <= 0.0) return 0.0;
        return val;
    }

    static inline bool ParseBoolString(const char* str, bool defaultVal) {
        if (!str || str[0] == '\0') return defaultVal;
        char clean[64] = {0};
        TrimString(str, clean, sizeof(clean));
        if (clean[0] == '\0') return defaultVal;

        char lower[64] = {0};
        for (size_t i = 0; i < sizeof(lower) - 1 && clean[i] != '\0'; ++i) {
            char c = clean[i];
            if (c >= 'A' && c <= 'Z') c = static_cast<char>(c + 32);
            lower[i] = c;
        }

        if (std::strcmp(lower, "off") == 0 || std::strcmp(lower, "disabled") == 0 || std::strcmp(lower, "0") == 0 || std::strcmp(lower, "false") == 0) {
            return false;
        }
        if (std::strcmp(lower, "on") == 0 || std::strcmp(lower, "enabled") == 0 || std::strcmp(lower, "1") == 0 || std::strcmp(lower, "true") == 0) {
            return true;
        }
        return defaultVal;
    }

    static inline int ParseIntString(const char* str, int defaultVal) {
        if (!str || str[0] == '\0') return defaultVal;
        char clean[64] = {0};
        TrimString(str, clean, sizeof(clean));
        if (clean[0] == '\0') return defaultVal;
        char* endPtr = nullptr;
        long val = std::strtol(clean, &endPtr, 10);
        if (endPtr == clean) return defaultVal;
        return static_cast<int>(val);
    }

    static inline const CustomVarDef* GetCustomVarDefs(int& count) {
        static const CustomVarDef s_defs[] = {
            { "TargetIP",                "127.0.0.1" },
            { "TargetPort",              "5000" },
            { "InboundControl",          "Enabled" },
            { "InboundPort",             "5001" },
            { "TelemetryRate",           "unlimited" },
            { "CompactScoringRate",      "unlimited" },
            { "FullScoringRate",         "5Hz" },
            { "TrackRulesRate",          "3Hz" },
            { "PitMenuRate",             "100Hz" },
            { "WeatherRate",             "1Hz" },
            { "ExtendedStateRate",       "5Hz" },
            { "ForceFeedbackRate",       "unlimited" },
            { "GraphicsRate",            "60Hz" },
            { "SystemEvents",            "Enabled" },
            { "UnsubscribedBuffersMask", "0" }
        };
        count = static_cast<int>(sizeof(s_defs) / sizeof(s_defs[0]));
        return s_defs;
    }

    void InitDefaults() {
        std::strncpy(config.targetIp, DEFAULT_UDP_HOST, sizeof(config.targetIp) - 1);
        config.targetIp[sizeof(config.targetIp) - 1] = '\0';
        config.targetPort = DEFAULT_UDP_PORT;
        config.inboundPort = 5001;
        config.enableInboundControl = true;
        config.telemetryHz = -1.0;     // unlimited
        config.compactScoringHz = -1.0;// unlimited
        config.fullScoringHz = 5.0;    // 5Hz
        config.trackRulesHz = 3.0;     // 3Hz
        config.pitMenuHz = 100.0;      // 100Hz
        config.weatherHz = 1.0;        // 1Hz
        config.extendedStateHz = 5.0;  // 5Hz
        config.forceFeedbackHz = -1.0; // unlimited (up to 400Hz)
        config.graphicsHz = 60.0;      // 60Hz
        config.enableSystemEvents = true;
        config.unsubscribedBuffersMask = 0;

        telemetryLimiter.SetRate(config.telemetryHz);
        compactScoringLimiter.SetRate(config.compactScoringHz);
        fullScoringLimiter.SetRate(config.fullScoringHz);
        trackRulesLimiter.SetRate(config.trackRulesHz);
        pitMenuLimiter.SetRate(config.pitMenuHz);
        weatherLimiter.SetRate(config.weatherHz);
        extendedStateLimiter.SetRate(config.extendedStateHz);
        forceFeedbackLimiter.SetRate(config.forceFeedbackHz);
        graphicsLimiter.SetRate(config.graphicsHz);
    }

public:
    // -------------------------------------------------------------------------
    // InternalsPluginV07 Custom Variables Callbacks (String-Based API)
    // -------------------------------------------------------------------------

    bool GetCustomVariable(long i, CustomVariableV01 &var) override {
        int count = 0;
        const CustomVarDef* defs = GetCustomVarDefs(count);
        if (i < 0 || i >= count) return false;

        std::strncpy(var.mCaption, defs[i].caption, sizeof(var.mCaption) - 1);
        var.mCaption[sizeof(var.mCaption) - 1] = '\0';
        var.mNumSettings = 0; // 0 indicates limitless / string type in isiMotor Custom Variables API
        var.mCurrentSetting = 0;
        std::memset(var.mExpansion, 0, sizeof(var.mExpansion));
        std::strncpy(reinterpret_cast<char*>(var.mExpansion), defs[i].defaultValue, sizeof(var.mExpansion) - 1);
        return true;
    }

    void GetCustomVariableSetting(CustomVariableV01 &var, long i, CustomSettingV01 &setting) override {
        (void)var;
        (void)i;
        (void)setting;
        // Not used when mNumSettings == 0 (string type)
    }

    void AccessCustomVariable(CustomVariableV01 &var) override {
        const char* strVal = reinterpret_cast<const char*>(var.mExpansion);
        char cleanStr[128] = {0};
        if (strVal && strVal[0] != '\0') {
            TrimString(strVal, cleanStr, sizeof(cleanStr));
        }

        if (std::strcmp(var.mCaption, "TargetIP") == 0) {
            if (cleanStr[0] != '\0') {
                std::strncpy(config.targetIp, cleanStr, sizeof(config.targetIp) - 1);
                config.targetIp[sizeof(config.targetIp) - 1] = '\0';
            }
            if (initialized && udpSocket != INVALID_SOCKET) {
                inet_pton(AF_INET, config.targetIp, &serverAddr.sin_addr);
            }
        }
        else if (std::strcmp(var.mCaption, "TargetPort") == 0) {
            if (cleanStr[0] != '\0') {
                config.targetPort = ParseIntString(cleanStr, DEFAULT_UDP_PORT);
            } else if (var.mCurrentSetting > 0) {
                config.targetPort = static_cast<int>(var.mCurrentSetting);
            }
            if (initialized && udpSocket != INVALID_SOCKET) {
                serverAddr.sin_port = htons(static_cast<u_short>(config.targetPort));
            }
        }
        else if (std::strcmp(var.mCaption, "InboundControl") == 0) {
            if (cleanStr[0] != '\0') {
                config.enableInboundControl = ParseBoolString(cleanStr, true);
            } else {
                config.enableInboundControl = (var.mCurrentSetting != 0);
            }
        }
        else if (std::strcmp(var.mCaption, "InboundPort") == 0) {
            if (cleanStr[0] != '\0') {
                config.inboundPort = ParseIntString(cleanStr, 5001);
            } else if (var.mCurrentSetting > 0) {
                config.inboundPort = static_cast<int>(var.mCurrentSetting);
            }
        }
        else if (std::strcmp(var.mCaption, "TelemetryRate") == 0) {
            if (cleanStr[0] != '\0') {
                config.telemetryHz = ParseRateString(cleanStr, -1.0);
            }
            telemetryLimiter.SetRate(config.telemetryHz);
        }
        else if (std::strcmp(var.mCaption, "CompactScoringRate") == 0) {
            if (cleanStr[0] != '\0') {
                config.compactScoringHz = ParseRateString(cleanStr, -1.0);
            }
            compactScoringLimiter.SetRate(config.compactScoringHz);
        }
        else if (std::strcmp(var.mCaption, "FullScoringRate") == 0) {
            if (cleanStr[0] != '\0') {
                config.fullScoringHz = ParseRateString(cleanStr, 5.0);
            }
            fullScoringLimiter.SetRate(config.fullScoringHz);
        }
        else if (std::strcmp(var.mCaption, "TrackRulesRate") == 0) {
            if (cleanStr[0] != '\0') {
                config.trackRulesHz = ParseRateString(cleanStr, 3.0);
            }
            trackRulesLimiter.SetRate(config.trackRulesHz);
        }
        else if (std::strcmp(var.mCaption, "PitMenuRate") == 0) {
            if (cleanStr[0] != '\0') {
                config.pitMenuHz = ParseRateString(cleanStr, 100.0);
            }
            pitMenuLimiter.SetRate(config.pitMenuHz);
        }
        else if (std::strcmp(var.mCaption, "WeatherRate") == 0) {
            if (cleanStr[0] != '\0') {
                config.weatherHz = ParseRateString(cleanStr, 1.0);
            }
            weatherLimiter.SetRate(config.weatherHz);
        }
        else if (std::strcmp(var.mCaption, "ExtendedStateRate") == 0) {
            if (cleanStr[0] != '\0') {
                config.extendedStateHz = ParseRateString(cleanStr, 5.0);
            }
            extendedStateLimiter.SetRate(config.extendedStateHz);
        }
        else if (std::strcmp(var.mCaption, "ForceFeedbackRate") == 0) {
            if (cleanStr[0] != '\0') {
                config.forceFeedbackHz = ParseRateString(cleanStr, -1.0);
            }
            forceFeedbackLimiter.SetRate(config.forceFeedbackHz);
        }
        else if (std::strcmp(var.mCaption, "GraphicsRate") == 0) {
            if (cleanStr[0] != '\0') {
                config.graphicsHz = ParseRateString(cleanStr, 60.0);
            }
            graphicsLimiter.SetRate(config.graphicsHz);
        }
        else if (std::strcmp(var.mCaption, "SystemEvents") == 0) {
            if (cleanStr[0] != '\0') {
                config.enableSystemEvents = ParseBoolString(cleanStr, true);
            } else {
                config.enableSystemEvents = (var.mCurrentSetting != 0);
            }
        }
        else if (std::strcmp(var.mCaption, "UnsubscribedBuffersMask") == 0) {
            if (cleanStr[0] != '\0') {
                config.unsubscribedBuffersMask = ParseIntString(cleanStr, 0);
            } else {
                config.unsubscribedBuffersMask = var.mCurrentSetting;
            }
        }
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

    void ApplyHWControl(const char* name, double value, unsigned short durationMs) {
        if (!name || name[0] == '\0') return;

        double durationSec = (durationMs > 0) ? (durationMs / 1000.0) : 0.050; // Default 50ms pulse

        // Check if already active
        for (int i = 0; i < MAX_ACTIVE_HW_CONTROLS; ++i) {
            if (activeControls[i].active && std::strncmp(activeControls[i].controlName, name, sizeof(activeControls[i].controlName)) == 0) {
                activeControls[i].value = value;
                activeControls[i].remainingTimeSec = durationSec;
                return;
            }
        }

        // Find inactive slot
        for (int i = 0; i < MAX_ACTIVE_HW_CONTROLS; ++i) {
            if (!activeControls[i].active) {
                std::strncpy(activeControls[i].controlName, name, sizeof(activeControls[i].controlName) - 1);
                activeControls[i].controlName[sizeof(activeControls[i].controlName) - 1] = '\0';
                activeControls[i].value = value;
                activeControls[i].remainingTimeSec = durationSec;
                activeControls[i].active = true;
                return;
            }
        }
    }

    void PollInboundCommands() {
        if (!initialized || inboundSocket == INVALID_SOCKET || !config.enableInboundControl) return;

        char recvBuf[512];
        sockaddr_in clientAddr;
#ifdef _WIN32
        int addrLen = sizeof(clientAddr);
#else
        socklen_t addrLen = sizeof(clientAddr);
#endif

        while (true) {
            int bytes = recvfrom(inboundSocket, recvBuf, sizeof(recvBuf), 0,
                                 reinterpret_cast<sockaddr*>(&clientAddr), &addrLen);
            if (bytes < static_cast<int>(sizeof(RawUdpHeader))) {
                break;
            }

            const RawUdpHeader* hdr = reinterpret_cast<const RawUdpHeader*>(recvBuf);
            if (std::memcmp(hdr->magic, "SIMP", 4) != 0 || hdr->protocolVersion != 1) {
                continue;
            }

            const char* payload = recvBuf + sizeof(RawUdpHeader);
            size_t payloadSize = static_cast<size_t>(bytes - sizeof(RawUdpHeader));

            if (hdr->packetType == 100 && payloadSize >= sizeof(HWControlCommandPacket)) {
                const HWControlCommandPacket* cmd = reinterpret_cast<const HWControlCommandPacket*>(payload);
                ApplyHWControl(cmd->controlName, cmd->controlValue, cmd->durationMs);
            } else if (hdr->packetType == 101 && payloadSize >= sizeof(WeatherControlCommandPacket)) {
                const WeatherControlCommandPacket* cmd = reinterpret_cast<const WeatherControlCommandPacket*>(payload);
                weatherOverride.data = *cmd;
                weatherOverride.active = true;
            }
        }
    }

public:
    IsiMotorRawUdpPlugin() : udpSocket(INVALID_SOCKET), inboundSocket(INVALID_SOCKET), initialized(false) {
        std::memset(&serverAddr, 0, sizeof(serverAddr));
        std::memset(&inboundAddr, 0, sizeof(inboundAddr));
        std::memset(&config, 0, sizeof(config));
        std::memset(sequenceCounters, 0, sizeof(sequenceCounters));
        std::memset(activeControls, 0, sizeof(activeControls));
        std::memset(&weatherOverride, 0, sizeof(weatherOverride));
        InitDefaults();
    }

    ~IsiMotorRawUdpPlugin() override {
        Shutdown();
    }

    void Startup(long version) override {
        (void)version;
        if (initialized) return;

        // Initialize Winsock 2.2
        WSADATA wsaData;
        if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
            return;
        }

        // 1. Create outgoing UDP socket
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

        // 2. Create inbound UDP socket (FR-07 Bi-Directional Input)
        if (config.enableInboundControl) {
            inboundSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
            if (inboundSocket != INVALID_SOCKET) {
                int reuse = 1;
                setsockopt(inboundSocket, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char*>(&reuse), sizeof(reuse));
#ifdef _WIN32
                u_long nonBlocking = 1;
                ioctlsocket(inboundSocket, FIONBIO, &nonBlocking);
#else
                int flags = fcntl(inboundSocket, F_GETFL, 0);
                fcntl(inboundSocket, F_SETFL, flags | O_NONBLOCK);
#endif
                inboundAddr.sin_family = AF_INET;
                inboundAddr.sin_port = htons(static_cast<u_short>(config.inboundPort));
                inboundAddr.sin_addr.s_addr = INADDR_ANY;
                bind(inboundSocket, reinterpret_cast<const sockaddr*>(&inboundAddr), sizeof(inboundAddr));
            }
        }

        initialized = true;
        maxImpactMagnitude = 0.0;
        accumulatedImpactMagnitude = 0.0;
        inRealtimeFC = false;
        sessionStarted = false;
        currentSession = 0;
        currentPitSpeedLimit = 16.67f;
        std::memset(&cachedPhysics, 0, sizeof(cachedPhysics));
        std::memset(activeControls, 0, sizeof(activeControls));
        std::memset(&weatherOverride, 0, sizeof(weatherOverride));
    }

    void Shutdown() override {
        if (initialized) {
            if (udpSocket != INVALID_SOCKET) {
                closesocket(udpSocket);
                udpSocket = INVALID_SOCKET;
            }
            if (inboundSocket != INVALID_SOCKET) {
                closesocket(inboundSocket);
                inboundSocket = INVALID_SOCKET;
            }
            WSACleanup();
            initialized = false;
        }
    }

    void SendExtendedState(double sessionET) {
        if (!initialized || udpSocket == INVALID_SOCKET) return;
        if (!extendedStateLimiter.IsEnabled()) return;

        ExtendedStatePacket pkt{};
        // Physics options
        pkt.tractionControl = cachedPhysics.mTractionControl;
        pkt.antiLockBrakes = cachedPhysics.mAntiLockBrakes;
        pkt.stabilityControl = cachedPhysics.mStabilityControl;
        pkt.autoShift = cachedPhysics.mAutoShift;
        pkt.autoClutch = cachedPhysics.mAutoClutch;
        pkt.invulnerable = cachedPhysics.mInvulnerable;
        pkt.oppositeLock = cachedPhysics.mOppositeLock;
        pkt.steeringHelp = cachedPhysics.mSteeringHelp;
        pkt.brakingHelp = cachedPhysics.mBrakingHelp;
        pkt.spinRecovery = cachedPhysics.mSpinRecovery;
        pkt.autoPit = cachedPhysics.mAutoPit;
        pkt.autoLift = cachedPhysics.mAutoLift;
        pkt.autoBlip = cachedPhysics.mAutoBlip;
        pkt.fuelMult = cachedPhysics.mFuelMult;
        pkt.tireMult = cachedPhysics.mTireMult;
        pkt.mechFail = cachedPhysics.mMechFail;
        pkt.allowPitcrewPush = cachedPhysics.mAllowPitcrewPush;
        pkt.repeatShifts = cachedPhysics.mRepeatShifts;
        pkt.holdClutch = cachedPhysics.mHoldClutch;
        pkt.autoReverse = cachedPhysics.mAutoReverse;
        pkt.alternateNeutral = cachedPhysics.mAlternateNeutral;
        pkt.aiControl = cachedPhysics.mAIControl;
        pkt.pad1[0] = 0; pkt.pad1[1] = 0;
        pkt.manualShiftOverrideTime = cachedPhysics.mManualShiftOverrideTime;
        pkt.autoShiftOverrideTime = cachedPhysics.mAutoShiftOverrideTime;
        pkt.speedSensitiveSteering = cachedPhysics.mSpeedSensitiveSteering;
        pkt.steerRatioSpeed = cachedPhysics.mSteerRatioSpeed;

        // Damage tracking
        pkt.maxImpactMagnitude = maxImpactMagnitude;
        pkt.accumulatedImpactMagnitude = accumulatedImpactMagnitude;

        // Status
        pkt.inRealtimeFC = inRealtimeFC;
        pkt.sessionStarted = sessionStarted;
        pkt.pad2[0] = 0; pkt.pad2[1] = 0;
        pkt.session = currentSession;
        pkt.currentPitSpeedLimit = currentPitSpeedLimit;

        SendSlicedPayload(8, 0, &pkt, sizeof(pkt), sessionET);
    }

    void EnterRealtime() override {
        inRealtimeFC = true;
        SendSystemEvent(1);
        SendExtendedState(0.0);
    }

    void ExitRealtime() override {
        inRealtimeFC = false;
        SendSystemEvent(2);
        SendExtendedState(0.0);
    }

    void StartSession() override {
        sessionStarted = true;
        maxImpactMagnitude = 0.0;
        accumulatedImpactMagnitude = 0.0;
        SendSystemEvent(3);
        SendExtendedState(0.0);
    }

    void EndSession() override {
        sessionStarted = false;
        SendSystemEvent(4);
        SendExtendedState(0.0);
    }

    void SetPhysicsOptions(PhysicsOptionsV01 &options) override {
        std::memcpy(&cachedPhysics, &options, sizeof(PhysicsOptionsV01));
        SendExtendedState(0.0);
    }

    // Subscribe to telemetry updates: 1 = Player vehicle only, 2 = All vehicles, 0 = Disabled
    long WantsTelemetryUpdates() override {
        if (config.unsubscribedBuffersMask & UNSUB_TELEMETRY) return 0;
        return telemetryLimiter.IsEnabled() ? 1 : 0;
    }

    // High frequency callback (~60-100Hz): Direct memory dump (zero-copy, zero-allocation)
    void UpdateTelemetry(const TelemInfoV01 &info) override {
        if (!initialized || udpSocket == INVALID_SOCKET) return;

        // Track collision damage impacts
        if (info.mLastImpactMagnitude > 0.0) {
            if (info.mLastImpactMagnitude > maxImpactMagnitude) {
                maxImpactMagnitude = info.mLastImpactMagnitude;
            }
            accumulatedImpactMagnitude += info.mLastImpactMagnitude;
        }

        // Periodic ExtendedState stream (SIMP Type 8 @ 5Hz)
        if (extendedStateLimiter.IsEnabled() && extendedStateLimiter.ShouldSend()) {
            SendExtendedState(info.mElapsedTime);
        }

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

    // Subscribe to track rules updates (FR-03, SIMP Type 5)
    bool WantsTrackRulesAccess() override {
        if (config.unsubscribedBuffersMask & UNSUB_RULES) return false;
        return trackRulesLimiter.IsEnabled();
    }

    bool AccessTrackRules(TrackRulesV01 &info) override {
        if (!initialized || udpSocket == INVALID_SOCKET) return false;
        if (config.unsubscribedBuffersMask & UNSUB_RULES) return false;
        if (!trackRulesLimiter.ShouldSend()) return false;

        TrackRulesSessionPacket* rules = reinterpret_cast<TrackRulesSessionPacket*>(s_trackRulesBuffer);
        std::memset(rules, 0, sizeof(TrackRulesSessionPacket));

        rules->currentET = info.mCurrentET;
        rules->stage = info.mStage;
        rules->poleColumn = info.mPoleColumn;
        rules->numActions = info.mNumActions;

        long numParticipants = (info.mNumParticipants > 128) ? 128 : info.mNumParticipants;
        rules->numParticipants = numParticipants;

        rules->yellowFlagDetected = info.mYellowFlagDetected;
        rules->yellowFlagLapsWasOverridden = info.mYellowFlagLapsWasOverridden;
        rules->safetyCarExists = info.mSafetyCarExists;
        rules->safetyCarActive = info.mSafetyCarActive;
        rules->safetyCarLaps = info.mSafetyCarLaps;
        rules->safetyCarThreshold = info.mSafetyCarThreshold;
        rules->safetyCarLapDist = info.mSafetyCarLapDist;
        rules->safetyCarLapDistAtStart = info.mSafetyCarLapDistAtStart;
        rules->pitLaneStartDist = info.mPitLaneStartDist;
        rules->teleportLapDist = info.mTeleportLapDist;
        rules->yellowFlagState = info.mYellowFlagState;
        rules->yellowFlagLaps = info.mYellowFlagLaps;
        rules->safetyCarInstruction = info.mSafetyCarInstruction;
        rules->safetyCarSpeed = info.mSafetyCarSpeed;
        rules->safetyCarMinimumSpacing = info.mSafetyCarMinimumSpacing;
        rules->safetyCarMaximumSpacing = info.mSafetyCarMaximumSpacing;
        rules->minimumColumnSpacing = info.mMinimumColumnSpacing;
        rules->maximumColumnSpacing = info.mMaximumColumnSpacing;
        rules->minimumSpeed = info.mMinimumSpeed;
        rules->maximumSpeed = info.mMaximumSpeed;
        std::strncpy(rules->message, info.mMessage, sizeof(rules->message) - 1);
        rules->message[sizeof(rules->message) - 1] = '\0';

        if (numParticipants > 0 && info.mParticipant != nullptr) {
            TrackRulesParticipantPacket* partDst = reinterpret_cast<TrackRulesParticipantPacket*>(
                s_trackRulesBuffer + sizeof(TrackRulesSessionPacket)
            );
            for (long i = 0; i < numParticipants; ++i) {
                const auto &p = info.mParticipant[i];
                auto &dst = partDst[i];
                dst.id = p.mID;
                dst.frozenOrder = p.mFrozenOrder;
                dst.place = p.mPlace;
                dst.yellowSeverity = p.mYellowSeverity;
                dst.currentRelativeDistance = p.mCurrentRelativeDistance;
                dst.relativeLaps = p.mRelativeLaps;
                dst.columnAssignment = p.mColumnAssignment;
                dst.positionAssignment = p.mPositionAssignment;
                dst.pitsOpen = p.mPitsOpen;
                dst.upToSpeed = p.mUpToSpeed;
                dst.pad[0] = 0; dst.pad[1] = 0;
                dst.goalRelativeDistance = p.mGoalRelativeDistance;
                std::strncpy(dst.message, p.mMessage, sizeof(dst.message) - 1);
                dst.message[sizeof(dst.message) - 1] = '\0';
            }
        }

        size_t totalPayloadSize = sizeof(TrackRulesSessionPacket) + (numParticipants * sizeof(TrackRulesParticipantPacket));
        SendSlicedPayload(5, static_cast<unsigned short>(numParticipants), s_trackRulesBuffer, totalPayloadSize, info.mCurrentET);
        return false;
    }

    // Subscribe to pit menu updates (FR-04, SIMP Type 6 @ 100Hz)
    bool WantsPitMenuAccess() override {
        if (config.unsubscribedBuffersMask & UNSUB_PIT_INFO) return false;
        return pitMenuLimiter.IsEnabled();
    }

    bool AccessPitMenu(PitMenuV01 &info) override {
        if (!initialized || udpSocket == INVALID_SOCKET) return false;
        if (config.unsubscribedBuffersMask & UNSUB_PIT_INFO) return false;
        if (!pitMenuLimiter.ShouldSend()) return false;

        PitMenuPacket pkt{};
        pkt.categoryIndex = info.mCategoryIndex;
        std::strncpy(pkt.categoryName, info.mCategoryName, sizeof(pkt.categoryName) - 1);
        pkt.categoryName[sizeof(pkt.categoryName) - 1] = '\0';
        pkt.choiceIndex = info.mChoiceIndex;
        std::strncpy(pkt.choiceString, info.mChoiceString, sizeof(pkt.choiceString) - 1);
        pkt.choiceString[sizeof(pkt.choiceString) - 1] = '\0';
        pkt.numChoices = info.mNumChoices;

        SendSlicedPayload(6, 0, &pkt, sizeof(pkt), 0.0);
        return false;
    }

    // Inbound Hardware & Pit Menu Controls (FR-07)
    bool HasHardwareInputs() override {
        return config.enableInboundControl;
    }

    void UpdateHardware(const double fDT) override {
        if (!initialized || !config.enableInboundControl) return;

        // Poll non-blocking inbound UDP socket
        PollInboundCommands();

        // Decrement remaining pulse timers
        for (int i = 0; i < MAX_ACTIVE_HW_CONTROLS; ++i) {
            if (activeControls[i].active) {
                activeControls[i].remainingTimeSec -= fDT;
                if (activeControls[i].remainingTimeSec <= 0.0) {
                    activeControls[i].active = false;
                }
            }
        }
    }

    bool CheckHWControl(const char* const controlName, double &fRetVal) override {
        if (!initialized || !config.enableInboundControl || !controlName) return false;

        // Handle both with and without leading underscore (isiMotor standard)
        const char* cleanName = (controlName[0] == '_') ? (controlName + 1) : controlName;

        for (int i = 0; i < MAX_ACTIVE_HW_CONTROLS; ++i) {
            if (activeControls[i].active) {
                if (std::strcmp(activeControls[i].controlName, controlName) == 0 ||
                    std::strcmp(activeControls[i].controlName, cleanName) == 0) {
                    fRetVal = activeControls[i].value;
                    return true;
                }
            }
        }
        return false;
    }

    // Subscribe to weather updates (FR-04, SIMP Type 7 @ 1Hz) & Weather Injection (FR-07)
    bool WantsWeatherAccess() override {
        if (config.unsubscribedBuffersMask & UNSUB_WEATHER) return false;
        return weatherLimiter.IsEnabled() || (config.enableInboundControl && weatherOverride.active);
    }

    bool AccessWeather(double trackNodeSize, WeatherControlInfoV01 &info) override {
        (void)trackNodeSize;
        if (!initialized) return false;

        // 1. Apply Inbound Weather Override (FR-07)
        if (config.enableInboundControl && weatherOverride.active) {
            info.mAmbientTempK = weatherOverride.data.ambientTemp + 273.15;
            info.mRaining[1][1] = weatherOverride.data.raining;
            info.mCloudiness = weatherOverride.data.darkCloud;
            info.mWindMaxSpeed = weatherOverride.data.windSpeed;
            info.mApplyCloudinessInstantly = true;
            weatherOverride.active = false; // Override applied

            // Broadcast the modified conditions immediately if output socket is ready
            if (udpSocket != INVALID_SOCKET && !(config.unsubscribedBuffersMask & UNSUB_WEATHER) && weatherLimiter.IsEnabled()) {
                WeatherPacket pkt{};
                pkt.et = info.mET;
                for (int r = 0; r < 3; ++r) {
                    for (int c = 0; c < 3; ++c) {
                        pkt.raining[r][c] = info.mRaining[r][c];
                    }
                }
                pkt.cloudiness = info.mCloudiness;
                pkt.ambientTempK = info.mAmbientTempK;
                pkt.windMaxSpeed = info.mWindMaxSpeed;
                pkt.applyCloudinessInstantly = info.mApplyCloudinessInstantly;
                pkt.pad[0] = 0; pkt.pad[1] = 0; pkt.pad[2] = 0;

                SendSlicedPayload(7, 0, &pkt, sizeof(pkt), info.mET);
            }
            return true; // Overridden!
        }

        // 2. Standard weather broadcast (FR-04)
        if (config.unsubscribedBuffersMask & UNSUB_WEATHER) return false;
        if (udpSocket == INVALID_SOCKET) return false;
        if (!weatherLimiter.ShouldSend()) return false;

        WeatherPacket pkt{};
        pkt.et = info.mET;
        for (int r = 0; r < 3; ++r) {
            for (int c = 0; c < 3; ++c) {
                pkt.raining[r][c] = info.mRaining[r][c];
            }
        }
        pkt.cloudiness = info.mCloudiness;
        pkt.ambientTempK = info.mAmbientTempK;
        pkt.windMaxSpeed = info.mWindMaxSpeed;
        pkt.applyCloudinessInstantly = info.mApplyCloudinessInstantly;
        pkt.pad[0] = 0; pkt.pad[1] = 0; pkt.pad[2] = 0;

        SendSlicedPayload(7, 0, &pkt, sizeof(pkt), info.mET);
        return false;
    }

    // High frequency Force Feedback callback (FR-06, SIMP Type 9 @ up to 400Hz)
    bool ForceFeedback(double &forceValue) override {
        if (!initialized || udpSocket == INVALID_SOCKET) return false;
        if (config.unsubscribedBuffersMask & UNSUB_FORCE_FEEDBACK) return false;
        if (!forceFeedbackLimiter.ShouldSend()) return false;

        ForceFeedbackPacket pkt{};
        pkt.forceValue = forceValue;

        SendSlicedPayload(9, 0, &pkt, sizeof(pkt), 0.0);
        return false; // Return false so game's native FFB calculation is not overridden
    }

    // High frequency Graphics & Camera callback (FR-06, SIMP Type 10 @ 60-100Hz)
    void UpdateGraphics(const GraphicsInfoV02 &info) override {
        if (!initialized || udpSocket == INVALID_SOCKET) return;
        if (config.unsubscribedBuffersMask & UNSUB_GRAPHICS) return;
        if (!graphicsLimiter.ShouldSend()) return;

        GraphicsPacket pkt{};
        pkt.camPos = info.mCamPos;
        pkt.camOri[0] = info.mCamOri[0];
        pkt.camOri[1] = info.mCamOri[1];
        pkt.camOri[2] = info.mCamOri[2];
        pkt.ambientRed = info.mAmbientRed;
        pkt.ambientGreen = info.mAmbientGreen;
        pkt.ambientBlue = info.mAmbientBlue;
        pkt.slotId = info.mID;
        pkt.cameraType = info.mCameraType;

        SendSlicedPayload(10, static_cast<unsigned short>(info.mID >= 0 ? info.mID : 0), &pkt, sizeof(pkt), 0.0);
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
    return 7; // Corresponds to InternalsPluginV07
}

extern "C" __declspec(dllexport) PluginObject* __cdecl CreatePluginObject() {
    return new IsiMotorRawUdpPlugin();
}

extern "C" __declspec(dllexport) void __cdecl DestroyPluginObject(PluginObject* obj) {
    delete obj;
}
