/**
 * isiMotor-RawUDP-Plugin
 * High-Performance Raw Binary Telemetry & Multi-Car Scoring Plugin for isiMotor games
 * (Le Mans Ultimate, rFactor 2).
 * 
 * Copyright 2026 Marc GARDENT
 * Licensed under the Apache License, Version 2.0.
 * 
 * Features:
 * - ZeroMQ PUB/SUB transport over TCP (libzmq/cppzmq), no JSON/Boost dependency.
 * - Each outbound packet type is FlatBuffers-encoded (schemas/*.fbs) and published on
 *   its own TCP port (TcpBasePort + packet type); no header, no chunking - the ZeroMQ
 *   message boundary already delimits one message.
 * - Zero dynamic memory allocations in high-frequency telemetry and scoring update loops
 *   (FlatBufferBuilders are member-owned and reused via Clear() rather than reallocated).
 * - TelemInfoV01 (1888 bytes) telemetry stream, including all 4 wheels and the LMU
 *   telemetry/wheel extensions.
 * - Multi-vehicle full scoring stream (up to 128 vehicles, ScoringInfoV01 + VehicleScoringInfoV01,
 *   including the LMU scoring extensions).
 * - Weather & ambient conditions stream (WeatherControlInfoV01, Type 7 @ 1Hz).
 * - Compact binary scoring packet (Type 2) for ultra-low overhead HUDs.
 * - System event state notifications (Type 3).
 * - UnsubscribedBuffersMask support matching rF2SharedMemoryMapPlugin.
 * - Standard isiMotor configuration via CustomPluginVariables.JSON (InternalsPluginV07).
 * - Live hot-reload of configuration (event-based Win32 file watcher, zero polling).
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
#include <cstdarg>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#define __cdecl
#define __declspec(x)
typedef void* HWND;
#define long int
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
#define GetCurrentProcessId() 0
#endif

#include <zmq.hpp>

#include "flatbuffers/flatbuffers.h"
#include "system_event_generated.h"
#include "force_feedback_generated.h"
#include "inbound_command_generated.h"
#include "compact_scoring_generated.h"
#include "weather_generated.h"
#include "extended_state_generated.h"
#include "graphics_generated.h"
#include "telemetry_generated.h"
#include "full_scoring_generated.h"

#include "InternalsPlugin.hpp"

#define PLUGIN_NAME "isiMotor_RawUDP.dll"
#define DEFAULT_ZMQ_PORT 5000
#define DEFAULT_ZMQ_HOST "127.0.0.1"

// Module handle saved at DLL injection time
static HINSTANCE g_hModule = NULL;
static bool g_enableLogging = false;

static inline void PluginLog(const char* fmt, ...) {
    if (!g_enableLogging) return;
    char path[MAX_PATH] = {0};
#ifdef _WIN32
    if (g_hModule) {
        GetModuleFileNameA(static_cast<HMODULE>(g_hModule), path, sizeof(path));
        char* lastSlash = std::strrchr(path, '\\');
        if (!lastSlash) lastSlash = std::strrchr(path, '/');
        if (lastSlash) {
            std::strcpy(lastSlash + 1, "isiMotor_RawUDP.log");
        }
    }
#endif
    FILE* f = path[0] ? std::fopen(path, "a") : nullptr;
    if (!f) f = std::fopen("Plugins/isiMotor_RawUDP.log", "a");
    if (!f) f = std::fopen("isiMotor_RawUDP.log", "a");
    if (!f) f = std::fopen("UserData/Log/isiMotor_RawUDP.log", "a");
    if (!f) f = std::fopen("UserData/isiMotor_RawUDP.log", "a");
    if (!f) return;
    va_list args;
    va_start(args, fmt);
    std::vfprintf(f, fmt, args);
    std::fprintf(f, "\n");
    va_end(args);
    std::fclose(f);
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    (void)lpReserved;
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        g_hModule = hModule;
        PluginLog("=== isiMotor_RawUDP.dll Loaded (DLL_PROCESS_ATTACH, PID=%lu) ===", static_cast<unsigned long>(GetCurrentProcessId()));
    }
    return TRUE;
}

#pragma pack(push, 4)

// CompactScoring (Type 2) is now a FlatBuffer (schemas/compact_scoring.fbs) - see UpdateScoring().

// SystemEvent (Type 3) is now a FlatBuffer (schemas/system_event.fbs, isimotor::fbs::SystemEvent) - see SendSystemEvent().

// FullScoringSession (Type 4, header + vehicle array) is now a FlatBuffer
// (schemas/full_scoring.fbs) - see UpdateScoring(). With ZeroMQ/TCP the
// message boundary already delimits it, so the old header+chunking across
// the session header and up to 128 vehicle records is gone too.

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

// WeatherControl (Type 7) is now a FlatBuffer (schemas/weather.fbs) - see SendWeather().

// ExtendedState (Type 8) is now a FlatBuffer (schemas/extended_state.fbs) - see SendExtendedState().

// ForceFeedback (Type 9) is now a FlatBuffer (schemas/force_feedback.fbs, isimotor::fbs::ForceFeedback) - see ForceFeedback() override below.

// Graphics (Type 10) is now a FlatBuffer (schemas/graphics.fbs) - see UpdateGraphics().

// Inbound commands (HWControl, Type 100; WeatherControl, Type 101) are now a
// single isimotor::fbs::InboundCommand FlatBuffer with a CommandPayload union
// (schemas/inbound_command.fbs) - see PollInboundCommands().

#pragma pack(pop)

// Buffer unsubscription bitmask flags
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
    bool enabled;
    bool enableLogging;
    char tcpHost[64];
    int tcpBasePort;
    char inboundTcpHost[64];
    int inboundTcpPort;
    bool enableInboundControl;
    double playerTelemetryHz;
    double opponentTelemetryHz;
    double compactScoringHz;
    double fullScoringHz;
    double weatherHz;
    double extendedStateHz;
    double forceFeedbackHz;
    double graphicsHz;
    bool enableSystemEvents;
    long unsubscribedBuffersMask;
};

// -------------------------------------------------------------------------
// ConfigFileWatcher — Event-based file change detection (Win32 native)
// Uses FindFirstChangeNotification to avoid polling. A dedicated thread
// sleeps on WaitForSingleObject until the OS signals a directory change.
// A volatile flag is set for the main plugin thread to check and clear.
// -------------------------------------------------------------------------
#ifdef _WIN32
class ConfigFileWatcher {
private:
    HANDLE hChangeNotify;
    HANDLE hThread;
    HANDLE hStopEvent;
    volatile bool dirty;
    char watchedDir[MAX_PATH];

    static DWORD WINAPI WatcherThreadProc(LPVOID param) {
        ConfigFileWatcher* self = reinterpret_cast<ConfigFileWatcher*>(param);
        HANDLE handles[2] = { self->hStopEvent, self->hChangeNotify };

        while (true) {
            DWORD result = WaitForMultipleObjects(2, handles, FALSE, INFINITE);

            if (result == WAIT_OBJECT_0) {
                // hStopEvent signaled — exit thread
                break;
            }
            if (result == WAIT_OBJECT_0 + 1) {
                // Directory change detected — debounce: wait 200ms for editor to finish writing
                Sleep(200);
                self->dirty = true;

                // Re-arm the notification
                if (!FindNextChangeNotification(self->hChangeNotify)) {
                    break;  // Handle invalidated, exit
                }
            } else {
                // Error or abandoned — exit
                break;
            }
        }
        return 0;
    }

public:
    ConfigFileWatcher() : hChangeNotify(INVALID_HANDLE_VALUE), hThread(NULL),
                          hStopEvent(NULL), dirty(false) {
        std::memset(watchedDir, 0, sizeof(watchedDir));
    }

    ~ConfigFileWatcher() {
        Stop();
    }

    bool Start(const char* configFilePath) {
        if (!configFilePath || configFilePath[0] == '\0') return false;
        Stop();  // Clean up any previous watcher

        // Extract directory from config file path
        std::strncpy(watchedDir, configFilePath, sizeof(watchedDir) - 1);
        watchedDir[sizeof(watchedDir) - 1] = '\0';
        char* lastSlash = std::strrchr(watchedDir, '\\');
        if (!lastSlash) lastSlash = std::strrchr(watchedDir, '/');
        if (lastSlash) {
            *lastSlash = '\0';
        } else {
            // No directory separator — watch current directory
            std::strcpy(watchedDir, ".");
        }

        // Create stop event for clean shutdown
        hStopEvent = CreateEvent(NULL, TRUE, FALSE, NULL);
        if (!hStopEvent) return false;

        // Create change notification handle (watch for file writes in the directory)
        hChangeNotify = FindFirstChangeNotificationA(
            watchedDir,
            FALSE,  // Do not watch subtree
            FILE_NOTIFY_CHANGE_LAST_WRITE | FILE_NOTIFY_CHANGE_FILE_NAME
        );
        if (hChangeNotify == INVALID_HANDLE_VALUE) {
            CloseHandle(hStopEvent);
            hStopEvent = NULL;
            return false;
        }

        dirty = false;

        // Launch watcher thread
        hThread = CreateThread(NULL, 0, WatcherThreadProc, this, 0, NULL);
        if (!hThread) {
            FindCloseChangeNotification(hChangeNotify);
            hChangeNotify = INVALID_HANDLE_VALUE;
            CloseHandle(hStopEvent);
            hStopEvent = NULL;
            return false;
        }

        return true;
    }

    void Stop() {
        if (hStopEvent) {
            SetEvent(hStopEvent);
        }
        if (hThread) {
            WaitForSingleObject(hThread, 2000);
            CloseHandle(hThread);
            hThread = NULL;
        }
        if (hChangeNotify != INVALID_HANDLE_VALUE) {
            FindCloseChangeNotification(hChangeNotify);
            hChangeNotify = INVALID_HANDLE_VALUE;
        }
        if (hStopEvent) {
            CloseHandle(hStopEvent);
            hStopEvent = NULL;
        }
    }

    bool CheckAndClearDirty() {
        if (dirty) {
            dirty = false;
            return true;
        }
        return false;
    }

    bool IsRunning() const {
        return hThread != NULL;
    }
};
#endif // _WIN32

// Outbound packet types actually emitted by this plugin, each on its own bound
// TCP port (tcpBasePort + packetType) so consumers can subscribe to only the
// stream(s) they need. Ports are hardcoded arithmetically for now, pending a
// future service registry that will allocate them dynamically.
static const unsigned char kOutboundPacketTypes[] = {1, 2, 3, 4, 7, 8, 9, 10};
static const int kMaxPacketType = 10;

class IsiMotorRawUdpPlugin : public InternalsPluginV06 {
private:
    zmq::context_t zmqContext;
    zmq::socket_t pubSockets[kMaxPacketType + 1];  // Outbound telemetry, one PUB per packet type, indexed by type.
    bool pubBound[kMaxPacketType + 1];
    zmq::socket_t inboundSocket;  // Inbound commands: plugin binds SUB, clients connect PUB (grouped, single port).
    bool inboundBound;
    PluginConfig config;
    RateLimiter playerTelemetryLimiter;
    RateLimiter opponentTelemetryLimiters[128];
    RateLimiter compactScoringLimiter;
    RateLimiter fullScoringLimiter;
    RateLimiter weatherLimiter;
    RateLimiter extendedStateLimiter;
    RateLimiter forceFeedbackLimiter;
    RateLimiter graphicsLimiter;
    bool initialized;

    // FlatBuffers builders reused across calls (Clear()'d each time) to avoid
    // repeated heap allocation for the packet types migrated off the legacy
    // RawUdpHeader + chunking format (no framing needed: with TCP/ZeroMQ the
    // message boundary IS the FlatBuffer, so no chunking is needed either).
    flatbuffers::FlatBufferBuilder fbSystemEventBuilder;
    flatbuffers::FlatBufferBuilder fbForceFeedbackBuilder;
    flatbuffers::FlatBufferBuilder fbCompactScoringBuilder;
    flatbuffers::FlatBufferBuilder fbWeatherBuilder;
    flatbuffers::FlatBufferBuilder fbExtendedStateBuilder;
    flatbuffers::FlatBufferBuilder fbGraphicsBuilder;
    flatbuffers::FlatBufferBuilder fbTelemetryBuilder;
    flatbuffers::FlatBufferBuilder fbFullScoringBuilder;

    // Hot-reload: file watcher and resolved config path
#ifdef _WIN32
    ConfigFileWatcher configWatcher;
#endif
    char resolvedConfigPath[MAX_PATH];

    // Inbound Hardware & Pit Menu Controls (FR-07)
    struct ActiveHWControl {
        char controlName[32];
        double value;
        double remainingTimeSec;
        bool active;
    };
    static const int MAX_ACTIVE_HW_CONTROLS = 32;
    ActiveHWControl activeControls[MAX_ACTIVE_HW_CONTROLS];

    // Inbound Dynamic Weather Override (FR-07). Decoupled from the wire
    // format (isimotor::fbs::WeatherControl) so this internal state layout
    // doesn't need to track the schema field-for-field.
    struct WeatherOverrideData {
        double ambientTemp;
        double trackTemp;
        double darkCloud;
        double raining;
        double windSpeed;
        double windDirection;
        double minPathWetness;
        double maxPathWetness;
    };
    struct WeatherOverrideState {
        bool active;
        WeatherOverrideData data;
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
    // Safe Zero-Allocation JSON Parser & Configuration Helpers
    // -------------------------------------------------------------------------

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

    static inline void ExtractJsonString(const char* json, const char* key, char* dst, size_t maxLen, const char* defaultVal) {
        if (!dst || maxLen == 0) return;
        std::strncpy(dst, defaultVal, maxLen - 1);
        dst[maxLen - 1] = '\0';
        if (!json || !key) return;

        char searchKey[128];
        std::snprintf(searchKey, sizeof(searchKey), "\"%s\"", key);
        const char* pos = std::strstr(json, searchKey);
        if (!pos) return;

        pos += std::strlen(searchKey);
        while (*pos == ' ' || *pos == '\t' || *pos == ':') ++pos;

        if (*pos == '\"') {
            ++pos;
            size_t i = 0;
            while (*pos && *pos != '\"' && *pos != '\r' && *pos != '\n' && i < maxLen - 1) {
                dst[i++] = *pos++;
            }
            dst[i] = '\0';
        } else {
            size_t i = 0;
            while (*pos && *pos != ',' && *pos != '}' && *pos != '\r' && *pos != '\n' && *pos != ' ' && *pos != '\t' && i < maxLen - 1) {
                dst[i++] = *pos++;
            }
            dst[i] = '\0';
        }
    }

    static void BuildTcpEndpoint(const char* host, int port, char* out, size_t outLen) {
        std::snprintf(out, outLen, "tcp://%s:%d", host, port);
    }

    void InitDefaults() {
        config.enabled = true;
        config.enableLogging = false;
        g_enableLogging = false;
        std::strncpy(config.tcpHost, DEFAULT_ZMQ_HOST, sizeof(config.tcpHost) - 1);
        config.tcpHost[sizeof(config.tcpHost) - 1] = '\0';
        config.tcpBasePort = DEFAULT_ZMQ_PORT;
        std::strncpy(config.inboundTcpHost, DEFAULT_ZMQ_HOST, sizeof(config.inboundTcpHost) - 1);
        config.inboundTcpHost[sizeof(config.inboundTcpHost) - 1] = '\0';
        config.inboundTcpPort = 5101;
        config.enableInboundControl = true;
        config.playerTelemetryHz = -1.0;   // unlimited
        config.opponentTelemetryHz = 0.0;  // off (disabled for zero overhead)
        config.compactScoringHz = 10.0;    // 10Hz
        config.fullScoringHz = 5.0;        // 5Hz
        config.weatherHz = 1.0;            // 1Hz
        config.extendedStateHz = 5.0;      // 5Hz
        config.forceFeedbackHz = -1.0;     // unlimited (up to 400Hz)
        config.graphicsHz = 60.0;          // 60Hz
        config.enableSystemEvents = true;
        config.unsubscribedBuffersMask = 0;

        playerTelemetryLimiter.SetRate(config.playerTelemetryHz);
        for (int i = 0; i < 128; ++i) {
            opponentTelemetryLimiters[i].SetRate(config.opponentTelemetryHz);
        }
        compactScoringLimiter.SetRate(config.compactScoringHz);
        fullScoringLimiter.SetRate(config.fullScoringHz);
        weatherLimiter.SetRate(config.weatherHz);
        extendedStateLimiter.SetRate(config.extendedStateHz);
        forceFeedbackLimiter.SetRate(config.forceFeedbackHz);
        graphicsLimiter.SetRate(config.graphicsHz);
    }

    void LoadConfigFile() {
        FILE* f = nullptr;

        // On hot-reload, reuse the previously resolved path
        if (resolvedConfigPath[0] != '\0') {
            f = std::fopen(resolvedConfigPath, "rb");
        }

        // First load (or resolved path became invalid): scan candidate paths
        if (!f) {
            const char* paths[] = {
                "UserData/player/CustomPluginVariables.JSON",
                "UserData/CustomPluginVariables.JSON",
                "../UserData/player/CustomPluginVariables.JSON",
                "../UserData/CustomPluginVariables.JSON"
            };

            for (const char* p : paths) {
                f = std::fopen(p, "rb");
                if (f) {
                    std::strncpy(resolvedConfigPath, p, sizeof(resolvedConfigPath) - 1);
                    resolvedConfigPath[sizeof(resolvedConfigPath) - 1] = '\0';
                    break;
                }
            }
        }
        if (!f) return;

        char buf[8192] = {0};
        size_t n = std::fread(buf, 1, sizeof(buf) - 1, f);
        std::fclose(f);
        if (n == 0) return;
        buf[n] = '\0';

        char strVal[128];

        ExtractJsonString(buf, " Enabled", strVal, sizeof(strVal), "1");
        config.enabled = (ParseIntString(strVal, 1) != 0);

        ExtractJsonString(buf, "EnableLogging", strVal, sizeof(strVal), "Disabled");
        config.enableLogging = ParseBoolString(strVal, false);
        g_enableLogging = config.enableLogging;

        ExtractJsonString(buf, "TcpHost", config.tcpHost, sizeof(config.tcpHost), DEFAULT_ZMQ_HOST);

        ExtractJsonString(buf, "TcpBasePort", strVal, sizeof(strVal), "5000");
        config.tcpBasePort = ParseIntString(strVal, DEFAULT_ZMQ_PORT);

        ExtractJsonString(buf, "InboundTcpHost", config.inboundTcpHost, sizeof(config.inboundTcpHost), DEFAULT_ZMQ_HOST);

        ExtractJsonString(buf, "InboundTcpPort", strVal, sizeof(strVal), "5101");
        config.inboundTcpPort = ParseIntString(strVal, 5101);

        ExtractJsonString(buf, "InboundControl", strVal, sizeof(strVal), "Enabled");
        config.enableInboundControl = ParseBoolString(strVal, true);

        // Player Telemetry Rate
        ExtractJsonString(buf, "PlayerTelemetryRate", strVal, sizeof(strVal), "unlimited");
        config.playerTelemetryHz = ParseRateString(strVal, -1.0);

        // Opponent Telemetry Rate
        ExtractJsonString(buf, "OpponentTelemetryRate", strVal, sizeof(strVal), "off");
        config.opponentTelemetryHz = ParseRateString(strVal, 0.0);

        ExtractJsonString(buf, "CompactScoringRate", strVal, sizeof(strVal), "10Hz");
        config.compactScoringHz = ParseRateString(strVal, 10.0);

        ExtractJsonString(buf, "FullScoringRate", strVal, sizeof(strVal), "5Hz");
        config.fullScoringHz = ParseRateString(strVal, 5.0);

        ExtractJsonString(buf, "WeatherRate", strVal, sizeof(strVal), "1Hz");
        config.weatherHz = ParseRateString(strVal, 1.0);

        ExtractJsonString(buf, "ExtendedStateRate", strVal, sizeof(strVal), "5Hz");
        config.extendedStateHz = ParseRateString(strVal, 5.0);

        ExtractJsonString(buf, "ForceFeedbackRate", strVal, sizeof(strVal), "unlimited");
        config.forceFeedbackHz = ParseRateString(strVal, -1.0);

        ExtractJsonString(buf, "GraphicsRate", strVal, sizeof(strVal), "60Hz");
        config.graphicsHz = ParseRateString(strVal, 60.0);

        ExtractJsonString(buf, "SystemEvents", strVal, sizeof(strVal), "Enabled");
        config.enableSystemEvents = ParseBoolString(strVal, true);

        ExtractJsonString(buf, "UnsubscribedBuffersMask", strVal, sizeof(strVal), "0");
        config.unsubscribedBuffersMask = ParseIntString(strVal, 0);

        // Update rate limiters with parsed values
        playerTelemetryLimiter.SetRate(config.playerTelemetryHz);
        for (int i = 0; i < 128; ++i) {
            opponentTelemetryLimiters[i].SetRate(config.opponentTelemetryHz);
        }
        compactScoringLimiter.SetRate(config.compactScoringHz);
        fullScoringLimiter.SetRate(config.fullScoringHz);
        weatherLimiter.SetRate(config.weatherHz);
        extendedStateLimiter.SetRate(config.extendedStateHz);
        forceFeedbackLimiter.SetRate(config.forceFeedbackHz);
        graphicsLimiter.SetRate(config.graphicsHz);
    }

public:
    // Sends a FlatBuffer message on a per-type PUB socket, no header/chunking:
    // over TCP/ZeroMQ the message boundary already IS the FlatBuffer.
    void SendFlatBuffer(unsigned char packetType, flatbuffers::FlatBufferBuilder& builder) {
        if (!initialized || packetType > kMaxPacketType || !pubBound[packetType]) return;
        try {
            pubSockets[packetType].send(zmq::buffer(builder.GetBufferPointer(), builder.GetSize()), zmq::send_flags::dontwait);
        } catch (const zmq::error_t&) {
            // Best-effort: drop the message (e.g. HWM reached, no subscriber connected yet).
        }
    }

    void SendSystemEvent(unsigned char eventType) {
        if (!initialized || !config.enableSystemEvents || !pubBound[3]) return;
        fbSystemEventBuilder.Clear();
        auto root = isimotor::fbs::CreateSystemEvent(fbSystemEventBuilder, eventType);
        fbSystemEventBuilder.Finish(root);
        SendFlatBuffer(3, fbSystemEventBuilder);
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
        if (!initialized || !inboundBound || !config.enableInboundControl) return;

        zmq::message_t msg;

        while (true) {
            zmq::recv_result_t result;
            try {
                result = inboundSocket.recv(msg, zmq::recv_flags::dontwait);
            } catch (const zmq::error_t&) {
                break;
            }
            if (!result.has_value()) {
                break;  // EAGAIN: no more pending messages.
            }

            // No header/framing: the message IS an isimotor::fbs::InboundCommand
            // FlatBuffer; its CommandPayload union tells HWControl from WeatherControl.
            flatbuffers::Verifier verifier(static_cast<const uint8_t*>(msg.data()), msg.size());
            if (!isimotor::fbs::VerifyInboundCommandBuffer(verifier)) {
                continue;
            }
            const isimotor::fbs::InboundCommand* cmd = isimotor::fbs::GetInboundCommand(msg.data());

            if (cmd->payload_type() == isimotor::fbs::CommandPayload_HWControlCommand) {
                const isimotor::fbs::HWControlCommand* hw = cmd->payload_as_HWControlCommand();
                if (hw && hw->control_name()) {
                    ApplyHWControl(hw->control_name()->c_str(), hw->control_value(), hw->duration_ms());
                }
            } else if (cmd->payload_type() == isimotor::fbs::CommandPayload_WeatherControlCommand) {
                const isimotor::fbs::WeatherControlCommand* wc = cmd->payload_as_WeatherControlCommand();
                if (wc) {
                    weatherOverride.data.ambientTemp = wc->ambient_temp();
                    weatherOverride.data.trackTemp = wc->track_temp();
                    weatherOverride.data.darkCloud = wc->dark_cloud();
                    weatherOverride.data.raining = wc->raining();
                    weatherOverride.data.windSpeed = wc->wind_speed();
                    weatherOverride.data.windDirection = wc->wind_direction();
                    weatherOverride.data.minPathWetness = wc->min_path_wetness();
                    weatherOverride.data.maxPathWetness = wc->max_path_wetness();
                    weatherOverride.active = true;
                }
            }
        }
    }

public:
    IsiMotorRawUdpPlugin()
        : zmqContext(1), inboundSocket(), inboundBound(false), initialized(false) {
        for (int i = 0; i <= kMaxPacketType; ++i) {
            pubBound[i] = false;
        }
        std::memset(&config, 0, sizeof(config));
        std::memset(activeControls, 0, sizeof(activeControls));
        std::memset(&weatherOverride, 0, sizeof(weatherOverride));
        std::memset(resolvedConfigPath, 0, sizeof(resolvedConfigPath));
        InitDefaults();
    }

    ~IsiMotorRawUdpPlugin() override {
        Shutdown();
    }

    void Startup(long version) override {
        (void)version;
        if (initialized) return;

        // Load configuration from CustomPluginVariables.JSON
        LoadConfigFile();

        if (!config.enabled) {
            return;
        }

        // 1. Outbound telemetry: one PUB socket per packet type, plugin binds each on
        //    tcpBasePort + packetType, clients (SUB) connect to only the type(s) they need.
        for (unsigned char packetType : kOutboundPacketTypes) {
            try {
                pubSockets[packetType] = zmq::socket_t(zmqContext, zmq::socket_type::pub);
                pubSockets[packetType].set(zmq::sockopt::sndhwm, 10);  // Drop rather than buffer if no subscriber keeps up.
                pubSockets[packetType].set(zmq::sockopt::linger, 0);
                char endpoint[96];
                BuildTcpEndpoint(config.tcpHost, config.tcpBasePort + packetType, endpoint, sizeof(endpoint));
                pubSockets[packetType].bind(endpoint);
                pubBound[packetType] = true;
                PluginLog("[RawUDP] PUB socket for packet type %d bound on %s", packetType, endpoint);
            } catch (const zmq::error_t& e) {
                PluginLog("[RawUDP] Failed to bind PUB socket for packet type %d: %s", packetType, e.what());
                pubBound[packetType] = false;
            }
        }

        // 2. Inbound commands (FR-07 Bi-Directional Input): SUB socket, plugin binds, clients (PUB) connect.
        if (config.enableInboundControl) {
            try {
                inboundSocket = zmq::socket_t(zmqContext, zmq::socket_type::sub);
                inboundSocket.set(zmq::sockopt::subscribe, "");
                inboundSocket.set(zmq::sockopt::linger, 0);
                char inboundEndpoint[96];
                BuildTcpEndpoint(config.inboundTcpHost, config.inboundTcpPort, inboundEndpoint, sizeof(inboundEndpoint));
                inboundSocket.bind(inboundEndpoint);
                inboundBound = true;
                PluginLog("[RawUDP] Inbound commands SUB bound on %s", inboundEndpoint);
            } catch (const zmq::error_t& e) {
                PluginLog("[RawUDP] Failed to bind inbound SUB socket: %s", e.what());
                inboundBound = false;
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

        // Start config file watcher for hot-reload
#ifdef _WIN32
        if (resolvedConfigPath[0] != '\0') {
            if (configWatcher.Start(resolvedConfigPath)) {
                PluginLog("[RawUDP] Config file watcher started on: %s", resolvedConfigPath);
            }
        }
#endif
    }

    void Shutdown() override {
        // Stop config file watcher before cleaning up
#ifdef _WIN32
        configWatcher.Stop();
#endif
        if (initialized) {
            for (unsigned char packetType : kOutboundPacketTypes) {
                if (pubBound[packetType]) {
                    pubSockets[packetType].close();
                    pubBound[packetType] = false;
                }
            }
            if (inboundBound) {
                inboundSocket.close();
                inboundBound = false;
            }
            initialized = false;
        }
    }

    void SendExtendedState(double sessionET) {
        (void)sessionET;  // No longer carried: FlatBuffers dropped the RawUdpHeader metadata entirely.
        if (!initialized || !pubBound[8]) return;
        if (!extendedStateLimiter.IsEnabled()) return;

        fbExtendedStateBuilder.Clear();
        auto physics = isimotor::fbs::CreatePhysicsOptions(
            fbExtendedStateBuilder,
            cachedPhysics.mTractionControl, cachedPhysics.mAntiLockBrakes, cachedPhysics.mStabilityControl,
            cachedPhysics.mAutoShift, cachedPhysics.mAutoClutch, cachedPhysics.mInvulnerable,
            cachedPhysics.mOppositeLock, cachedPhysics.mSteeringHelp, cachedPhysics.mBrakingHelp,
            cachedPhysics.mSpinRecovery, cachedPhysics.mAutoPit, cachedPhysics.mAutoLift,
            cachedPhysics.mAutoBlip, cachedPhysics.mFuelMult, cachedPhysics.mTireMult,
            cachedPhysics.mMechFail, cachedPhysics.mAllowPitcrewPush, cachedPhysics.mRepeatShifts,
            cachedPhysics.mHoldClutch, cachedPhysics.mAutoReverse, cachedPhysics.mAlternateNeutral,
            cachedPhysics.mAIControl, cachedPhysics.mManualShiftOverrideTime, cachedPhysics.mAutoShiftOverrideTime,
            cachedPhysics.mSpeedSensitiveSteering, cachedPhysics.mSteerRatioSpeed);

        auto root = isimotor::fbs::CreateExtendedState(
            fbExtendedStateBuilder, physics, maxImpactMagnitude, accumulatedImpactMagnitude,
            inRealtimeFC, sessionStarted, currentSession, currentPitSpeedLimit);
        fbExtendedStateBuilder.Finish(root);
        SendFlatBuffer(8, fbExtendedStateBuilder);
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
        bool playerOn = playerTelemetryLimiter.IsEnabled();
        bool opponentOn = (config.opponentTelemetryHz != 0.0);
        if (opponentOn) return 2; // All vehicles (player + opponents)
        if (playerOn) return 1;   // Player vehicle only (zero AI overhead)
        return 0;
    }

    // Encodes one TelemWheelV01 (with its embedded LMU wheel extension) into the builder.
    static flatbuffers::Offset<isimotor::fbs::TelemWheel> EncodeWheelFbs(
            flatbuffers::FlatBufferBuilder &b, const TelemWheelV01 &w) {
        auto lmu = isimotor::fbs::CreateLmuWheel(b, w.mLMUExtension.mCompoundType, w.mLMUExtension.mBrakeWear);
        auto terrainName = b.CreateString(w.mTerrainName, strnlen(w.mTerrainName, sizeof(w.mTerrainName)));
        double temperature[3] = {w.mTemperature[0], w.mTemperature[1], w.mTemperature[2]};
        auto temperatureOffset = b.CreateVector<double>(temperature, 3);
        double innerLayerTemp[3] = {
            w.mTireInnerLayerTemperature[0], w.mTireInnerLayerTemperature[1], w.mTireInnerLayerTemperature[2]};
        auto innerLayerTempOffset = b.CreateVector<double>(innerLayerTemp, 3);

        return isimotor::fbs::CreateTelemWheel(
            b, w.mSuspensionDeflection, w.mRideHeight, w.mSuspForce, w.mBrakeTemp, w.mBrakePressure,
            w.mRotation, w.mLateralPatchVel, w.mLongitudinalPatchVel, w.mLateralGroundVel, w.mLongitudinalGroundVel,
            w.mCamber, w.mLateralForce, w.mLongitudinalForce, w.mTireLoad, w.mGripFract, w.mPressure,
            temperatureOffset, w.mWear, terrainName, w.mSurfaceType, w.mFlat, w.mDetached,
            w.mStaticUndeflectedRadius, w.mVerticalTireDeflection, w.mWheelYLocation, w.mToe,
            w.mTireCarcassTemperature, innerLayerTempOffset, lmu);
    }

    // High frequency callback (~60-100Hz): Direct memory dump (zero-copy, zero-allocation)
    void UpdateTelemetry(const TelemInfoV01 &info) override {
        if (!initialized) return;

        // Periodic ExtendedState stream (SIMP Type 8 @ 5Hz)
        if (extendedStateLimiter.IsEnabled() && extendedStateLimiter.ShouldSend()) {
            SendExtendedState(info.mElapsedTime);
        }

        if (config.unsubscribedBuffersMask & UNSUB_TELEMETRY) return;

        // Discriminate player vs opponent vehicle
        bool isPlayer = (info.mID <= 0);
        if (isPlayer) {
            // Track collision damage impacts for player
            if (info.mLastImpactMagnitude > 0.0) {
                if (info.mLastImpactMagnitude > maxImpactMagnitude) {
                    maxImpactMagnitude = info.mLastImpactMagnitude;
                }
                accumulatedImpactMagnitude += info.mLastImpactMagnitude;
            }

            if (!playerTelemetryLimiter.ShouldSend()) return;
        } else {
            if (config.opponentTelemetryHz == 0.0) return;
            int slot = (info.mID >= 0 && info.mID < 128) ? info.mID : (info.mID % 128);
            if (slot < 0) slot = 0;
            if (!opponentTelemetryLimiters[slot].ShouldSend()) return;
        }

        if (!pubBound[1]) return;

        flatbuffers::FlatBufferBuilder &b = fbTelemetryBuilder;
        b.Clear();

        // Wheels (front-left, front-right, rear-left, rear-right), each with its LMU extension.
        flatbuffers::Offset<isimotor::fbs::TelemWheel> wheelOffsets[4];
        for (int i = 0; i < 4; ++i) {
            wheelOffsets[i] = EncodeWheelFbs(b, info.mWheel[i]);
        }
        auto wheelsVec = b.CreateVector(wheelOffsets, 4);

        // LMU telemetry extension (mapped within mExpansion/mLMUExtension union).
        const LMUExtendedTelemetry &lmuSrc = info.mLMUExtension;
        auto ecu = isimotor::fbs::CreateEcuRaw(
            b, lmuSrc.mTC, lmuSrc.mTCMax, lmuSrc.mTCCut, lmuSrc.mTCCutMax, lmuSrc.mTCSlip, lmuSrc.mTCSlipMax,
            lmuSrc.mABS, lmuSrc.mABSMax, lmuSrc.mTCActive, lmuSrc.mABSActive, lmuSrc.mMotorMap, lmuSrc.mMotorMapMax,
            lmuSrc.mMigration, lmuSrc.mMigrationMax, lmuSrc.mFrontAntiSway, lmuSrc.mFrontAntiSwayMax,
            lmuSrc.mRearAntiSway, lmuSrc.mRearAntiSwayMax, lmuSrc.mWiperState, lmuSrc.mLiftAndCoastProgress);
        auto vehicleModel = b.CreateString(lmuSrc.mVehicleModel, strnlen(lmuSrc.mVehicleModel, sizeof(lmuSrc.mVehicleModel)));
        auto lmu = isimotor::fbs::CreateLmuTelemetry(
            b, ecu, lmuSrc.mVirtualEnergy, lmuSrc.mRegen, lmuSrc.mTrackLimitsSteps, vehicleModel);

        auto vehicleName = b.CreateString(info.mVehicleName, strnlen(info.mVehicleName, sizeof(info.mVehicleName)));
        auto trackName = b.CreateString(info.mTrackName, strnlen(info.mTrackName, sizeof(info.mTrackName)));
        auto frontCompoundName = b.CreateString(
            info.mFrontTireCompoundName, strnlen(info.mFrontTireCompoundName, sizeof(info.mFrontTireCompoundName)));
        auto rearCompoundName = b.CreateString(
            info.mRearTireCompoundName, strnlen(info.mRearTireCompoundName, sizeof(info.mRearTireCompoundName)));

        uint8_t dentSeverity[8];
        for (int i = 0; i < 8; ++i) dentSeverity[i] = info.mDentSeverity[i];
        auto dentSeverityOffset = b.CreateVector<uint8_t>(dentSeverity, 8);

        float p2g[3] = {
            info.mPhysicsToGraphicsOffset[0], info.mPhysicsToGraphicsOffset[1], info.mPhysicsToGraphicsOffset[2]};
        auto p2gOffset = b.CreateVector<float>(p2g, 3);

        isimotor::fbs::Vec3 pos(info.mPos.x, info.mPos.y, info.mPos.z);
        isimotor::fbs::Vec3 localVel(info.mLocalVel.x, info.mLocalVel.y, info.mLocalVel.z);
        isimotor::fbs::Vec3 localAccel(info.mLocalAccel.x, info.mLocalAccel.y, info.mLocalAccel.z);
        isimotor::fbs::Vec3 ori0(info.mOri[0].x, info.mOri[0].y, info.mOri[0].z);
        isimotor::fbs::Vec3 ori1(info.mOri[1].x, info.mOri[1].y, info.mOri[1].z);
        isimotor::fbs::Vec3 ori2(info.mOri[2].x, info.mOri[2].y, info.mOri[2].z);
        isimotor::fbs::Vec3 localRot(info.mLocalRot.x, info.mLocalRot.y, info.mLocalRot.z);
        isimotor::fbs::Vec3 localRotAccel(info.mLocalRotAccel.x, info.mLocalRotAccel.y, info.mLocalRotAccel.z);
        isimotor::fbs::Vec3 lastImpactPos(info.mLastImpactPos.x, info.mLastImpactPos.y, info.mLastImpactPos.z);

        auto root = isimotor::fbs::CreateTelemInfo(
            b, info.mID, info.mDeltaTime, info.mElapsedTime, info.mLapNumber, info.mLapStartET,
            vehicleName, trackName, &pos, &localVel, &localAccel, &ori0, &ori1, &ori2, &localRot, &localRotAccel,
            info.mGear, info.mEngineRPM, info.mEngineWaterTemp, info.mEngineOilTemp, info.mClutchRPM,
            info.mUnfilteredThrottle, info.mUnfilteredBrake, info.mUnfilteredSteering, info.mUnfilteredClutch,
            info.mFilteredThrottle, info.mFilteredBrake, info.mFilteredSteering, info.mFilteredClutch,
            info.mSteeringShaftTorque, info.mFront3rdDeflection, info.mRear3rdDeflection,
            info.mFrontWingHeight, info.mFrontRideHeight, info.mRearRideHeight, info.mDrag,
            info.mFrontDownforce, info.mRearDownforce, info.mFuel, info.mEngineMaxRPM,
            info.mScheduledStops, info.mOverheating, info.mDetached, info.mHeadlights, dentSeverityOffset,
            info.mLastImpactET, info.mLastImpactMagnitude, &lastImpactPos, info.mEngineTorque, info.mCurrentSector,
            info.mSpeedLimiter, info.mMaxGears, info.mFrontTireCompoundIndex, info.mRearTireCompoundIndex,
            info.mFuelCapacity, info.mFrontFlapActivated, info.mRearFlapActivated, info.mRearFlapLegalStatus,
            info.mIgnitionStarter, frontCompoundName, rearCompoundName, info.mSpeedLimiterAvailable,
            info.mAntiStallActivated, info.mVisualSteeringWheelRange, info.mRearBrakeBias, info.mTurboBoostPressure,
            p2gOffset, info.mPhysicalSteeringWheelRange, info.mBatteryChargeFraction,
            info.mElectricBoostMotorTorque, info.mElectricBoostMotorRPM, info.mElectricBoostMotorTemperature,
            info.mElectricBoostWaterTemperature, info.mElectricBoostMotorState, lmu, wheelsVec);
        b.Finish(root);
        SendFlatBuffer(1, b);
    }

    // Subscribe to scoring updates (~1-5Hz)
    bool WantsScoringUpdates() override {
        if (config.unsubscribedBuffersMask & UNSUB_SCORING) return false;
        return compactScoringLimiter.IsEnabled() || fullScoringLimiter.IsEnabled();
    }

    // Encodes one VehicleScoringInfoV01 (with its embedded LMU vehicle scoring extension) into the builder.
    static flatbuffers::Offset<isimotor::fbs::VehicleScoring> EncodeVehicleScoringFbs(
            flatbuffers::FlatBufferBuilder &b, const VehicleScoringInfoV01 &v) {
        auto driverName = b.CreateString(v.mDriverName, strnlen(v.mDriverName, sizeof(v.mDriverName)));
        auto vehicleName = b.CreateString(v.mVehicleName, strnlen(v.mVehicleName, sizeof(v.mVehicleName)));
        auto vehicleClass = b.CreateString(v.mVehicleClass, strnlen(v.mVehicleClass, sizeof(v.mVehicleClass)));
        auto pitGroup = b.CreateString(v.mPitGroup, strnlen(v.mPitGroup, sizeof(v.mPitGroup)));

        isimotor::fbs::Vec3 pos(v.mPos.x, v.mPos.y, v.mPos.z);
        isimotor::fbs::Vec3 localVel(v.mLocalVel.x, v.mLocalVel.y, v.mLocalVel.z);
        isimotor::fbs::Vec3 localAccel(v.mLocalAccel.x, v.mLocalAccel.y, v.mLocalAccel.z);
        isimotor::fbs::Vec3 ori0(v.mOri[0].x, v.mOri[0].y, v.mOri[0].z);
        isimotor::fbs::Vec3 ori1(v.mOri[1].x, v.mOri[1].y, v.mOri[1].z);
        isimotor::fbs::Vec3 ori2(v.mOri[2].x, v.mOri[2].y, v.mOri[2].z);
        isimotor::fbs::Vec3 localRot(v.mLocalRot.x, v.mLocalRot.y, v.mLocalRot.z);
        isimotor::fbs::Vec3 localRotAccel(v.mLocalRotAccel.x, v.mLocalRotAccel.y, v.mLocalRotAccel.z);

        auto lmu = isimotor::fbs::CreateLmuVehicleScoring(
            b, v.mLMUExtension.mFuelFraction / 255.0f, v.mLMUExtension.mTrackLimitsSteps);

        return isimotor::fbs::CreateVehicleScoring(
            b, v.mID, driverName, vehicleName, v.mTotalLaps, v.mSector, v.mFinishStatus, v.mLapDist,
            v.mPathLateral, v.mTrackEdge, v.mBestSector1, v.mBestSector2, v.mBestLapTime, v.mLastSector1,
            v.mLastSector2, v.mLastLapTime, v.mCurSector1, v.mCurSector2, v.mNumPitstops, v.mNumPenalties,
            v.mIsPlayer, v.mControl, v.mInPits, v.mPlace, vehicleClass, v.mTimeBehindNext, v.mLapsBehindNext,
            v.mTimeBehindLeader, v.mLapsBehindLeader, v.mLapStartET, &pos, &localVel, &localAccel,
            &ori0, &ori1, &ori2, &localRot, &localRotAccel, v.mHeadlights, v.mPitState, v.mServerScored,
            v.mIndividualPhase, v.mQualification, v.mTimeIntoLap, v.mEstimatedLapTime, pitGroup, v.mFlag,
            v.mUnderYellow, v.mCountLapFlag, v.mInGarageStall, v.mPitLapDist, v.mBestLapSector1,
            v.mBestLapSector2, lmu);
    }

    void UpdateScoring(const ScoringInfoV01 &info) override {
        if (!initialized) return;

        // Hot-reload: check if config file was modified
#ifdef _WIN32
        if (configWatcher.CheckAndClearDirty()) {
            // Save current network config to detect changes
            char prevHost[64];
            std::strncpy(prevHost, config.tcpHost, sizeof(prevHost));
            prevHost[sizeof(prevHost) - 1] = '\0';
            int prevBasePort = config.tcpBasePort;
            int prevInboundPort = config.inboundTcpPort;

            LoadConfigFile();

            // Hot-reloadable: rates and flags are already applied by LoadConfigFile()

            // Outbound endpoints changed: re-bind each per-type PUB socket in-place (no context/socket recreation needed).
            if (std::strcmp(prevHost, config.tcpHost) != 0 || prevBasePort != config.tcpBasePort) {
                for (unsigned char packetType : kOutboundPacketTypes) {
                    if (!pubBound[packetType]) continue;
                    char oldEndpoint[96];
                    char newEndpoint[96];
                    BuildTcpEndpoint(prevHost, prevBasePort + packetType, oldEndpoint, sizeof(oldEndpoint));
                    BuildTcpEndpoint(config.tcpHost, config.tcpBasePort + packetType, newEndpoint, sizeof(newEndpoint));
                    try {
                        pubSockets[packetType].unbind(oldEndpoint);
                        pubSockets[packetType].bind(newEndpoint);
                        PluginLog("[RawUDP] Hot-reload: packet type %d endpoint updated to %s", packetType, newEndpoint);
                    } catch (const zmq::error_t& e) {
                        PluginLog("[RawUDP] Hot-reload: failed to rebind packet type %d endpoint to %s: %s", packetType, newEndpoint, e.what());
                    }
                }
            }

            // Inbound endpoint change requires socket re-bind (log warning, same as before: restart required)
            if (prevInboundPort != config.inboundTcpPort) {
                PluginLog("[RawUDP] Hot-reload: InboundTcpPort changed (%d -> %d), restart required to apply",
                          prevInboundPort, config.inboundTcpPort);
            }

            PluginLog("[RawUDP] Configuration hot-reloaded from: %s", resolvedConfigPath);
        }
#endif

        if (config.unsubscribedBuffersMask & UNSUB_SCORING) return;

        // 1. Compact Scoring Packet (Type 2)
        if (compactScoringLimiter.IsEnabled() && compactScoringLimiter.ShouldSend()) {
            long totalLaps = 0;
            signed char sector = 0;
            bool inGarageStall = false;
            unsigned char countLapFlag = 0;
            double curSector1 = 0.0, curSector2 = 0.0, lastSector1 = 0.0, lastSector2 = 0.0;
            double lastLapTime = 0.0, bestSector1 = 0.0, bestSector2 = 0.0, bestLapTime = 0.0;

            // Locate player vehicle scoring record
            if (info.mVehicle != nullptr && info.mNumVehicles > 0) {
                for (int i = 0; i < info.mNumVehicles; ++i) {
                    const auto &v = info.mVehicle[i];
                    if (v.mIsPlayer || v.mControl == 0) {
                        totalLaps = v.mTotalLaps;
                        sector = v.mSector;
                        inGarageStall = v.mInGarageStall;
                        countLapFlag = v.mCountLapFlag;
                        curSector1 = v.mCurSector1;
                        curSector2 = v.mCurSector2;
                        lastSector1 = v.mLastSector1;
                        lastSector2 = v.mLastSector2;
                        lastLapTime = v.mLastLapTime;
                        bestSector1 = v.mBestSector1;
                        bestSector2 = v.mBestSector2;
                        bestLapTime = v.mBestLapTime;
                        break;
                    }
                }
            }

            fbCompactScoringBuilder.Clear();
            auto trackNameOffset = fbCompactScoringBuilder.CreateString(info.mTrackName);
            auto root = isimotor::fbs::CreateCompactScoring(
                fbCompactScoringBuilder, trackNameOffset, info.mSession, info.mCurrentET, info.mLapDist,
                info.mMaxLaps, info.mInRealtime, static_cast<int16_t>(totalLaps), sector, inGarageStall,
                countLapFlag, curSector1, curSector2, lastSector1, lastSector2, lastLapTime,
                bestSector1, bestSector2, bestLapTime);
            fbCompactScoringBuilder.Finish(root);
            SendFlatBuffer(2, fbCompactScoringBuilder);
        }

        // 2. Full Multi-Car Scoring Stream (Type 4)
        if (fullScoringLimiter.IsEnabled() && fullScoringLimiter.ShouldSend() && pubBound[4]) {
            long numVehicles = 0;
            if (info.mVehicle != nullptr && info.mNumVehicles > 0) {
                numVehicles = (info.mNumVehicles > 128) ? 128 : info.mNumVehicles;
            }

            flatbuffers::FlatBufferBuilder &b = fbFullScoringBuilder;
            b.Clear();

            flatbuffers::Offset<isimotor::fbs::VehicleScoring> vehicleOffsets[128];
            for (long i = 0; i < numVehicles; ++i) {
                vehicleOffsets[i] = EncodeVehicleScoringFbs(b, info.mVehicle[i]);
            }
            auto vehiclesVec = b.CreateVector(vehicleOffsets, static_cast<size_t>(numVehicles));

            const LMUExtendedScoring &lmuSrc = info.mLMUExtension;
            auto lmu = isimotor::fbs::CreateLmuScoringSession(
                b, lmuSrc.mTrackGripLevel, lmuSrc.mTrackLimitsStepsPerPoint,
                lmuSrc.mTrackLimitsStepsPerPenalty, lmuSrc.mTimeOfDay);

            auto trackName = b.CreateString(info.mTrackName, strnlen(info.mTrackName, sizeof(info.mTrackName)));
            auto playerName = b.CreateString(info.mPlayerName, strnlen(info.mPlayerName, sizeof(info.mPlayerName)));
            auto plrFileName = b.CreateString(info.mPlrFileName, strnlen(info.mPlrFileName, sizeof(info.mPlrFileName)));

            isimotor::fbs::Vec3 wind(info.mWind.x, info.mWind.y, info.mWind.z);

            auto root = isimotor::fbs::CreateFullScoringSession(
                b, trackName, info.mSession, info.mCurrentET, info.mEndET, info.mMaxLaps, info.mLapDist,
                static_cast<int32_t>(numVehicles), info.mGamePhase, info.mYellowFlagState,
                info.mSectorFlag[0], info.mSectorFlag[1], info.mSectorFlag[2], info.mStartLight,
                info.mNumRedLights, info.mInRealtime, playerName, plrFileName, info.mDarkCloud, info.mRaining,
                info.mAmbientTemp, info.mTrackTemp, &wind, info.mMinPathWetness, info.mMaxPathWetness,
                info.mAvgPathWetness, lmu, vehiclesVec);
            b.Finish(root);
            SendFlatBuffer(4, b);
        }
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

    void SendWeather(const WeatherControlInfoV01 &info) {
        double raining[9];
        for (int r = 0; r < 3; ++r) {
            for (int c = 0; c < 3; ++c) {
                raining[r * 3 + c] = info.mRaining[r][c];
            }
        }
        fbWeatherBuilder.Clear();
        auto rainingOffset = fbWeatherBuilder.CreateVector<double>(raining, 9);
        auto root = isimotor::fbs::CreateWeatherControl(
            fbWeatherBuilder, info.mET, rainingOffset, info.mCloudiness,
            info.mAmbientTempK, info.mWindMaxSpeed, info.mApplyCloudinessInstantly);
        fbWeatherBuilder.Finish(root);
        SendFlatBuffer(7, fbWeatherBuilder);
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
            if (pubBound[7] && !(config.unsubscribedBuffersMask & UNSUB_WEATHER) && weatherLimiter.IsEnabled()) {
                SendWeather(info);
            }
            return true; // Overridden!
        }

        // 2. Standard weather broadcast (FR-04)
        if (config.unsubscribedBuffersMask & UNSUB_WEATHER) return false;
        if (!pubBound[7]) return false;
        if (!weatherLimiter.ShouldSend()) return false;

        SendWeather(info);
        return false;
    }

    // High frequency Force Feedback callback (FR-06, SIMP Type 9 @ up to 400Hz)
    bool ForceFeedback(double &forceValue) override {
        if (!initialized || !pubBound[9]) return false;
        if (config.unsubscribedBuffersMask & UNSUB_FORCE_FEEDBACK) return false;
        if (!forceFeedbackLimiter.ShouldSend()) return false;

        fbForceFeedbackBuilder.Clear();
        auto root = isimotor::fbs::CreateForceFeedback(fbForceFeedbackBuilder, forceValue);
        fbForceFeedbackBuilder.Finish(root);
        SendFlatBuffer(9, fbForceFeedbackBuilder);
        return false; // Return false so game's native FFB calculation is not overridden
    }

    // High frequency Graphics & Camera callback (FR-06, SIMP Type 10 @ 60-100Hz)
    void UpdateGraphics(const GraphicsInfoV02 &info) override {
        if (!initialized || !pubBound[10]) return;
        if (config.unsubscribedBuffersMask & UNSUB_GRAPHICS) return;
        if (!graphicsLimiter.ShouldSend()) return;

        isimotor::fbs::Vec3 camPos(info.mCamPos.x, info.mCamPos.y, info.mCamPos.z);
        isimotor::fbs::Vec3 camOri0(info.mCamOri[0].x, info.mCamOri[0].y, info.mCamOri[0].z);
        isimotor::fbs::Vec3 camOri1(info.mCamOri[1].x, info.mCamOri[1].y, info.mCamOri[1].z);
        isimotor::fbs::Vec3 camOri2(info.mCamOri[2].x, info.mCamOri[2].y, info.mCamOri[2].z);

        fbGraphicsBuilder.Clear();
        auto root = isimotor::fbs::CreateGraphics(
            fbGraphicsBuilder, &camPos, &camOri0, &camOri1, &camOri2,
            info.mAmbientRed, info.mAmbientGreen, info.mAmbientBlue, info.mID, info.mCameraType);
        fbGraphicsBuilder.Finish(root);
        SendFlatBuffer(10, fbGraphicsBuilder);
    }
};

// --- MSVC ABI Compatible VTable Shim for isiMotor (LMU / rFactor 2) Plugin Host ---

struct MsvcInternalsVTable {
    void (*Destructor)(void* self, unsigned int flags);
    void (*Startup)(void* self, long version);
    void (*Shutdown)(void* self);
    void (*Load)(void* self);
    void (*Unload)(void* self);
    void (*StartSession)(void* self);
    void (*EndSession)(void* self);
    void (*EnterRealtime)(void* self);
    void (*ExitRealtime)(void* self);
    bool (*WantsScoringUpdates)(void* self);
    void (*UpdateScoring)(void* self, const ScoringInfoV01 &info);
    long (*WantsTelemetryUpdates)(void* self);
    void (*UpdateTelemetry)(void* self, const TelemInfoV01 &info);
    bool (*WantsGraphicsUpdates)(void* self);
    void (*UpdateGraphics_V01)(void* self, const GraphicsInfoV01 &info);
    bool (*RequestCommentary)(void* self, CommentaryRequestInfoV01 &info);
    bool (*HasHardwareInputs)(void* self);
    void (*UpdateHardware)(void* self, const double fDT);
    void (*EnableHardware)(void* self);
    void (*DisableHardware)(void* self);
    bool (*CheckHWControl)(void* self, const char * const controlName, double &fRetVal);
    bool (*ForceFeedback)(void* self, double &forceValue);
    void (*Error)(void* self, const char * const msg);
    // V02
    void (*SetPhysicsOptions)(void* self, PhysicsOptionsV01 &options);
    // V03
    unsigned char (*WantsToViewVehicle)(void* self, CameraControlInfoV01 &camControl);
    void (*UpdateGraphics_V02)(void* self, const GraphicsInfoV02 &info);
    bool (*WantsToDisplayMessage)(void* self, MessageInfoV01 &msgInfo);
    // V04
    void (*SetEnvironment)(void* self, const EnvironmentInfoV01 &info);
    // V05
    void (*InitScreen)(void* self, const ScreenInfoV01 &info);
    void (*UninitScreen)(void* self, const ScreenInfoV01 &info);
    void (*DeactivateScreen)(void* self, const ScreenInfoV01 &info);
    void (*ReactivateScreen)(void* self, const ScreenInfoV01 &info);
    void (*RenderScreenBeforeOverlays)(void* self, const ScreenInfoV01 &info);
    void (*RenderScreenAfterOverlays)(void* self, const ScreenInfoV01 &info);
    void (*PreReset)(void* self, const ScreenInfoV01 &info);
    void (*PostReset)(void* self, const ScreenInfoV01 &info);
    bool (*InitCustomControl)(void* self, CustomControlInfoV01 &info);
    // V06
    bool (*WantsWeatherAccess)(void* self);
    bool (*AccessWeather)(void* self, double trackNodeSize, WeatherControlInfoV01 &info);
    void (*ThreadStarted)(void* self, long type);
    void (*ThreadStopping)(void* self, long type);
};

#pragma pack(push, 4)
struct MsvcPluginInstance {
    const MsvcInternalsVTable* vtable; // Offset 0: Primary MSVC VTable
    PluginInfo* mInfo;                 // Offset 8: PluginObject::mInfo
    IsiMotorRawUdpPlugin impl;         // Offset 16: Concrete Plugin Implementation
};
#pragma pack(pop)

extern const MsvcInternalsVTable g_MsvcVTable;

static inline IsiMotorRawUdpPlugin* GetPlugin(void* self) {
    if (!self) return nullptr;
    auto* inst = reinterpret_cast<MsvcPluginInstance*>(self);
    return &inst->impl;
}

static void Shim_Destructor(void* self, unsigned int flags) {
    (void)flags;
    PluginLog("Shim_Destructor(self=%p) called", self);
    if (!self) return;
    auto* inst = reinterpret_cast<MsvcPluginInstance*>(self);
    delete inst;
}

static void Shim_Startup(void* self, long version) {
    PluginLog("Shim_Startup(self=%p, version=%ld) called", self, version);
    auto* p = GetPlugin(self);
    if (p) p->Startup(version);
}

static void Shim_Shutdown(void* self) {
    PluginLog("Shim_Shutdown() called");
    auto* p = GetPlugin(self);
    if (p) p->Shutdown();
}

static void Shim_Load(void* self) {
    PluginLog("Shim_Load() called");
    auto* p = GetPlugin(self);
    if (p) p->Load();
}

static void Shim_Unload(void* self) {
    PluginLog("Shim_Unload() called");
    auto* p = GetPlugin(self);
    if (p) p->Unload();
}

static void Shim_StartSession(void* self) {
    PluginLog("Shim_StartSession() called");
    auto* p = GetPlugin(self);
    if (p) p->StartSession();
}

static void Shim_EndSession(void* self) {
    PluginLog("Shim_EndSession() called");
    auto* p = GetPlugin(self);
    if (p) p->EndSession();
}

static void Shim_EnterRealtime(void* self) {
    PluginLog("Shim_EnterRealtime() called");
    auto* p = GetPlugin(self);
    if (p) p->EnterRealtime();
}

static void Shim_ExitRealtime(void* self) {
    PluginLog("Shim_ExitRealtime() called");
    auto* p = GetPlugin(self);
    if (p) p->ExitRealtime();
}

static bool Shim_WantsScoringUpdates(void* self) {
    auto* p = GetPlugin(self);
    return p ? p->WantsScoringUpdates() : false;
}

static void Shim_UpdateScoring(void* self, const ScoringInfoV01 &info) {
    auto* p = GetPlugin(self);
    if (p) p->UpdateScoring(info);
}

static long Shim_WantsTelemetryUpdates(void* self) {
    auto* p = GetPlugin(self);
    return p ? p->WantsTelemetryUpdates() : 0;
}

static void Shim_UpdateTelemetry(void* self, const TelemInfoV01 &info) {
    auto* p = GetPlugin(self);
    if (p) p->UpdateTelemetry(info);
}

static bool Shim_WantsGraphicsUpdates(void* self) {
    auto* p = GetPlugin(self);
    return p ? p->WantsGraphicsUpdates() : false;
}

static void Shim_UpdateGraphics_V01(void* self, const GraphicsInfoV01 &info) {
    (void)self; (void)info;
}

static bool Shim_RequestCommentary(void* self, CommentaryRequestInfoV01 &info) {
    (void)self; (void)info; return false;
}

static bool Shim_HasHardwareInputs(void* self) {
    auto* p = GetPlugin(self);
    return p ? p->HasHardwareInputs() : false;
}

static void Shim_UpdateHardware(void* self, const double fDT) {
    auto* p = GetPlugin(self);
    if (p) p->UpdateHardware(fDT);
}

static void Shim_EnableHardware(void* self) {
    auto* p = GetPlugin(self);
    if (p) p->EnableHardware();
}

static void Shim_DisableHardware(void* self) {
    auto* p = GetPlugin(self);
    if (p) p->DisableHardware();
}

static bool Shim_CheckHWControl(void* self, const char * const controlName, double &fRetVal) {
    auto* p = GetPlugin(self);
    return p ? p->CheckHWControl(controlName, fRetVal) : false;
}

static bool Shim_ForceFeedback(void* self, double &forceValue) {
    auto* p = GetPlugin(self);
    return p ? p->ForceFeedback(forceValue) : false;
}

static void Shim_Error(void* self, const char * const msg) {
    auto* p = GetPlugin(self);
    if (p) p->Error(msg);
}

static void Shim_SetPhysicsOptions(void* self, PhysicsOptionsV01 &options) {
    auto* p = GetPlugin(self);
    if (p) p->SetPhysicsOptions(options);
}

static unsigned char Shim_WantsToViewVehicle(void* self, CameraControlInfoV01 &camControl) {
    (void)self; (void)camControl; return 0;
}

static void Shim_UpdateGraphics_V02(void* self, const GraphicsInfoV02 &info) {
    auto* p = GetPlugin(self);
    if (p) p->UpdateGraphics(info);
}

static bool Shim_WantsToDisplayMessage(void* self, MessageInfoV01 &msgInfo) {
    (void)self; (void)msgInfo; return false;
}

static void Shim_SetEnvironment(void* self, const EnvironmentInfoV01 &info) {
    (void)self; (void)info;
}

static void Shim_InitScreen(void* self, const ScreenInfoV01 &info) {
    (void)self; (void)info;
}

static void Shim_UninitScreen(void* self, const ScreenInfoV01 &info) {
    (void)self; (void)info;
}

static void Shim_DeactivateScreen(void* self, const ScreenInfoV01 &info) {
    (void)self; (void)info;
}

static void Shim_ReactivateScreen(void* self, const ScreenInfoV01 &info) {
    (void)self; (void)info;
}

static void Shim_RenderScreenBeforeOverlays(void* self, const ScreenInfoV01 &info) {
    (void)self; (void)info;
}

static void Shim_RenderScreenAfterOverlays(void* self, const ScreenInfoV01 &info) {
    (void)self; (void)info;
}

static void Shim_PreReset(void* self, const ScreenInfoV01 &info) {
    (void)self; (void)info;
}

static void Shim_PostReset(void* self, const ScreenInfoV01 &info) {
    (void)self; (void)info;
}

static bool Shim_InitCustomControl(void* self, CustomControlInfoV01 &info) {
    (void)self; (void)info; return false;
}

static bool Shim_WantsWeatherAccess(void* self) {
    auto* p = GetPlugin(self);
    return p ? p->WantsWeatherAccess() : false;
}

static bool Shim_AccessWeather(void* self, double trackNodeSize, WeatherControlInfoV01 &info) {
    auto* p = GetPlugin(self);
    return p ? p->AccessWeather(trackNodeSize, info) : false;
}

static void Shim_ThreadStarted(void* self, long type) {
    auto* p = GetPlugin(self);
    if (p) p->ThreadStarted(type);
}

static void Shim_ThreadStopping(void* self, long type) {
    auto* p = GetPlugin(self);
    if (p) p->ThreadStopping(type);
}

const MsvcInternalsVTable g_MsvcVTable = {
    Shim_Destructor,
    Shim_Startup,
    Shim_Shutdown,
    Shim_Load,
    Shim_Unload,
    Shim_StartSession,
    Shim_EndSession,
    Shim_EnterRealtime,
    Shim_ExitRealtime,
    Shim_WantsScoringUpdates,
    Shim_UpdateScoring,
    Shim_WantsTelemetryUpdates,
    Shim_UpdateTelemetry,
    Shim_WantsGraphicsUpdates,
    Shim_UpdateGraphics_V01,
    Shim_RequestCommentary,
    Shim_HasHardwareInputs,
    Shim_UpdateHardware,
    Shim_EnableHardware,
    Shim_DisableHardware,
    Shim_CheckHWControl,
    Shim_ForceFeedback,
    Shim_Error,
    Shim_SetPhysicsOptions,
    Shim_WantsToViewVehicle,
    Shim_UpdateGraphics_V02,
    Shim_WantsToDisplayMessage,
    Shim_SetEnvironment,
    Shim_InitScreen,
    Shim_UninitScreen,
    Shim_DeactivateScreen,
    Shim_ReactivateScreen,
    Shim_RenderScreenBeforeOverlays,
    Shim_RenderScreenAfterOverlays,
    Shim_PreReset,
    Shim_PostReset,
    Shim_InitCustomControl,
    Shim_WantsWeatherAccess,
    Shim_AccessWeather,
    Shim_ThreadStarted,
    Shim_ThreadStopping
};

// --- C Interface Exported for isiMotor (LMU / rFactor 2) Plugin Host ---

extern "C" __declspec(dllexport) const char* __cdecl GetPluginName() {
    return PLUGIN_NAME;
}

extern "C" __declspec(dllexport) PluginObjectType __cdecl GetPluginType() {
    return PO_INTERNALS;
}

extern "C" __declspec(dllexport) int __cdecl GetPluginVersion() {
    return 6; // Corresponds to InternalsPluginV06
}

extern "C" __declspec(dllexport) PluginObject* __cdecl CreatePluginObject() {
    auto* inst = new MsvcPluginInstance();
    inst->vtable = &g_MsvcVTable;
    inst->mInfo = nullptr;
    PluginLog("CreatePluginObject() -> inst=%p, pObj=%p", inst, &inst->mInfo);
    // Return pointer to PluginObject at offset 8 (PluginsAdapter.exe writes to [pObj] and accesses vtable at pObj - 8)
    return reinterpret_cast<PluginObject*>(&inst->mInfo);
}

extern "C" __declspec(dllexport) void __cdecl DestroyPluginObject(PluginObject* obj) {
    if (!obj) return;
    auto* inst = reinterpret_cast<MsvcPluginInstance*>(reinterpret_cast<char*>(obj) - sizeof(void*));
    PluginLog("DestroyPluginObject(obj=%p) -> inst=%p", obj, inst);
    delete inst;
}

