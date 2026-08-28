/**
 * isiMotor C++ Mock Host & Struct Layout Introspector
 * 
 * Provides:
 * 1. Exact memory layout & offset dumping for C++ structs (TelemInfoV01, CompactScoring, SystemEvent, FullScoring, TrackRules, PitMenu, Weather).
 * 2. Golden Binary Dataset Generator (dumps exact C++ memory buffers and corresponding JSON truth).
 * 3. Live UDP Mock Server (streams native C++ struct memory dumps over 127.0.0.1 for end-to-end integration tests).
 */

#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cmath>
#include <chrono>
#include <thread>
#include <vector>
#include <algorithm>

// POSIX socket headers for Linux
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>

// Windows / isiMotor compatibility macros
#define __cdecl
#define __declspec(x)
typedef void* HWND;

// Force 32-bit long as in Windows x64 MSVC ABI
#define long int
#include "../../include/InternalsPlugin.hpp"
#undef long

#pragma pack(push, 4)

struct RawUdpHeader {
    char          magic[4];          // "SIMP"
    uint8_t       protocolVersion;   // 1
    uint8_t       packetType;        // 1=Telem, 2=Scoring, 3=Event, 4=FullScoring, 5=Rules, 6=PitMenu, 7=Weather
    uint16_t      payloadSize;       // Size of chunk payload following header
    uint32_t      sequenceNumber;    // Monotonic stream sequence counter
    double        sessionET;         // Current session elapsed time in seconds
    uint8_t       chunkIndex;        // 0-based chunk index
    uint8_t       totalChunks;       // Total chunks count
    uint16_t      subTypeOrId;       // Active vehicle count or context ID
};

struct CompactScoringPacket {
    char magic[4];           // "SIMP"
    uint8_t packetType;      // 2 = Scoring
    char trackName[64];      // Current track name (null-terminated)
    int32_t session;         // 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race
    double currentET;        // Current session elapsed time in seconds
    double lapDist;          // Track total lap distance in meters
    int32_t maxLaps;         // Maximum laps for session
    bool inRealtime;         // True if in active realtime driving mode
    int16_t totalLaps;       // Player laps completed
    int8_t sector;           // Current sector (0=Sector 3, 1=Sector 1, 2=Sector 2)
    bool inGarageStall;      // True if vehicle is inside the garage stall
    uint8_t countLapFlag;    // 0=invalid, 1=lap count only, 2=valid lap & time
    double curSector1;       // Player current sector 1 time
    double curSector2;       // Player current sector 2 cumulative time (S1 + S2)
    double lastSector1;      // Player last lap sector 1 time
    double lastSector2;      // Player last lap sector 2 cumulative time
    double lastLapTime;      // Player last lap total time
    double bestSector1;      // Player personal best sector 1 time
    double bestSector2;      // Player personal best sector 2 cumulative time
    double bestLapTime;      // Player personal best lap time
};

struct SystemEventPacket {
    char magic[4];           // "SIMP"
    uint8_t packetType;      // 3 = System Event
    uint8_t eventType;       // 1 = EnterRealtime, 2 = ExitRealtime, 3 = StartSession, 4 = EndSession
};

struct FullScoringSessionPacket {
    char          trackName[64];       // Track/circuit name
    int32_t       session;             // 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race
    double        currentET;           // Current session elapsed time in seconds
    double        endET;               // Ending session elapsed time
    int32_t       maxLaps;             // Maximum laps for session
    double        lapDist;             // Track lap distance in meters
    int32_t       numVehicles;         // Number of active vehicles in grid (0..128)
    uint8_t       gamePhase;           // 0=Garage..5=GreenFlag, 6=FCY..8=SessionOver
    int8_t        yellowFlagState;     // -1=Invalid, 0=None, 1=Pending, 2=PitClosed, 3=PitLeadLap, 4=PitOpen, 5=LastLap, 6=Resume
    int8_t        sectorFlag[3];       // Local yellow flags in S3, S1, S2
    uint8_t       startLight;          // Start light frame
    uint8_t       numRedLights;        // Red lights in start sequence
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

struct TrackRulesParticipantPacket {
    int32_t       id;                        // Slot ID
    int16_t       frozenOrder;               // 0-based place when caution was called
    int16_t       place;                     // 1-based place
    float         yellowSeverity;            // Rating of yellow flag contribution
    double        currentRelativeDistance;   // Distance relative to track start/SC
    int32_t       relativeLaps;              // Laps relative to safety car
    int32_t       columnAssignment;          // 0=left, 1=midleft, 2=middle, 3=midright, 4=right, 5=invalid, 6=freechoice, 7=pending
    int32_t       positionAssignment;        // 0-based position within column (-1=invalid)
    uint8_t       pitsOpen;                  // 0=closed, 1=open, 2=false, 3=true
    bool          upToSpeed;                 // Vehicle can be followed
    uint8_t       pad[2];
    double        goalRelativeDistance;      // Target distance behind leader
    char          message[96];               // Participant message
};

struct TrackRulesSessionPacket {
    double        currentET;                 // Current session time
    int32_t       stage;                     // 0=formation_init, 1=formation_update, 2=normal, 3=caution_init, 4=caution_update
    int32_t       poleColumn;                // 0=left..4=right
    int32_t       numActions;                // Recent actions count
    int32_t       numParticipants;           // Active participant count (0..128)
    bool          yellowFlagDetected;        // Caution requested or threshold exceeded
    uint8_t       yellowFlagLapsWasOverridden; // Admin override flag
    bool          safetyCarExists;           // SC exists
    bool          safetyCarActive;           // SC on track
    int32_t       safetyCarLaps;             // SC laps count
    float         safetyCarThreshold;        // SC yellow threshold
    double        safetyCarLapDist;          // SC current track lap distance
    float         safetyCarLapDistAtStart;   // SC start position
    float         pitLaneStartDist;          // Pit entrance dist
    float         teleportLapDist;           // Green flag reference dist
    int8_t        yellowFlagState;           // Yellow flag state
    int16_t       yellowFlagLaps;            // Caution laps count
    uint8_t       pad1;
    int32_t       safetyCarInstruction;      // 0=none, 1=active, 2=head for pits
    float         safetyCarSpeed;            // Max SC speed m/s
    float         safetyCarMinimumSpacing;   // SC min spacing
    float         safetyCarMaximumSpacing;   // SC max spacing
    float         minimumColumnSpacing;      // Column min spacing
    float         maximumColumnSpacing;      // Column max spacing
    float         minimumSpeed;              // Min speed
    float         maximumSpeed;              // Max speed
    char          message[96];               // Global session message
};

struct PitMenuPacket {
    int32_t       categoryIndex;             // Current category index
    char          categoryName[32];          // Category name (e.g. "Tires", "Fuel")
    int32_t       choiceIndex;               // Current choice index
    char          choiceString[32];          // Choice string (e.g. "Soft Slick", "+35 L")
    int32_t       numChoices;                // Total available choices in category
};

struct WeatherPacket {
    double        et;                        // Effective session ET
    double        raining[3][3];             // Rain intensity grid
    double        cloudiness;                // Cloud cover (0.0 - 1.0)
    double        ambientTempK;              // Ambient temperature (Kelvin)
    double        windMaxSpeed;              // Wind speed (m/s)
    bool          applyCloudinessInstantly;  // Instant cloud application flag
    uint8_t       pad[3];
};

struct ExtendedStatePacket {
    // Physics options (40 bytes)
    uint8_t       tractionControl;           // 0 (off) - 3 (high)
    uint8_t       antiLockBrakes;            // 0 (off) - 2 (high)
    uint8_t       stabilityControl;          // 0 (off) - 2 (high)
    uint8_t       autoShift;                 // 0 (off), 1 (upshifts), 2 (downshifts), 3 (all)
    uint8_t       autoClutch;                // 0 (off), 1 (on)
    uint8_t       invulnerable;              // 0 (off), 1 (on)
    uint8_t       oppositeLock;              // 0 (off), 1 (on)
    uint8_t       steeringHelp;              // 0 (off) - 3 (high)
    uint8_t       brakingHelp;               // 0 (off) - 2 (high)
    uint8_t       spinRecovery;              // 0 (off), 1 (on)
    uint8_t       autoPit;                   // 0 (off), 1 (on)
    uint8_t       autoLift;                  // 0 (off), 1 (on)
    uint8_t       autoBlip;                  // 0 (off), 1 (on)
    uint8_t       fuelMult;                  // fuel multiplier (0x-7x)
    uint8_t       tireMult;                  // tire wear multiplier (0x-7x)
    uint8_t       mechFail;                  // mechanical failure (0=off, 1=normal, 2=timescaled)
    uint8_t       allowPitcrewPush;          // 0 (off), 1 (on)
    uint8_t       repeatShifts;              // accidental repeat shift prevention (0-5)
    uint8_t       holdClutch;                // 0 (off), 1 (on)
    uint8_t       autoReverse;               // 0 (off), 1 (on)
    uint8_t       alternateNeutral;          // 0 (off), 1 (on)
    uint8_t       aiControl;                 // 0 (player), 1 (AI)
    uint8_t       pad1[2];
    float         manualShiftOverrideTime;   // time before auto-shift can resume
    float         autoShiftOverrideTime;     // time before manual shift can resume
    float         speedSensitiveSteering;    // 0.0 (off) - 1.0
    float         steerRatioSpeed;           // speed (m/s) under which lock expands
    
    // Accumulated damage tracking (16 bytes)
    double        maxImpactMagnitude;        // Max collision impact recorded in session
    double        accumulatedImpactMagnitude; // Cumulative collision damage energy

    // Session status & transitions (12 bytes)
    bool          inRealtimeFC;              // In realtime cockpit mode
    bool          sessionStarted;            // Session started flag
    uint8_t       pad2[2];
    int32_t       session;                   // Current session index
    float         currentPitSpeedLimit;      // Pit speed limit m/s
};

struct ForceFeedbackPacket {
    double forceValue;                      // Steering shaft torque value
};

struct GraphicsPacket {
    TelemVect3 camPos;                      // Camera 3D world position
    TelemVect3 camOri[3];                   // Camera 3x3 orientation matrix
    double     ambientRed;                  // Ambient light RGB
    double     ambientGreen;
    double     ambientBlue;
    int32_t    slotId;                      // Slot ID being viewed (-1 if none)
    int32_t    cameraType;                  // Camera viewpoint type
};

struct HWControlCommandPacket {
    char          controlName[32];       // Control name (e.g. "PitMenuUp", "PitMenuSelect", "TCIncrease")
    double        controlValue;          // 1.0 = press/on, 0.0 = release/off, or analog value
    uint16_t      durationMs;            // Pulse duration in ms (e.g. 50ms)
    uint8_t       pad[2];                // Explicit 4-byte struct padding
};

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

// ── Populate Golden Test Vectors ─────────────────────────────────────────────

void populate_golden_telemetry(TelemInfoV01 &t) {
    std::memset(&t, 0, sizeof(t));

    t.mID = 42;
    t.mDeltaTime = 0.0166667;
    t.mElapsedTime = 125.456;
    t.mLapNumber = 7;
    t.mLapStartET = 45.123;
    std::strncpy(t.mVehicleName, "Ferrari 499P #51", sizeof(t.mVehicleName) - 1);
    std::strncpy(t.mTrackName, "Circuit de la Sarthe - Le Mans", sizeof(t.mTrackName) - 1);

    t.mPos.Set(-1250.5, 45.25, 3420.75);
    t.mLocalVel.Set(-1.5, 0.2, -78.5);
    t.mLocalAccel.Set(-2.4, 9.81, 14.2);

    t.mOri[0].Set(0.9998, 0.001, -0.015);
    t.mOri[1].Set(-0.001, 0.9999, 0.002);
    t.mOri[2].Set(0.015, -0.002, 0.9998);

    t.mLocalRot.Set(0.012, -0.045, 0.003);
    t.mLocalRotAccel.Set(0.15, -0.85, 0.05);

    t.mGear = 5;
    t.mEngineRPM = 8450.5;
    t.mEngineWaterTemp = 88.5;
    t.mEngineOilTemp = 104.2;
    t.mClutchRPM = 8448.0;

    t.mUnfilteredThrottle = 0.95;
    t.mUnfilteredBrake = 0.0;
    t.mUnfilteredSteering = -0.125;
    t.mUnfilteredClutch = 0.0;

    t.mFilteredThrottle = 0.92;
    t.mFilteredBrake = 0.0;
    t.mFilteredSteering = -0.120;
    t.mFilteredClutch = 0.0;

    t.mSteeringShaftTorque = -4.75;
    t.mFront3rdDeflection = 0.0125;
    t.mRear3rdDeflection = 0.0150;

    t.mFrontWingHeight = 0.045;
    t.mFrontRideHeight = 0.038;
    t.mRearRideHeight = 0.052;
    t.mDrag = 1850.0;
    t.mFrontDownforce = 3200.0;
    t.mRearDownforce = 4800.0;

    t.mFuel = 42.5;
    t.mEngineMaxRPM = 9200.0;
    t.mScheduledStops = 2;
    t.mOverheating = false;
    t.mDetached = false;
    t.mHeadlights = true;
    for (int i = 0; i < 8; ++i) t.mDentSeverity[i] = (i == 2 ? 1 : 0);

    t.mLastImpactET = 12.5;
    t.mLastImpactMagnitude = 1450.0;
    t.mLastImpactPos.Set(0.8, 0.2, 1.5);

    t.mEngineTorque = 620.5;
    t.mCurrentSector = 2;
    t.mSpeedLimiter = 0;
    t.mMaxGears = 7;
    t.mFrontTireCompoundIndex = 1;
    t.mRearTireCompoundIndex = 1;
    t.mFuelCapacity = 68.0;
    t.mFrontFlapActivated = 0;
    t.mRearFlapActivated = 1;
    t.mRearFlapLegalStatus = 2;
    t.mIgnitionStarter = 1;
    std::strncpy(t.mFrontTireCompoundName, "Soft Slick", sizeof(t.mFrontTireCompoundName) - 1);
    std::strncpy(t.mRearTireCompoundName, "Soft Slick", sizeof(t.mRearTireCompoundName) - 1);

    t.mSpeedLimiterAvailable = 1;
    t.mAntiStallActivated = 0;
    t.mVisualSteeringWheelRange = 450.0f;
    t.mRearBrakeBias = 0.46;
    t.mTurboBoostPressure = 145.2;
    t.mPhysicsToGraphicsOffset[0] = 0.0f;
    t.mPhysicsToGraphicsOffset[1] = 0.05f;
    t.mPhysicsToGraphicsOffset[2] = -0.10f;
    t.mPhysicalSteeringWheelRange = 450.0f;

    t.mBatteryChargeFraction = 0.785;
    t.mElectricBoostMotorTorque = 180.0;
    t.mElectricBoostMotorRPM = 16500.0;
    t.mElectricBoostMotorTemperature = 65.4;
    t.mElectricBoostWaterTemperature = 45.2;
    t.mElectricBoostMotorState = 2;

    const char* compounds[4] = {"FL_Asphalt", "FR_Asphalt", "RL_Asphalt", "RR_Asphalt"};
    for (int w = 0; w < 4; ++w) {
        auto &wheel = t.mWheel[w];
        wheel.mSuspensionDeflection = 0.025 + w * 0.002;
        wheel.mRideHeight = 0.040 + w * 0.001;
        wheel.mSuspForce = 4500.0 + w * 250.0;
        wheel.mBrakeTemp = 420.0 + w * 15.0;
        wheel.mBrakePressure = 0.0;
        wheel.mRotation = 145.2 + w * 0.5;
        wheel.mLateralPatchVel = 0.85 + w * 0.1;
        wheel.mLongitudinalPatchVel = 78.4 + w * 0.2;
        wheel.mLateralGroundVel = 0.80 + w * 0.1;
        wheel.mLongitudinalGroundVel = 78.5;
        wheel.mCamber = -0.052 + w * 0.005;
        wheel.mLateralForce = 3200.0 + w * 100.0;
        wheel.mLongitudinalForce = 1500.0 - w * 50.0;
        wheel.mTireLoad = 4800.0 + w * 200.0;
        wheel.mGripFract = 0.94;
        wheel.mPressure = 172.5 + w * 1.5;
        wheel.mTemperature[0] = 365.15; // Kelvin (~92 C)
        wheel.mTemperature[1] = 368.15; // Kelvin (~95 C)
        wheel.mTemperature[2] = 363.15; // Kelvin (~90 C)
        wheel.mWear = 0.05 + w * 0.01;
        std::strncpy(wheel.mTerrainName, compounds[w], sizeof(wheel.mTerrainName) - 1);
        wheel.mSurfaceType = 0; // dry
        wheel.mFlat = false;
        wheel.mDetached = false;
        wheel.mStaticUndeflectedRadius = 34;
        wheel.mVerticalTireDeflection = 0.008;
        wheel.mWheelYLocation = 0.35;
        wheel.mToe = 0.002 - w * 0.001;
        wheel.mTireCarcassTemperature = 360.15;
        wheel.mTireInnerLayerTemperature[0] = 366.15;
        wheel.mTireInnerLayerTemperature[1] = 369.15;
        wheel.mTireInnerLayerTemperature[2] = 364.15;
    }
}

void populate_golden_scoring(CompactScoringPacket &s) {
    std::memset(&s, 0, sizeof(s));
    s.magic[0] = 'S'; s.magic[1] = 'I'; s.magic[2] = 'M'; s.magic[3] = 'P';
    s.packetType = 2;
    std::strncpy(s.trackName, "Circuit de la Sarthe - Le Mans", sizeof(s.trackName) - 1);
    s.session = 10; // Race 1
    s.currentET = 1250.456;
    s.lapDist = 13626.0;
    s.maxLaps = 24;
    s.inRealtime = true;
    s.totalLaps = 8;
    s.sector = 2;
    s.inGarageStall = false;
    s.countLapFlag = 2;
    s.curSector1 = 41.250;
    s.curSector2 = 124.500;
    s.lastSector1 = 40.950;
    s.lastSector2 = 123.850;
    s.lastLapTime = 205.420;
    s.bestSector1 = 40.820;
    s.bestSector2 = 123.500;
    s.bestLapTime = 204.850;
}

void populate_golden_full_scoring(FullScoringSessionPacket &sess, std::vector<VehicleScoringInfoV01> &vehicles) {
    std::memset(&sess, 0, sizeof(sess));
    std::strncpy(sess.trackName, "Circuit de la Sarthe - Le Mans", sizeof(sess.trackName) - 1);
    sess.session = 10; // Race 1
    sess.currentET = 1250.456;
    sess.endET = 86400.0;
    sess.maxLaps = 24;
    sess.lapDist = 13626.0;
    sess.numVehicles = 3;
    sess.gamePhase = 5; // GreenFlag
    sess.yellowFlagState = 0; // None
    sess.sectorFlag[0] = 0; sess.sectorFlag[1] = 0; sess.sectorFlag[2] = 0;
    sess.startLight = 0;
    sess.numRedLights = 0;
    sess.inRealtime = true;
    std::strncpy(sess.playerName, "Marc Gardent", sizeof(sess.playerName) - 1);
    std::strncpy(sess.plrFileName, "Marc_Gardent.plr", sizeof(sess.plrFileName) - 1);
    sess.darkCloud = 0.15;
    sess.raining = 0.0;
    sess.ambientTemp = 24.5;
    sess.trackTemp = 32.8;
    sess.wind.Set(2.5, 0.0, 1.2);
    sess.minPathWetness = 0.0;
    sess.maxPathWetness = 0.0;
    sess.avgPathWetness = 0.0;

    vehicles.resize(3);
    for (size_t i = 0; i < 3; ++i) {
        std::memset(&vehicles[i], 0, sizeof(VehicleScoringInfoV01));
    }

    // Car 1 (Player - Ferrari 499P #51 - P1)
    vehicles[0].mID = 51;
    std::strncpy(vehicles[0].mDriverName, "Marc Gardent", sizeof(vehicles[0].mDriverName) - 1);
    std::strncpy(vehicles[0].mVehicleName, "Ferrari 499P #51", sizeof(vehicles[0].mVehicleName) - 1);
    std::strncpy(vehicles[0].mVehicleClass, "Hypercar", sizeof(vehicles[0].mVehicleClass) - 1);
    vehicles[0].mTotalLaps = 8;
    vehicles[0].mSector = 2;
    vehicles[0].mFinishStatus = 0;
    vehicles[0].mLapDist = 8450.0;
    vehicles[0].mBestSector1 = 40.820;
    vehicles[0].mBestSector2 = 123.500;
    vehicles[0].mBestLapTime = 204.850;
    vehicles[0].mLastLapTime = 205.420;
    vehicles[0].mNumPitstops = 1;
    vehicles[0].mIsPlayer = true;
    vehicles[0].mControl = 0;
    vehicles[0].mPlace = 1;

    // Car 2 (Toyota GR010 #7 - P2)
    vehicles[1].mID = 7;
    std::strncpy(vehicles[1].mDriverName, "Kamui Kobayashi", sizeof(vehicles[1].mDriverName) - 1);
    std::strncpy(vehicles[1].mVehicleName, "Toyota GR010 #7", sizeof(vehicles[1].mVehicleName) - 1);
    std::strncpy(vehicles[1].mVehicleClass, "Hypercar", sizeof(vehicles[1].mVehicleClass) - 1);
    vehicles[1].mTotalLaps = 8;
    vehicles[1].mPlace = 2;
    vehicles[1].mTimeBehindLeader = 1.450;
    vehicles[1].mBestLapTime = 205.110;
    vehicles[1].mLastLapTime = 205.650;

    // Car 3 (Porsche 963 #6 - P3, in pits)
    vehicles[2].mID = 6;
    std::strncpy(vehicles[2].mDriverName, "Kevin Estre", sizeof(vehicles[2].mDriverName) - 1);
    std::strncpy(vehicles[2].mVehicleName, "Porsche 963 #6", sizeof(vehicles[2].mVehicleName) - 1);
    vehicles[2].mPlace = 3;
    vehicles[2].mInPits = true;
    vehicles[2].mPitState = 3;
    vehicles[2].mTimeBehindLeader = 4.650;
}

void populate_golden_track_rules(TrackRulesSessionPacket &rules, std::vector<TrackRulesParticipantPacket> &participants) {
    std::memset(&rules, 0, sizeof(rules));
    rules.currentET = 1250.456;
    rules.stage = 4; // Caution Update (FCY)
    rules.poleColumn = 0; // Left
    rules.numActions = 1;
    rules.numParticipants = 3;
    rules.yellowFlagDetected = true;
    rules.yellowFlagLapsWasOverridden = 0;
    rules.safetyCarExists = true;
    rules.safetyCarActive = true;
    rules.safetyCarLaps = 2;
    rules.safetyCarThreshold = 1.0f;
    rules.safetyCarLapDist = 4520.0;
    rules.safetyCarLapDistAtStart = 0.0f;
    rules.pitLaneStartDist = 13200.0f;
    rules.teleportLapDist = 500.0f;
    rules.yellowFlagState = 4; // PitOpen
    rules.yellowFlagLaps = 3;
    rules.safetyCarInstruction = 1; // Active
    rules.safetyCarSpeed = 22.22f; // 80 km/h in m/s
    rules.safetyCarMinimumSpacing = 10.0f;
    rules.safetyCarMaximumSpacing = 30.0f;
    rules.minimumColumnSpacing = 5.0f;
    rules.maximumColumnSpacing = 20.0f;
    rules.minimumSpeed = 15.0f;
    rules.maximumSpeed = 25.0f;
    std::strncpy(rules.message, "Full Course Yellow - Follow Safety Car", sizeof(rules.message) - 1);

    participants.resize(3);
    for (size_t i = 0; i < 3; ++i) {
        std::memset(&participants[i], 0, sizeof(TrackRulesParticipantPacket));
    }

    // Car 1 (Player - P1)
    participants[0].id = 51;
    participants[0].frozenOrder = 0;
    participants[0].place = 1;
    participants[0].yellowSeverity = 0.0f;
    participants[0].currentRelativeDistance = 4500.0;
    participants[0].relativeLaps = 0;
    participants[0].columnAssignment = 0; // Left Lane
    participants[0].positionAssignment = 0;
    participants[0].pitsOpen = 3; // True
    participants[0].upToSpeed = true;
    participants[0].goalRelativeDistance = 4510.0;
    std::strncpy(participants[0].message, "Follow Safety Car", sizeof(participants[0].message) - 1);

    // Car 2 (P2)
    participants[1].id = 7;
    participants[1].frozenOrder = 1;
    participants[1].place = 2;
    participants[1].yellowSeverity = 0.0f;
    participants[1].currentRelativeDistance = 4485.0;
    participants[1].relativeLaps = 0;
    participants[1].columnAssignment = 0;
    participants[1].positionAssignment = 1;
    participants[1].pitsOpen = 3;
    participants[1].upToSpeed = true;
    participants[1].goalRelativeDistance = 4495.0;
    std::strncpy(participants[1].message, "Follow Car #51", sizeof(participants[1].message) - 1);

    // Car 3 (P3, caused caution)
    participants[2].id = 6;
    participants[2].frozenOrder = 2;
    participants[2].place = 3;
    participants[2].yellowSeverity = 1.5f;
    participants[2].currentRelativeDistance = 120.0;
    participants[2].relativeLaps = 1;
    participants[2].columnAssignment = 5; // Invalid / Pits
    participants[2].positionAssignment = -1;
    participants[2].pitsOpen = 3;
    participants[2].upToSpeed = false;
    participants[2].goalRelativeDistance = 0.0;
    std::strncpy(participants[2].message, "In Pits", sizeof(participants[2].message) - 1);
}

void populate_golden_pit_menu(PitMenuPacket &p) {
    std::memset(&p, 0, sizeof(p));
    p.categoryIndex = 1;
    std::strncpy(p.categoryName, "Tires", sizeof(p.categoryName) - 1);
    p.choiceIndex = 0;
    std::strncpy(p.choiceString, "Soft Slick", sizeof(p.choiceString) - 1);
    p.numChoices = 4;
}

void populate_golden_weather(WeatherPacket &w) {
    std::memset(&w, 0, sizeof(w));
    w.et = 1250.456;
    for (int r = 0; r < 3; ++r) {
        for (int c = 0; c < 3; ++c) {
            w.raining[r][c] = (r == 1 && c == 1) ? 0.05 : 0.0;
        }
    }
    w.cloudiness = 0.25;
    w.ambientTempK = 297.65; // 24.5 °C
    w.windMaxSpeed = 4.5;
    w.applyCloudinessInstantly = false;
}

void populate_golden_extended(ExtendedStatePacket &ext) {
    std::memset(&ext, 0, sizeof(ext));
    ext.tractionControl = 2;          // Medium
    ext.antiLockBrakes = 1;           // Low
    ext.stabilityControl = 0;         // Off
    ext.autoShift = 0;                // Manual
    ext.autoClutch = 1;               // On
    ext.invulnerable = 0;
    ext.oppositeLock = 0;
    ext.steeringHelp = 0;
    ext.brakingHelp = 0;
    ext.spinRecovery = 0;
    ext.autoPit = 0;
    ext.autoLift = 0;
    ext.autoBlip = 1;                // On
    ext.fuelMult = 1;
    ext.tireMult = 2;                // 2x
    ext.mechFail = 1;                // Normal
    ext.allowPitcrewPush = 1;
    ext.repeatShifts = 0;
    ext.holdClutch = 0;
    ext.autoReverse = 0;
    ext.alternateNeutral = 0;
    ext.aiControl = 0;               // Player
    ext.pad1[0] = 0; ext.pad1[1] = 0;
    ext.manualShiftOverrideTime = 0.5f;
    ext.autoShiftOverrideTime = 0.3f;
    ext.speedSensitiveSteering = 0.15f;
    ext.steerRatioSpeed = 25.0f;

    ext.maxImpactMagnitude = 1845.50;
    ext.accumulatedImpactMagnitude = 3250.75;
    ext.inRealtimeFC = true;
    ext.sessionStarted = true;
    ext.pad2[0] = 0; ext.pad2[1] = 0;
    ext.session = 10;                // Race
    ext.currentPitSpeedLimit = 16.6667f; // 60 km/h
}

void populate_golden_ffb(ForceFeedbackPacket &ffb) {
    std::memset(&ffb, 0, sizeof(ffb));
    ffb.forceValue = 0.685;
}

void populate_golden_graphics(GraphicsPacket &gfx) {
    std::memset(&gfx, 0, sizeof(gfx));
    gfx.camPos.Set(-1250.5, 46.8, 3420.2);
    gfx.camOri[0].Set(1.0, 0.0, 0.0);
    gfx.camOri[1].Set(0.0, 1.0, 0.0);
    gfx.camOri[2].Set(0.0, 0.0, 1.0);
    gfx.ambientRed = 0.85;
    gfx.ambientGreen = 0.88;
    gfx.ambientBlue = 0.92;
    gfx.slotId = 42;
    gfx.cameraType = 1; // Cockpit
}

void populate_golden_event(SystemEventPacket &ev, uint8_t type = 1) {
    std::memset(&ev, 0, sizeof(ev));
    ev.magic[0] = 'S'; ev.magic[1] = 'I'; ev.magic[2] = 'M'; ev.magic[3] = 'P';
    ev.packetType = 3;
    ev.eventType = type;
}

void populate_golden_hw_control(HWControlCommandPacket &hw) {
    std::memset(&hw, 0, sizeof(hw));
    std::strncpy(hw.controlName, "PitMenuNext", sizeof(hw.controlName) - 1);
    hw.controlValue = 1.0;
    hw.durationMs = 50;
    hw.pad[0] = 0; hw.pad[1] = 0;
}

void populate_golden_weather_control(WeatherControlCommandPacket &w) {
    std::memset(&w, 0, sizeof(w));
    w.ambientTemp = 24.5;
    w.trackTemp = 29.8;
    w.darkCloud = 0.75;
    w.raining = 0.45;
    w.windSpeed = 4.2;
    w.windDirection = 1.5708;
    w.minPathWetness = 0.2;
    w.maxPathWetness = 0.8;
}

// ── JSON & Binary Dumper ──────────────────────────────────────────────────────

void dump_truth(const std::string &bin_telem_path, const std::string &json_telem_path,
                const std::string &bin_scoring_path, const std::string &json_scoring_path,
                const std::string &bin_full_scoring_path, const std::string &json_full_scoring_path,
                const std::string &bin_rules_path, const std::string &json_rules_path,
                const std::string &bin_pit_path, const std::string &json_pit_path,
                const std::string &bin_weather_path, const std::string &json_weather_path,
                const std::string &bin_ext_path, const std::string &json_ext_path,
                const std::string &bin_ffb_path, const std::string &json_ffb_path,
                const std::string &bin_gfx_path, const std::string &json_gfx_path,
                const std::string &bin_event_path, const std::string &json_event_path) {
    // 1. Telemetry
    TelemInfoV01 t;
    populate_golden_telemetry(t);
    std::ofstream fb_t(bin_telem_path, std::ios::binary);
    fb_t.write(reinterpret_cast<const char*>(&t), sizeof(t));
    fb_t.close();

    std::ofstream fj_t(json_telem_path);
    fj_t << std::setprecision(6) << std::fixed;
    fj_t << "{\n";
    fj_t << "  \"struct_size\": " << sizeof(t) << ",\n";
    fj_t << "  \"slot_id\": " << t.mID << ",\n";
    fj_t << "  \"delta_time\": " << t.mDeltaTime << ",\n";
    fj_t << "  \"elapsed_time\": " << t.mElapsedTime << ",\n";
    fj_t << "  \"lap_number\": " << t.mLapNumber << ",\n";
    fj_t << "  \"lap_start_et\": " << t.mLapStartET << ",\n";
    fj_t << "  \"vehicle_name\": \"" << t.mVehicleName << "\",\n";
    fj_t << "  \"track_name\": \"" << t.mTrackName << "\",\n";
    fj_t << "  \"pos\": [" << t.mPos.x << ", " << t.mPos.y << ", " << t.mPos.z << "],\n";
    fj_t << "  \"local_vel\": [" << t.mLocalVel.x << ", " << t.mLocalVel.y << ", " << t.mLocalVel.z << "],\n";
    fj_t << "  \"local_accel\": [" << t.mLocalAccel.x << ", " << t.mLocalAccel.y << ", " << t.mLocalAccel.z << "],\n";
    fj_t << "  \"gear\": " << t.mGear << ",\n";
    fj_t << "  \"engine_rpm\": " << t.mEngineRPM << ",\n";
    fj_t << "  \"engine_water_temp\": " << t.mEngineWaterTemp << ",\n";
    fj_t << "  \"engine_oil_temp\": " << t.mEngineOilTemp << ",\n";
    fj_t << "  \"unfiltered_throttle\": " << t.mUnfilteredThrottle << ",\n";
    fj_t << "  \"unfiltered_brake\": " << t.mUnfilteredBrake << ",\n";
    fj_t << "  \"unfiltered_steering\": " << t.mUnfilteredSteering << ",\n";
    fj_t << "  \"fuel\": " << t.mFuel << ",\n";
    fj_t << "  \"fuel_capacity\": " << t.mFuelCapacity << ",\n";
    fj_t << "  \"battery_charge_fraction\": " << t.mBatteryChargeFraction << ",\n";
    fj_t << "  \"electric_boost_motor_torque\": " << t.mElectricBoostMotorTorque << ",\n";
    fj_t << "  \"electric_boost_motor_rpm\": " << t.mElectricBoostMotorRPM << ",\n";
    fj_t << "  \"wheels\": [\n";
    for (int i = 0; i < 4; ++i) {
        const auto &w = t.mWheel[i];
        fj_t << "    {\n";
        fj_t << "      \"suspension_deflection\": " << w.mSuspensionDeflection << ",\n";
        fj_t << "      \"ride_height\": " << w.mRideHeight << ",\n";
        fj_t << "      \"susp_force\": " << w.mSuspForce << ",\n";
        fj_t << "      \"brake_temp\": " << w.mBrakeTemp << ",\n";
        fj_t << "      \"pressure\": " << w.mPressure << ",\n";
        fj_t << "      \"wear\": " << w.mWear << ",\n";
        fj_t << "      \"terrain_name\": \"" << w.mTerrainName << "\",\n";
        fj_t << "      \"temp_celsius\": [" << (w.mTemperature[0] - 273.15) << ", " << (w.mTemperature[1] - 273.15) << ", " << (w.mTemperature[2] - 273.15) << "]\n";
        fj_t << "    }" << (i < 3 ? "," : "") << "\n";
    }
    fj_t << "  ]\n";
    fj_t << "}\n";
    fj_t.close();

    // 2. Compact Scoring
    CompactScoringPacket s;
    populate_golden_scoring(s);
    std::ofstream fb_s(bin_scoring_path, std::ios::binary);
    fb_s.write(reinterpret_cast<const char*>(&s), sizeof(s));
    fb_s.close();

    std::ofstream fj_s(json_scoring_path);
    fj_s << std::setprecision(6) << std::fixed;
    fj_s << "{\n";
    fj_s << "  \"struct_size\": " << sizeof(s) << ",\n";
    fj_s << "  \"track_name\": \"" << s.trackName << "\",\n";
    fj_s << "  \"session\": " << s.session << ",\n";
    fj_s << "  \"current_et\": " << s.currentET << ",\n";
    fj_s << "  \"lap_dist\": " << s.lapDist << ",\n";
    fj_s << "  \"max_laps\": " << s.maxLaps << ",\n";
    fj_s << "  \"in_realtime\": " << (s.inRealtime ? "true" : "false") << ",\n";
    fj_s << "  \"total_laps\": " << s.totalLaps << ",\n";
    fj_s << "  \"sector\": " << static_cast<int>(s.sector) << ",\n";
    fj_s << "  \"last_lap_time\": " << s.lastLapTime << ",\n";
    fj_s << "  \"best_lap_time\": " << s.bestLapTime << "\n";
    fj_s << "}\n";
    fj_s.close();

    // 3. Full Scoring (Session Header + 3 Vehicles)
    FullScoringSessionPacket fs_sess;
    std::vector<VehicleScoringInfoV01> fs_vehs;
    populate_golden_full_scoring(fs_sess, fs_vehs);

    std::ofstream fb_fs(bin_full_scoring_path, std::ios::binary);
    fb_fs.write(reinterpret_cast<const char*>(&fs_sess), sizeof(fs_sess));
    fb_fs.write(reinterpret_cast<const char*>(fs_vehs.data()), fs_vehs.size() * sizeof(VehicleScoringInfoV01));
    fb_fs.close();

    std::ofstream fj_fs(json_full_scoring_path);
    fj_fs << std::setprecision(6) << std::fixed;
    fj_fs << "{\n";
    fj_fs << "  \"session_header_size\": " << sizeof(fs_sess) << ",\n";
    fj_fs << "  \"vehicle_struct_size\": " << sizeof(VehicleScoringInfoV01) << ",\n";
    fj_fs << "  \"track_name\": \"" << fs_sess.trackName << "\",\n";
    fj_fs << "  \"session\": " << fs_sess.session << ",\n";
    fj_fs << "  \"current_et\": " << fs_sess.currentET << ",\n";
    fj_fs << "  \"end_et\": " << fs_sess.endET << ",\n";
    fj_fs << "  \"max_laps\": " << fs_sess.maxLaps << ",\n";
    fj_fs << "  \"lap_dist\": " << fs_sess.lapDist << ",\n";
    fj_fs << "  \"num_vehicles\": " << fs_sess.numVehicles << ",\n";
    fj_fs << "  \"ambient_temp\": " << fs_sess.ambientTemp << ",\n";
    fj_fs << "  \"track_temp\": " << fs_sess.trackTemp << ",\n";
    fj_fs << "  \"vehicles\": [\n";
    for (size_t i = 0; i < fs_vehs.size(); ++i) {
        const auto &v = fs_vehs[i];
        fj_fs << "    {\n";
        fj_fs << "      \"id\": " << v.mID << ",\n";
        fj_fs << "      \"driver_name\": \"" << v.mDriverName << "\",\n";
        fj_fs << "      \"vehicle_name\": \"" << v.mVehicleName << "\",\n";
        fj_fs << "      \"vehicle_class\": \"" << v.mVehicleClass << "\",\n";
        fj_fs << "      \"total_laps\": " << v.mTotalLaps << ",\n";
        fj_fs << "      \"place\": " << static_cast<int>(v.mPlace) << ",\n";
        fj_fs << "      \"is_player\": " << (v.mIsPlayer ? "true" : "false") << ",\n";
        fj_fs << "      \"in_pits\": " << (v.mInPits ? "true" : "false") << ",\n";
        fj_fs << "      \"time_behind_leader\": " << v.mTimeBehindLeader << ",\n";
        fj_fs << "      \"best_lap_time\": " << v.mBestLapTime << ",\n";
        fj_fs << "      \"last_lap_time\": " << v.mLastLapTime << "\n";
        fj_fs << "    }" << (i + 1 < fs_vehs.size() ? "," : "") << "\n";
    }
    fj_fs << "  ]\n";
    fj_fs << "}\n";
    fj_fs.close();

    // 4. Track Rules (Session Header + 3 Participants)
    TrackRulesSessionPacket tr_sess;
    std::vector<TrackRulesParticipantPacket> tr_parts;
    populate_golden_track_rules(tr_sess, tr_parts);

    std::ofstream fb_tr(bin_rules_path, std::ios::binary);
    fb_tr.write(reinterpret_cast<const char*>(&tr_sess), sizeof(tr_sess));
    fb_tr.write(reinterpret_cast<const char*>(tr_parts.data()), tr_parts.size() * sizeof(TrackRulesParticipantPacket));
    fb_tr.close();

    std::ofstream fj_tr(json_rules_path);
    fj_tr << std::setprecision(6) << std::fixed;
    fj_tr << "{\n";
    fj_tr << "  \"rules_header_size\": " << sizeof(tr_sess) << ",\n";
    fj_tr << "  \"participant_size\": " << sizeof(TrackRulesParticipantPacket) << ",\n";
    fj_tr << "  \"current_et\": " << tr_sess.currentET << ",\n";
    fj_tr << "  \"stage\": " << tr_sess.stage << ",\n";
    fj_tr << "  \"pole_column\": " << tr_sess.poleColumn << ",\n";
    fj_tr << "  \"num_participants\": " << tr_sess.numParticipants << ",\n";
    fj_tr << "  \"safety_car_active\": " << (tr_sess.safetyCarActive ? "true" : "false") << ",\n";
    fj_tr << "  \"yellow_flag_detected\": " << (tr_sess.yellowFlagDetected ? "true" : "false") << ",\n";
    fj_tr << "  \"yellow_flag_state\": " << static_cast<int>(tr_sess.yellowFlagState) << ",\n";
    fj_tr << "  \"safety_car_speed\": " << tr_sess.safetyCarSpeed << ",\n";
    fj_tr << "  \"message\": \"" << tr_sess.message << "\",\n";
    fj_tr << "  \"participants\": [\n";
    for (size_t i = 0; i < tr_parts.size(); ++i) {
        const auto &p = tr_parts[i];
        fj_tr << "    {\n";
        fj_tr << "      \"id\": " << p.id << ",\n";
        fj_tr << "      \"place\": " << p.place << ",\n";
        fj_tr << "      \"frozen_order\": " << p.frozenOrder << ",\n";
        fj_tr << "      \"column_assignment\": " << p.columnAssignment << ",\n";
        fj_tr << "      \"pits_open\": " << static_cast<int>(p.pitsOpen) << ",\n";
        fj_tr << "      \"up_to_speed\": " << (p.upToSpeed ? "true" : "false") << ",\n";
        fj_tr << "      \"goal_relative_distance\": " << p.goalRelativeDistance << ",\n";
        fj_tr << "      \"message\": \"" << p.message << "\"\n";
        fj_tr << "    }" << (i + 1 < tr_parts.size() ? "," : "") << "\n";
    }
    fj_tr << "  ]\n";
    fj_tr << "}\n";
    fj_tr.close();

    // 5. Pit Menu
    PitMenuPacket pm;
    populate_golden_pit_menu(pm);
    std::ofstream fb_pm(bin_pit_path, std::ios::binary);
    fb_pm.write(reinterpret_cast<const char*>(&pm), sizeof(pm));
    fb_pm.close();

    std::ofstream fj_pm(json_pit_path);
    fj_pm << "{\n";
    fj_pm << "  \"struct_size\": " << sizeof(pm) << ",\n";
    fj_pm << "  \"category_index\": " << pm.categoryIndex << ",\n";
    fj_pm << "  \"category_name\": \"" << pm.categoryName << "\",\n";
    fj_pm << "  \"choice_index\": " << pm.choiceIndex << ",\n";
    fj_pm << "  \"choice_string\": \"" << pm.choiceString << "\",\n";
    fj_pm << "  \"num_choices\": " << pm.numChoices << "\n";
    fj_pm << "}\n";
    fj_pm.close();

    // 6. Weather
    WeatherPacket wp;
    populate_golden_weather(wp);
    std::ofstream fb_wp(bin_weather_path, std::ios::binary);
    fb_wp.write(reinterpret_cast<const char*>(&wp), sizeof(wp));
    fb_wp.close();

    std::ofstream fj_wp(json_weather_path);
    fj_wp << std::setprecision(6) << std::fixed;
    fj_wp << "{\n";
    fj_wp << "  \"struct_size\": " << sizeof(wp) << ",\n";
    fj_wp << "  \"et\": " << wp.et << ",\n";
    fj_wp << "  \"cloudiness\": " << wp.cloudiness << ",\n";
    fj_wp << "  \"ambient_temp_k\": " << wp.ambientTempK << ",\n";
    fj_wp << "  \"ambient_temp_c\": " << (wp.ambientTempK - 273.15) << ",\n";
    fj_wp << "  \"wind_max_speed\": " << wp.windMaxSpeed << ",\n";
    fj_wp << "  \"origin_raining\": " << wp.raining[1][1] << "\n";
    fj_wp << "}\n";
    fj_wp.close();

    // 7. Extended State (FR-05)
    ExtendedStatePacket ext;
    populate_golden_extended(ext);
    std::ofstream fb_ext(bin_ext_path, std::ios::binary);
    fb_ext.write(reinterpret_cast<const char*>(&ext), sizeof(ext));
    fb_ext.close();

    std::ofstream fj_ext(json_ext_path);
    fj_ext << std::setprecision(6) << std::fixed;
    fj_ext << "{\n";
    fj_ext << "  \"struct_size\": " << sizeof(ext) << ",\n";
    fj_ext << "  \"traction_control\": " << static_cast<int>(ext.tractionControl) << ",\n";
    fj_ext << "  \"anti_lock_brakes\": " << static_cast<int>(ext.antiLockBrakes) << ",\n";
    fj_ext << "  \"auto_clutch\": " << static_cast<int>(ext.autoClutch) << ",\n";
    fj_ext << "  \"auto_blip\": " << static_cast<int>(ext.autoBlip) << ",\n";
    fj_ext << "  \"tire_mult\": " << static_cast<int>(ext.tireMult) << ",\n";
    fj_ext << "  \"max_impact_magnitude\": " << ext.maxImpactMagnitude << ",\n";
    fj_ext << "  \"accumulated_impact_magnitude\": " << ext.accumulatedImpactMagnitude << ",\n";
    fj_ext << "  \"in_realtime_fc\": " << (ext.inRealtimeFC ? "true" : "false") << ",\n";
    fj_ext << "  \"session_started\": " << (ext.sessionStarted ? "true" : "false") << ",\n";
    fj_ext << "  \"session\": " << ext.session << ",\n";
    fj_ext << "  \"current_pit_speed_limit\": " << ext.currentPitSpeedLimit << "\n";
    fj_ext << "}\n";
    fj_ext.close();

    // 8. Force Feedback (FR-06)
    ForceFeedbackPacket ffb;
    populate_golden_ffb(ffb);
    std::ofstream fb_ffb(bin_ffb_path, std::ios::binary);
    fb_ffb.write(reinterpret_cast<const char*>(&ffb), sizeof(ffb));
    fb_ffb.close();

    std::ofstream fj_ffb(json_ffb_path);
    fj_ffb << std::setprecision(6) << std::fixed;
    fj_ffb << "{\n";
    fj_ffb << "  \"struct_size\": " << sizeof(ffb) << ",\n";
    fj_ffb << "  \"force_value\": " << ffb.forceValue << "\n";
    fj_ffb << "}\n";
    fj_ffb.close();

    // 9. Graphics (FR-06)
    GraphicsPacket gfx;
    populate_golden_graphics(gfx);
    std::ofstream fb_gfx(bin_gfx_path, std::ios::binary);
    fb_gfx.write(reinterpret_cast<const char*>(&gfx), sizeof(gfx));
    fb_gfx.close();

    std::ofstream fj_gfx(json_gfx_path);
    fj_gfx << std::setprecision(6) << std::fixed;
    fj_gfx << "{\n";
    fj_gfx << "  \"struct_size\": " << sizeof(gfx) << ",\n";
    fj_gfx << "  \"cam_pos\": [" << gfx.camPos.x << ", " << gfx.camPos.y << ", " << gfx.camPos.z << "],\n";
    fj_gfx << "  \"ambient_rgb\": [" << gfx.ambientRed << ", " << gfx.ambientGreen << ", " << gfx.ambientBlue << "],\n";
    fj_gfx << "  \"slot_id\": " << gfx.slotId << ",\n";
    fj_gfx << "  \"camera_type\": " << gfx.cameraType << "\n";
    fj_gfx << "}\n";
    fj_gfx.close();

    // 10. System Event
    SystemEventPacket ev;
    populate_golden_event(ev, 1);
    std::ofstream fb_e(bin_event_path, std::ios::binary);
    fb_e.write(reinterpret_cast<const char*>(&ev), sizeof(ev));
    fb_e.close();

    std::ofstream fj_e(json_event_path);
    fj_e << "{\n";
    fj_e << "  \"struct_size\": " << sizeof(ev) << ",\n";
    fj_e << "  \"event_id\": " << static_cast<int>(ev.eventType) << ",\n";
    fj_e << "  \"name\": \"EnterRealtime\"\n";
    fj_e << "}\n";
    fj_e.close();

    // 11. Hardware Control Inbound (FR-07, Type 100)
    HWControlCommandPacket hw;
    populate_golden_hw_control(hw);
    std::string bin_hw_path = bin_event_path.substr(0, bin_event_path.find_last_of('/')) + "/hw_control_golden.bin";
    std::string json_hw_path = json_event_path.substr(0, json_event_path.find_last_of('/')) + "/hw_control_golden.json";
    std::ofstream fb_hw(bin_hw_path, std::ios::binary);
    fb_hw.write(reinterpret_cast<const char*>(&hw), sizeof(hw));
    fb_hw.close();

    std::ofstream fj_hw(json_hw_path);
    fj_hw << std::setprecision(6) << std::fixed;
    fj_hw << "{\n";
    fj_hw << "  \"struct_size\": " << sizeof(hw) << ",\n";
    fj_hw << "  \"control_name\": \"" << hw.controlName << "\",\n";
    fj_hw << "  \"control_value\": " << hw.controlValue << ",\n";
    fj_hw << "  \"duration_ms\": " << hw.durationMs << "\n";
    fj_hw << "}\n";
    fj_hw.close();

    // 12. Weather Control Inbound (FR-07, Type 101)
    WeatherControlCommandPacket wc;
    populate_golden_weather_control(wc);
    std::string bin_wc_path = bin_event_path.substr(0, bin_event_path.find_last_of('/')) + "/weather_control_golden.bin";
    std::string json_wc_path = json_event_path.substr(0, json_event_path.find_last_of('/')) + "/weather_control_golden.json";
    std::ofstream fb_wc(bin_wc_path, std::ios::binary);
    fb_wc.write(reinterpret_cast<const char*>(&wc), sizeof(wc));
    fb_wc.close();

    std::ofstream fj_wc(json_wc_path);
    fj_wc << std::setprecision(6) << std::fixed;
    fj_wc << "{\n";
    fj_wc << "  \"struct_size\": " << sizeof(wc) << ",\n";
    fj_wc << "  \"ambient_temp\": " << wc.ambientTemp << ",\n";
    fj_wc << "  \"track_temp\": " << wc.trackTemp << ",\n";
    fj_wc << "  \"dark_cloud\": " << wc.darkCloud << ",\n";
    fj_wc << "  \"raining\": " << wc.raining << ",\n";
    fj_wc << "  \"wind_speed\": " << wc.windSpeed << ",\n";
    fj_wc << "  \"wind_direction\": " << wc.windDirection << ",\n";
    fj_wc << "  \"min_path_wetness\": " << wc.minPathWetness << ",\n";
    fj_wc << "  \"max_path_wetness\": " << wc.maxPathWetness << "\n";
    fj_wc << "}\n";
    fj_wc.close();
}

// ── Live UDP Server Mock ──────────────────────────────────────────────────────

void send_sliced_udp_mock(int sock, const sockaddr_in &dest, unsigned char packetType, unsigned short subId, const void* payload, size_t totalPayloadSize, double sessionET, unsigned int &seq) {
    const size_t MAX_CHUNK = 1200;
    const char* src = reinterpret_cast<const char*>(payload);
    size_t offset = 0;
    unsigned char totalChunks = static_cast<unsigned char>((totalPayloadSize + MAX_CHUNK - 1) / MAX_CHUNK);
    if (totalChunks == 0) totalChunks = 1;
    unsigned char chunkIdx = 0;
    seq++;

    char buffer[sizeof(RawUdpHeader) + MAX_CHUNK];

    while (offset < totalPayloadSize) {
        size_t chunkSize = (totalPayloadSize - offset > MAX_CHUNK) ? MAX_CHUNK : (totalPayloadSize - offset);

        RawUdpHeader* hdr = reinterpret_cast<RawUdpHeader*>(buffer);
        hdr->magic[0] = 'S'; hdr->magic[1] = 'I'; hdr->magic[2] = 'M'; hdr->magic[3] = 'P';
        hdr->protocolVersion = 1;
        hdr->packetType = packetType;
        hdr->payloadSize = static_cast<unsigned short>(chunkSize);
        hdr->sequenceNumber = seq;
        hdr->sessionET = sessionET;
        hdr->chunkIndex = chunkIdx++;
        hdr->totalChunks = totalChunks;
        hdr->subTypeOrId = subId;

        std::memcpy(buffer + sizeof(RawUdpHeader), src + offset, chunkSize);

        sendto(sock, buffer, sizeof(RawUdpHeader) + chunkSize, 0,
               reinterpret_cast<const sockaddr*>(&dest), sizeof(dest));

        offset += chunkSize;
    }
}

void run_live_udp_server(int port, int hz, int duration_sec) {
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        std::cerr << "Error creating UDP socket" << std::endl;
        return;
    }

    sockaddr_in dest{};
    dest.sin_family = AF_INET;
    dest.sin_port = htons(port);
    inet_pton(AF_INET, "127.0.0.1", &dest.sin_addr);

    // Inbound Socket for FR-07 Bi-Directional Input & Control
    int inbound_port = port + 1;
    int inbound_sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (inbound_sock >= 0) {
        int reuse = 1;
        setsockopt(inbound_sock, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
        fcntl(inbound_sock, F_SETFL, O_NONBLOCK);
        sockaddr_in in_addr{};
        in_addr.sin_family = AF_INET;
        in_addr.sin_port = htons(inbound_port);
        in_addr.sin_addr.s_addr = INADDR_ANY;
        bind(inbound_sock, reinterpret_cast<sockaddr*>(&in_addr), sizeof(in_addr));
    }

    TelemInfoV01 telem;
    populate_golden_telemetry(telem);

    CompactScoringPacket scoring;
    populate_golden_scoring(scoring);

    FullScoringSessionPacket full_sess;
    std::vector<VehicleScoringInfoV01> full_vehs;
    populate_golden_full_scoring(full_sess, full_vehs);

    std::vector<char> full_scoring_buf(sizeof(full_sess) + full_vehs.size() * sizeof(VehicleScoringInfoV01));
    std::memcpy(full_scoring_buf.data(), &full_sess, sizeof(full_sess));
    std::memcpy(full_scoring_buf.data() + sizeof(full_sess), full_vehs.data(), full_vehs.size() * sizeof(VehicleScoringInfoV01));

    TrackRulesSessionPacket rules_sess;
    std::vector<TrackRulesParticipantPacket> rules_parts;
    populate_golden_track_rules(rules_sess, rules_parts);

    std::vector<char> rules_buf(sizeof(rules_sess) + rules_parts.size() * sizeof(TrackRulesParticipantPacket));
    std::memcpy(rules_buf.data(), &rules_sess, sizeof(rules_sess));
    std::memcpy(rules_buf.data() + sizeof(rules_sess), rules_parts.data(), rules_parts.size() * sizeof(TrackRulesParticipantPacket));

    PitMenuPacket pit_menu;
    populate_golden_pit_menu(pit_menu);

    WeatherPacket weather;
    populate_golden_weather(weather);

    ExtendedStatePacket ext_state;
    populate_golden_extended(ext_state);

    ForceFeedbackPacket ffb;
    populate_golden_ffb(ffb);

    GraphicsPacket gfx;
    populate_golden_graphics(gfx);

    SystemEventPacket ev;
    populate_golden_event(ev, 1);

    unsigned int full_scoring_seq = 0;
    unsigned int rules_seq = 0;
    unsigned int pit_seq = 0;
    unsigned int weather_seq = 0;
    unsigned int ext_seq = 0;
    unsigned int ffb_seq = 0;
    unsigned int gfx_seq = 0;

    // Send initial system event
    sendto(sock, reinterpret_cast<const char*>(&ev), sizeof(ev), 0,
           reinterpret_cast<sockaddr*>(&dest), sizeof(dest));

    int total_frames = hz * duration_sec;
    int scoring_divider = std::max(1, hz / 5);    // 5Hz scoring
    int rules_divider = std::max(1, hz / 3);      // 3Hz track rules
    int weather_divider = std::max(1, hz / 1);    // 1Hz weather
    int ext_divider = std::max(1, hz / 5);        // 5Hz extended state
    int gfx_divider = std::max(1, hz / 60);       // 60Hz graphics
    auto frame_delay = std::chrono::microseconds(1000000 / hz);

    std::cout << "[C++ Mock Host] Streaming UDP packets to 127.0.0.1:" << port
              << " (Inbound listening on :" << inbound_port << ") @ "
              << hz << "Hz for " << duration_sec << "s..." << std::endl;

    for (int frame = 0; frame < total_frames; ++frame) {
        double sim_time = frame * (1.0 / hz);
        telem.mElapsedTime = 125.0 + sim_time;
        telem.mEngineRPM = 7500.0 + std::sin(sim_time * 5.0) * 1200.0;
        telem.mSpeedLimiter = (frame % 200 < 50) ? 1 : 0;

        // Poll inbound commands (FR-07)
        if (inbound_sock >= 0) {
            char in_buf[512];
            sockaddr_in from_addr{};
            socklen_t from_len = sizeof(from_addr);
            while (true) {
                int bytes = recvfrom(inbound_sock, in_buf, sizeof(in_buf), 0,
                                     reinterpret_cast<sockaddr*>(&from_addr), &from_len);
                if (bytes < static_cast<int>(sizeof(RawUdpHeader))) break;

                const RawUdpHeader* in_hdr = reinterpret_cast<const RawUdpHeader*>(in_buf);
                if (std::memcmp(in_hdr->magic, "SIMP", 4) != 0) continue;

                const char* in_payload = in_buf + sizeof(RawUdpHeader);
                size_t in_size = static_cast<size_t>(bytes - sizeof(RawUdpHeader));

                if (in_hdr->packetType == 100 && in_size >= sizeof(HWControlCommandPacket)) {
                    const HWControlCommandPacket* cmd = reinterpret_cast<const HWControlCommandPacket*>(in_payload);
                    std::cout << "[C++ Mock Host] Received HW Control Command: " << cmd->controlName
                              << " (val=" << cmd->controlValue << ", dur=" << cmd->durationMs << "ms)" << std::endl;
                    if (std::strcmp(cmd->controlName, "PitMenuDown") == 0) {
                        pit_menu.choiceIndex = (pit_menu.choiceIndex + 1) % pit_menu.numChoices;
                    }
                } else if (in_hdr->packetType == 101 && in_size >= sizeof(WeatherControlCommandPacket)) {
                    const WeatherControlCommandPacket* cmd = reinterpret_cast<const WeatherControlCommandPacket*>(in_payload);
                    std::cout << "[C++ Mock Host] Received Weather Control Command: Temp=" << cmd->ambientTemp
                              << "C, Rain=" << cmd->raining << std::endl;
                    weather.ambientTempK = cmd->ambientTemp + 273.15;
                    weather.raining[1][1] = cmd->raining;
                    weather.cloudiness = cmd->darkCloud;
                    weather.windMaxSpeed = cmd->windSpeed;
                    send_sliced_udp_mock(sock, dest, 7, 0, &weather, sizeof(weather), telem.mElapsedTime, weather_seq);
                }
            }
        }

        // 1. Send telemetry (1888 bytes)
        sendto(sock, reinterpret_cast<const char*>(&telem), sizeof(telem), 0,
               reinterpret_cast<sockaddr*>(&dest), sizeof(dest));

        // 2. Send PitMenu (Type 6 @ 100Hz)
        send_sliced_udp_mock(sock, dest, 6, 0, &pit_menu, sizeof(pit_menu), 0.0, pit_seq);

        // 3. Send Force Feedback (Type 9 @ high frequency up to 400Hz)
        ffb.forceValue = 0.65 + 0.3 * std::sin(sim_time * 25.0);
        send_sliced_udp_mock(sock, dest, 9, 0, &ffb, sizeof(ffb), 0.0, ffb_seq);

        // 4. Send Graphics (Type 10 @ 60Hz)
        if (frame % gfx_divider == 0) {
            send_sliced_udp_mock(sock, dest, 10, static_cast<unsigned short>(gfx.slotId), &gfx, sizeof(gfx), 0.0, gfx_seq);
        }

        // 5. Send Scoring (Compact + Full Sliced @ 5Hz)
        if (frame % scoring_divider == 0) {
            scoring.currentET = 1250.0 + sim_time;
            sendto(sock, reinterpret_cast<const char*>(&scoring), sizeof(scoring), 0,
                   reinterpret_cast<sockaddr*>(&dest), sizeof(dest));

            full_sess.currentET = 1250.0 + sim_time;
            std::memcpy(full_scoring_buf.data(), &full_sess, sizeof(full_sess));
            send_sliced_udp_mock(sock, dest, 4, static_cast<unsigned short>(full_vehs.size()),
                                full_scoring_buf.data(), full_scoring_buf.size(), full_sess.currentET, full_scoring_seq);
        }

        // 6. Send TrackRules (Type 5 Sliced @ 3Hz)
        if (frame % rules_divider == 0) {
            rules_sess.currentET = 1250.0 + sim_time;
            std::memcpy(rules_buf.data(), &rules_sess, sizeof(rules_sess));
            send_sliced_udp_mock(sock, dest, 5, static_cast<unsigned short>(rules_parts.size()),
                                rules_buf.data(), rules_buf.size(), rules_sess.currentET, rules_seq);
        }

        // 7. Send Extended State (Type 8 @ 5Hz)
        if (frame % ext_divider == 0) {
            ext_state.accumulatedImpactMagnitude = 3250.75 + sim_time * 10.0;
            send_sliced_udp_mock(sock, dest, 8, 0, &ext_state, sizeof(ext_state), telem.mElapsedTime, ext_seq);
        }

        // 8. Send Weather (Type 7 @ 1Hz)
        if (frame % weather_divider == 0) {
            weather.et = 1250.0 + sim_time;
            send_sliced_udp_mock(sock, dest, 7, 0, &weather, sizeof(weather), weather.et, weather_seq);
        }

        std::this_thread::sleep_for(frame_delay);
    }

    if (inbound_sock >= 0) close(inbound_sock);
    close(sock);
    std::cout << "[C++ Mock Host] Stream completed (" << total_frames << " frames sent)." << std::endl;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cout << "Usage:" << std::endl;
        std::cout << "  " << argv[0] << " --dump-truth <output_dir>" << std::endl;
        std::cout << "  " << argv[0] << " --serve <port> <hz> <duration_sec>" << std::endl;
        std::cout << "  " << argv[0] << " --sizes" << std::endl;
        return 1;
    }

    std::string mode = argv[1];

    if (mode == "--sizes") {
        std::cout << "RawUdpHeader: " << sizeof(RawUdpHeader) << " bytes" << std::endl;
        std::cout << "TelemInfoV01: " << sizeof(TelemInfoV01) << " bytes" << std::endl;
        std::cout << "TelemWheelV01: " << sizeof(TelemWheelV01) << " bytes" << std::endl;
        std::cout << "CompactScoringPacket: " << sizeof(CompactScoringPacket) << " bytes" << std::endl;
        std::cout << "FullScoringSessionPacket: " << sizeof(FullScoringSessionPacket) << " bytes" << std::endl;
        std::cout << "VehicleScoringInfoV01: " << sizeof(VehicleScoringInfoV01) << " bytes" << std::endl;
        std::cout << "TrackRulesSessionPacket: " << sizeof(TrackRulesSessionPacket) << " bytes" << std::endl;
        std::cout << "TrackRulesParticipantPacket: " << sizeof(TrackRulesParticipantPacket) << " bytes" << std::endl;
        std::cout << "PitMenuPacket: " << sizeof(PitMenuPacket) << " bytes" << std::endl;
        std::cout << "WeatherPacket: " << sizeof(WeatherPacket) << " bytes" << std::endl;
        std::cout << "ExtendedStatePacket: " << sizeof(ExtendedStatePacket) << " bytes" << std::endl;
        std::cout << "ForceFeedbackPacket: " << sizeof(ForceFeedbackPacket) << " bytes" << std::endl;
        std::cout << "GraphicsPacket: " << sizeof(GraphicsPacket) << " bytes" << std::endl;
        std::cout << "SystemEventPacket: " << sizeof(SystemEventPacket) << " bytes" << std::endl;
        std::cout << "HWControlCommandPacket: " << sizeof(HWControlCommandPacket) << " bytes" << std::endl;
        std::cout << "WeatherControlCommandPacket: " << sizeof(WeatherControlCommandPacket) << " bytes" << std::endl;
        return 0;
    }

    if (mode == "--dump-truth" && argc >= 3) {
        std::string dir = argv[2];
        dump_truth(
            dir + "/telemetry_golden.bin", dir + "/telemetry_golden.json",
            dir + "/scoring_golden.bin", dir + "/scoring_golden.json",
            dir + "/full_scoring_golden.bin", dir + "/full_scoring_golden.json",
            dir + "/track_rules_golden.bin", dir + "/track_rules_golden.json",
            dir + "/pit_menu_golden.bin", dir + "/pit_menu_golden.json",
            dir + "/weather_golden.bin", dir + "/weather_golden.json",
            dir + "/extended_golden.bin", dir + "/extended_golden.json",
            dir + "/ffb_golden.bin", dir + "/ffb_golden.json",
            dir + "/graphics_golden.bin", dir + "/graphics_golden.json",
            dir + "/event_golden.bin", dir + "/event_golden.json"
        );
        std::cout << "[C++ Mock Host] Golden datasets successfully dumped to " << dir << std::endl;
        return 0;
    }

    if (mode == "--serve") {
        int port = (argc >= 3) ? std::stoi(argv[2]) : 5000;
        int hz = (argc >= 4) ? std::stoi(argv[3]) : 100;
        int duration = (argc >= 5) ? std::stoi(argv[4]) : 2;
        run_live_udp_server(port, hz, duration);
        return 0;
    }

    return 0;
}
