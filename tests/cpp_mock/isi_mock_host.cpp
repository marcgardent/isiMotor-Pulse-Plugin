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

// Windows / isiMotor compatibility macros
#define __cdecl
#define __declspec(x)
typedef void* HWND;

// Force 32-bit long as in Windows x64 MSVC ABI
#define long int
#include "InternalsPlugin.hpp"
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

// SystemEvent (Type 3) is now a FlatBuffer (schemas/system_event.fbs) - see build_golden_event_fbs().

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

// ForceFeedback (Type 9) is now a FlatBuffer (schemas/force_feedback.fbs) - see build_golden_ffb_fbs().

struct GraphicsPacket {
    TelemVect3 camPos;                      // Camera 3D world position
    TelemVect3 camOri[3];                   // Camera 3x3 orientation matrix
    double     ambientRed;                  // Ambient light RGB
    double     ambientGreen;
    double     ambientBlue;
    int32_t    slotId;                      // Slot ID being viewed (-1 if none)
    int32_t    cameraType;                  // Camera viewpoint type
};

// HWControl/WeatherControl (Types 100/101) are now a single InboundCommand
// FlatBuffer with a CommandPayload union (schemas/inbound_command.fbs) - see
// build_golden_hw_control_fbs() / build_golden_weather_control_fbs().

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

// CompactScoring (Type 2) is a FlatBuffer now (schemas/compact_scoring.fbs).
// The legacy struct is kept purely as a convenient internal staging area
// (never sent raw); encode_scoring_fbs() converts it to the wire FlatBuffer.
void populate_golden_scoring(CompactScoringPacket &s) {
    std::memset(&s, 0, sizeof(s));
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

std::vector<uint8_t> encode_scoring_fbs(const CompactScoringPacket &s) {
    flatbuffers::FlatBufferBuilder builder;
    auto trackName = builder.CreateString(s.trackName);
    auto root = isimotor::fbs::CreateCompactScoring(
        builder, trackName, s.session, s.currentET, s.lapDist, s.maxLaps, s.inRealtime,
        s.totalLaps, s.sector, s.inGarageStall, s.countLapFlag, s.curSector1, s.curSector2,
        s.lastSector1, s.lastSector2, s.lastLapTime, s.bestSector1, s.bestSector2, s.bestLapTime);
    builder.Finish(root);
    return std::vector<uint8_t>(builder.GetBufferPointer(), builder.GetBufferPointer() + builder.GetSize());
}

std::vector<uint8_t> build_golden_scoring_fbs() {
    CompactScoringPacket s;
    populate_golden_scoring(s);
    return encode_scoring_fbs(s);
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

// TelemInfo (Type 1) is a FlatBuffer now (schemas/telemetry.fbs); mirrors
// isimotor-rawudp-plugin/src/main.cpp's EncodeWheelFbs()/UpdateTelemetry().
flatbuffers::Offset<isimotor::fbs::TelemWheel> encode_telem_wheel_fbs(
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

std::vector<uint8_t> encode_telemetry_fbs(const TelemInfoV01 &info) {
    flatbuffers::FlatBufferBuilder b;

    flatbuffers::Offset<isimotor::fbs::TelemWheel> wheelOffsets[4];
    for (int i = 0; i < 4; ++i) {
        wheelOffsets[i] = encode_telem_wheel_fbs(b, info.mWheel[i]);
    }
    auto wheelsVec = b.CreateVector(wheelOffsets, 4);

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

    float p2g[3] = {info.mPhysicsToGraphicsOffset[0], info.mPhysicsToGraphicsOffset[1], info.mPhysicsToGraphicsOffset[2]};
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
    return std::vector<uint8_t>(b.GetBufferPointer(), b.GetBufferPointer() + b.GetSize());
}

// FullScoringSession (Type 4) is a FlatBuffer now (schemas/full_scoring.fbs);
// mirrors main.cpp's EncodeVehicleScoringFbs()/UpdateScoring() full-scoring block.
flatbuffers::Offset<isimotor::fbs::VehicleScoring> encode_vehicle_scoring_fbs(
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

std::vector<uint8_t> encode_full_scoring_fbs(
        const FullScoringSessionPacket &info, const std::vector<VehicleScoringInfoV01> &vehicles) {
    flatbuffers::FlatBufferBuilder b;

    std::vector<flatbuffers::Offset<isimotor::fbs::VehicleScoring>> vehicleOffsets;
    vehicleOffsets.reserve(vehicles.size());
    for (const auto &v : vehicles) {
        vehicleOffsets.push_back(encode_vehicle_scoring_fbs(b, v));
    }
    auto vehiclesVec = b.CreateVector(vehicleOffsets);

    // The mock's FullScoringSessionPacket has no mLMUExtension field (unlike
    // the real ScoringInfoV01), so its LMU scoring session extension is
    // encoded with defaults.
    auto lmu = isimotor::fbs::CreateLmuScoringSession(b, 0, 0, 0, 0.0f);

    auto trackName = b.CreateString(info.trackName, strnlen(info.trackName, sizeof(info.trackName)));
    auto playerName = b.CreateString(info.playerName, strnlen(info.playerName, sizeof(info.playerName)));
    auto plrFileName = b.CreateString(info.plrFileName, strnlen(info.plrFileName, sizeof(info.plrFileName)));

    isimotor::fbs::Vec3 wind(info.wind.x, info.wind.y, info.wind.z);

    auto root = isimotor::fbs::CreateFullScoringSession(
        b, trackName, info.session, info.currentET, info.endET, info.maxLaps, info.lapDist,
        static_cast<int32_t>(vehicles.size()), info.gamePhase, info.yellowFlagState,
        info.sectorFlag[0], info.sectorFlag[1], info.sectorFlag[2], info.startLight,
        info.numRedLights, info.inRealtime, playerName, plrFileName, info.darkCloud, info.raining,
        info.ambientTemp, info.trackTemp, &wind, info.minPathWetness, info.maxPathWetness,
        info.avgPathWetness, lmu, vehiclesVec);
    b.Finish(root);
    return std::vector<uint8_t>(b.GetBufferPointer(), b.GetBufferPointer() + b.GetSize());
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

// WeatherControl (Type 7) is a FlatBuffer now (schemas/weather.fbs). The
// legacy struct is kept purely as a convenient internal staging area (the
// live loop mutates it in place on inbound weather overrides); never sent raw.
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

std::vector<uint8_t> encode_weather_fbs(const WeatherPacket &w) {
    flatbuffers::FlatBufferBuilder builder;
    double raining[9];
    for (int r = 0; r < 3; ++r) {
        for (int c = 0; c < 3; ++c) {
            raining[r * 3 + c] = w.raining[r][c];
        }
    }
    auto rainingOffset = builder.CreateVector<double>(raining, 9);
    auto root = isimotor::fbs::CreateWeatherControl(
        builder, w.et, rainingOffset, w.cloudiness, w.ambientTempK, w.windMaxSpeed, w.applyCloudinessInstantly);
    builder.Finish(root);
    return std::vector<uint8_t>(builder.GetBufferPointer(), builder.GetBufferPointer() + builder.GetSize());
}

std::vector<uint8_t> build_golden_weather_fbs() {
    WeatherPacket w;
    populate_golden_weather(w);
    return encode_weather_fbs(w);
}

// ExtendedState (Type 8) is a FlatBuffer now (schemas/extended_state.fbs).
// The legacy struct is kept purely as a convenient internal staging area.
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

std::vector<uint8_t> encode_extended_fbs(const ExtendedStatePacket &ext) {
    flatbuffers::FlatBufferBuilder builder;
    auto physics = isimotor::fbs::CreatePhysicsOptions(
        builder,
        ext.tractionControl, ext.antiLockBrakes, ext.stabilityControl, ext.autoShift,
        ext.autoClutch, ext.invulnerable, ext.oppositeLock, ext.steeringHelp,
        ext.brakingHelp, ext.spinRecovery, ext.autoPit, ext.autoLift,
        ext.autoBlip, ext.fuelMult, ext.tireMult, ext.mechFail,
        ext.allowPitcrewPush, ext.repeatShifts, ext.holdClutch, ext.autoReverse,
        ext.alternateNeutral, ext.aiControl, ext.manualShiftOverrideTime,
        ext.autoShiftOverrideTime, ext.speedSensitiveSteering, ext.steerRatioSpeed);
    auto root = isimotor::fbs::CreateExtendedState(
        builder, physics, ext.maxImpactMagnitude, ext.accumulatedImpactMagnitude,
        ext.inRealtimeFC, ext.sessionStarted, ext.session, ext.currentPitSpeedLimit);
    builder.Finish(root);
    return std::vector<uint8_t>(builder.GetBufferPointer(), builder.GetBufferPointer() + builder.GetSize());
}

std::vector<uint8_t> build_golden_extended_fbs() {
    ExtendedStatePacket ext;
    populate_golden_extended(ext);
    return encode_extended_fbs(ext);
}

// ForceFeedback (Type 9) is a FlatBuffer now; the "golden" value lives here
// as a plain double, encoded on demand by build_golden_ffb_fbs().
static const double kGoldenForceValue = 0.685;

std::vector<uint8_t> build_golden_ffb_fbs() {
    flatbuffers::FlatBufferBuilder builder;
    auto root = isimotor::fbs::CreateForceFeedback(builder, kGoldenForceValue);
    builder.Finish(root);
    return std::vector<uint8_t>(builder.GetBufferPointer(), builder.GetBufferPointer() + builder.GetSize());
}

// Graphics (Type 10) is a FlatBuffer now (schemas/graphics.fbs). The legacy
// struct is kept purely as a convenient internal staging area; never sent raw.
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

std::vector<uint8_t> encode_graphics_fbs(const GraphicsPacket &gfx) {
    flatbuffers::FlatBufferBuilder builder;
    isimotor::fbs::Vec3 camPos(gfx.camPos.x, gfx.camPos.y, gfx.camPos.z);
    isimotor::fbs::Vec3 camOri0(gfx.camOri[0].x, gfx.camOri[0].y, gfx.camOri[0].z);
    isimotor::fbs::Vec3 camOri1(gfx.camOri[1].x, gfx.camOri[1].y, gfx.camOri[1].z);
    isimotor::fbs::Vec3 camOri2(gfx.camOri[2].x, gfx.camOri[2].y, gfx.camOri[2].z);
    auto root = isimotor::fbs::CreateGraphics(
        builder, &camPos, &camOri0, &camOri1, &camOri2,
        gfx.ambientRed, gfx.ambientGreen, gfx.ambientBlue, gfx.slotId, gfx.cameraType);
    builder.Finish(root);
    return std::vector<uint8_t>(builder.GetBufferPointer(), builder.GetBufferPointer() + builder.GetSize());
}

std::vector<uint8_t> build_golden_graphics_fbs() {
    GraphicsPacket gfx;
    populate_golden_graphics(gfx);
    return encode_graphics_fbs(gfx);
}

// SystemEvent (Type 3) is a FlatBuffer now; encoded on demand.
std::vector<uint8_t> build_golden_event_fbs(uint8_t type = 1) {
    flatbuffers::FlatBufferBuilder builder;
    auto root = isimotor::fbs::CreateSystemEvent(builder, type);
    builder.Finish(root);
    return std::vector<uint8_t>(builder.GetBufferPointer(), builder.GetBufferPointer() + builder.GetSize());
}

// HWControl/WeatherControl (Types 100/101) are both wrapped in a single
// InboundCommand FlatBuffer union now; encoded on demand.
std::vector<uint8_t> build_golden_hw_control_fbs() {
    flatbuffers::FlatBufferBuilder builder;
    auto name = builder.CreateString("PitMenuNext");
    auto hw = isimotor::fbs::CreateHWControlCommand(builder, name, 1.0, 50);
    auto root = isimotor::fbs::CreateInboundCommand(builder, isimotor::fbs::CommandPayload_HWControlCommand, hw.Union());
    builder.Finish(root);
    return std::vector<uint8_t>(builder.GetBufferPointer(), builder.GetBufferPointer() + builder.GetSize());
}

std::vector<uint8_t> build_golden_weather_control_fbs() {
    flatbuffers::FlatBufferBuilder builder;
    auto wc = isimotor::fbs::CreateWeatherControlCommand(builder, 24.5, 29.8, 0.75, 0.45, 4.2, 1.5708, 0.2, 0.8);
    auto root = isimotor::fbs::CreateInboundCommand(builder, isimotor::fbs::CommandPayload_WeatherControlCommand, wc.Union());
    builder.Finish(root);
    return std::vector<uint8_t>(builder.GetBufferPointer(), builder.GetBufferPointer() + builder.GetSize());
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
    // 1. Telemetry - FlatBuffer (schemas/telemetry.fbs)
    TelemInfoV01 t;
    populate_golden_telemetry(t);
    std::vector<uint8_t> telem_buf = encode_telemetry_fbs(t);
    std::ofstream fb_t(bin_telem_path, std::ios::binary);
    fb_t.write(reinterpret_cast<const char*>(telem_buf.data()), static_cast<std::streamsize>(telem_buf.size()));
    fb_t.close();

    std::ofstream fj_t(json_telem_path);
    fj_t << std::setprecision(6) << std::fixed;
    fj_t << "{\n";
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

    // 2. Compact Scoring - FlatBuffer (schemas/compact_scoring.fbs)
    std::vector<uint8_t> scoring_buf = build_golden_scoring_fbs();
    std::ofstream fb_s(bin_scoring_path, std::ios::binary);
    fb_s.write(reinterpret_cast<const char*>(scoring_buf.data()), static_cast<std::streamsize>(scoring_buf.size()));
    fb_s.close();

    std::ofstream fj_s(json_scoring_path);
    fj_s << std::setprecision(6) << std::fixed;
    fj_s << "{\n";
    fj_s << "  \"track_name\": \"Circuit de la Sarthe - Le Mans\",\n";
    fj_s << "  \"session\": 10,\n";
    fj_s << "  \"current_et\": 1250.456,\n";
    fj_s << "  \"lap_dist\": 13626.0,\n";
    fj_s << "  \"max_laps\": 24,\n";
    fj_s << "  \"in_realtime\": true,\n";
    fj_s << "  \"total_laps\": 8,\n";
    fj_s << "  \"sector\": 2,\n";
    fj_s << "  \"last_lap_time\": 205.420,\n";
    fj_s << "  \"best_lap_time\": 204.850\n";
    fj_s << "}\n";
    fj_s.close();

    // 3. Full Scoring (Session + 3 Vehicles) - FlatBuffer (schemas/full_scoring.fbs)
    FullScoringSessionPacket fs_sess;
    std::vector<VehicleScoringInfoV01> fs_vehs;
    populate_golden_full_scoring(fs_sess, fs_vehs);

    std::vector<uint8_t> full_scoring_fbs_buf = encode_full_scoring_fbs(fs_sess, fs_vehs);
    std::ofstream fb_fs(bin_full_scoring_path, std::ios::binary);
    fb_fs.write(reinterpret_cast<const char*>(full_scoring_fbs_buf.data()),
                static_cast<std::streamsize>(full_scoring_fbs_buf.size()));
    fb_fs.close();

    std::ofstream fj_fs(json_full_scoring_path);
    fj_fs << std::setprecision(6) << std::fixed;
    fj_fs << "{\n";
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

    // 6. Weather - FlatBuffer (schemas/weather.fbs)
    std::vector<uint8_t> weather_buf = build_golden_weather_fbs();
    std::ofstream fb_wp(bin_weather_path, std::ios::binary);
    fb_wp.write(reinterpret_cast<const char*>(weather_buf.data()), static_cast<std::streamsize>(weather_buf.size()));
    fb_wp.close();

    std::ofstream fj_wp(json_weather_path);
    fj_wp << std::setprecision(6) << std::fixed;
    fj_wp << "{\n";
    fj_wp << "  \"et\": 1250.456,\n";
    fj_wp << "  \"cloudiness\": 0.25,\n";
    fj_wp << "  \"ambient_temp_k\": 297.65,\n";
    fj_wp << "  \"ambient_temp_c\": " << (297.65 - 273.15) << ",\n";
    fj_wp << "  \"wind_max_speed\": 4.5,\n";
    fj_wp << "  \"origin_raining\": 0.05\n";
    fj_wp << "}\n";
    fj_wp.close();

    // 7. Extended State (FR-05) - FlatBuffer (schemas/extended_state.fbs)
    std::vector<uint8_t> ext_buf = build_golden_extended_fbs();
    std::ofstream fb_ext(bin_ext_path, std::ios::binary);
    fb_ext.write(reinterpret_cast<const char*>(ext_buf.data()), static_cast<std::streamsize>(ext_buf.size()));
    fb_ext.close();

    std::ofstream fj_ext(json_ext_path);
    fj_ext << std::setprecision(6) << std::fixed;
    fj_ext << "{\n";
    fj_ext << "  \"traction_control\": 2,\n";
    fj_ext << "  \"anti_lock_brakes\": 1,\n";
    fj_ext << "  \"auto_clutch\": 1,\n";
    fj_ext << "  \"auto_blip\": 1,\n";
    fj_ext << "  \"tire_mult\": 2,\n";
    fj_ext << "  \"max_impact_magnitude\": 1845.50,\n";
    fj_ext << "  \"accumulated_impact_magnitude\": 3250.75,\n";
    fj_ext << "  \"in_realtime_fc\": true,\n";
    fj_ext << "  \"session_started\": true,\n";
    fj_ext << "  \"session\": 10,\n";
    fj_ext << "  \"current_pit_speed_limit\": 16.6667\n";
    fj_ext << "}\n";
    fj_ext.close();

    // 8. Force Feedback (FR-06) - FlatBuffer (schemas/force_feedback.fbs)
    std::vector<uint8_t> ffb_buf = build_golden_ffb_fbs();
    std::ofstream fb_ffb(bin_ffb_path, std::ios::binary);
    fb_ffb.write(reinterpret_cast<const char*>(ffb_buf.data()), static_cast<std::streamsize>(ffb_buf.size()));
    fb_ffb.close();

    std::ofstream fj_ffb(json_ffb_path);
    fj_ffb << std::setprecision(6) << std::fixed;
    fj_ffb << "{\n";
    fj_ffb << "  \"force_value\": " << kGoldenForceValue << "\n";
    fj_ffb << "}\n";
    fj_ffb.close();

    // 9. Graphics (FR-06) - FlatBuffer (schemas/graphics.fbs)
    std::vector<uint8_t> gfx_buf = build_golden_graphics_fbs();
    std::ofstream fb_gfx(bin_gfx_path, std::ios::binary);
    fb_gfx.write(reinterpret_cast<const char*>(gfx_buf.data()), static_cast<std::streamsize>(gfx_buf.size()));
    fb_gfx.close();

    std::ofstream fj_gfx(json_gfx_path);
    fj_gfx << std::setprecision(6) << std::fixed;
    fj_gfx << "{\n";
    fj_gfx << "  \"cam_pos\": [-1250.5, 46.8, 3420.2],\n";
    fj_gfx << "  \"ambient_rgb\": [0.85, 0.88, 0.92],\n";
    fj_gfx << "  \"slot_id\": 42,\n";
    fj_gfx << "  \"camera_type\": 1\n";
    fj_gfx << "}\n";
    fj_gfx.close();

    // 10. System Event - FlatBuffer (schemas/system_event.fbs)
    std::vector<uint8_t> ev_buf = build_golden_event_fbs(1);
    std::ofstream fb_e(bin_event_path, std::ios::binary);
    fb_e.write(reinterpret_cast<const char*>(ev_buf.data()), static_cast<std::streamsize>(ev_buf.size()));
    fb_e.close();

    std::ofstream fj_e(json_event_path);
    fj_e << "{\n";
    fj_e << "  \"event_id\": 1,\n";
    fj_e << "  \"name\": \"EnterRealtime\"\n";
    fj_e << "}\n";
    fj_e.close();

    // 11. Hardware Control Inbound (FR-07, Type 100) - FlatBuffer (schemas/inbound_command.fbs)
    std::vector<uint8_t> hw_buf = build_golden_hw_control_fbs();
    std::string bin_hw_path = bin_event_path.substr(0, bin_event_path.find_last_of('/')) + "/hw_control_golden.bin";
    std::string json_hw_path = json_event_path.substr(0, json_event_path.find_last_of('/')) + "/hw_control_golden.json";
    std::ofstream fb_hw(bin_hw_path, std::ios::binary);
    fb_hw.write(reinterpret_cast<const char*>(hw_buf.data()), static_cast<std::streamsize>(hw_buf.size()));
    fb_hw.close();

    std::ofstream fj_hw(json_hw_path);
    fj_hw << std::setprecision(6) << std::fixed;
    fj_hw << "{\n";
    fj_hw << "  \"control_name\": \"PitMenuNext\",\n";
    fj_hw << "  \"control_value\": 1.0,\n";
    fj_hw << "  \"duration_ms\": 50\n";
    fj_hw << "}\n";
    fj_hw.close();

    // 12. Weather Control Inbound (FR-07, Type 101) - FlatBuffer (schemas/inbound_command.fbs)
    std::vector<uint8_t> wc_buf = build_golden_weather_control_fbs();
    std::string bin_wc_path = bin_event_path.substr(0, bin_event_path.find_last_of('/')) + "/weather_control_golden.bin";
    std::string json_wc_path = json_event_path.substr(0, json_event_path.find_last_of('/')) + "/weather_control_golden.json";
    std::ofstream fb_wc(bin_wc_path, std::ios::binary);
    fb_wc.write(reinterpret_cast<const char*>(wc_buf.data()), static_cast<std::streamsize>(wc_buf.size()));
    fb_wc.close();

    std::ofstream fj_wc(json_wc_path);
    fj_wc << std::setprecision(6) << std::fixed;
    fj_wc << "{\n";
    fj_wc << "  \"ambient_temp\": 24.5,\n";
    fj_wc << "  \"track_temp\": 29.8,\n";
    fj_wc << "  \"dark_cloud\": 0.75,\n";
    fj_wc << "  \"raining\": 0.45,\n";
    fj_wc << "  \"wind_speed\": 4.2,\n";
    fj_wc << "  \"wind_direction\": 1.5708,\n";
    fj_wc << "  \"min_path_wetness\": 0.2,\n";
    fj_wc << "  \"max_path_wetness\": 0.8\n";
    fj_wc << "}\n";
    fj_wc.close();
}

// ── Live ZeroMQ PUB/SUB Server Mock ────────────────────────────────────────────

// Outbound packet types emitted by the mock (mirrors the plugin's own list,
// plus TrackRules(5)/PitMenu(6) which the mock also exercises for test
// coverage even though the real plugin does not currently send them). Each
// type is bound on its own port (basePort + packetType), same scheme as
// isimotor-rawudp-plugin/src/main.cpp's kOutboundPacketTypes.
static const unsigned char kMockOutboundPacketTypes[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
static const int kMockMaxPacketType = 10;

void send_sliced_udp_mock(zmq::socket_t &pub, unsigned char packetType, unsigned short subId, const void* payload, size_t totalPayloadSize, double sessionET, unsigned int &seq) {
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

        try {
            pub.send(zmq::buffer(buffer, sizeof(RawUdpHeader) + chunkSize), zmq::send_flags::dontwait);
        } catch (const zmq::error_t&) {
            // Best-effort, same semantics as the plugin's own PUB socket.
        }

        offset += chunkSize;
    }
}

// Sends a pre-encoded FlatBuffer message as-is: no header, no chunking (the
// message boundary already delimits it), matching the plugin's own SendFlatBuffer.
void send_fbs_mock(zmq::socket_t &pub, const std::vector<uint8_t> &buf) {
    try {
        pub.send(zmq::buffer(buf.data(), buf.size()), zmq::send_flags::dontwait);
    } catch (const zmq::error_t&) {
        // Best-effort, same semantics as the plugin's own PUB socket.
    }
}

void run_live_udp_server(int base_port, int hz, int duration_sec) {
    zmq::context_t ctx(1);

    // Outbound telemetry: one PUB socket per packet type, bound (mirrors the real
    // plugin's role); clients (SUB) connect to only the port(s) they need.
    zmq::socket_t pubSockets[kMockMaxPacketType + 1];
    bool pubBound[kMockMaxPacketType + 1] = {};
    for (unsigned char packetType : kMockOutboundPacketTypes) {
        pubSockets[packetType] = zmq::socket_t(ctx, zmq::socket_type::pub);
        pubSockets[packetType].set(zmq::sockopt::sndhwm, 1000);
        pubSockets[packetType].set(zmq::sockopt::linger, 0);
        char endpoint[64];
        std::snprintf(endpoint, sizeof(endpoint), "tcp://127.0.0.1:%d", base_port + packetType);
        try {
            pubSockets[packetType].bind(endpoint);
            pubBound[packetType] = true;
        } catch (const zmq::error_t& e) {
            std::cerr << "Error binding PUB socket for packet type " << static_cast<int>(packetType)
                       << " on " << endpoint << ": " << e.what() << std::endl;
            return;
        }
    }

    // Inbound commands (FR-07 Bi-Directional Input & Control): SUB socket, bound; clients (PUB) connect.
    int inbound_port = base_port + 101;
    zmq::socket_t inbound_sock(ctx, zmq::socket_type::sub);
    inbound_sock.set(zmq::sockopt::subscribe, "");
    inbound_sock.set(zmq::sockopt::linger, 0);
    bool inbound_bound = false;
    {
        char inbound_endpoint[64];
        std::snprintf(inbound_endpoint, sizeof(inbound_endpoint), "tcp://127.0.0.1:%d", inbound_port);
        try {
            inbound_sock.bind(inbound_endpoint);
            inbound_bound = true;
        } catch (const zmq::error_t& e) {
            std::cerr << "Error binding inbound SUB socket on " << inbound_endpoint << ": " << e.what() << std::endl;
        }
    }

    // ZMQ_PUB requires its subscriber(s) to complete connection + subscription
    // propagation before it will forward any message ("slow joiner"); give
    // the test client time to connect before streaming starts.
    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    TelemInfoV01 telem;
    populate_golden_telemetry(telem);

    CompactScoringPacket scoring;
    populate_golden_scoring(scoring);

    FullScoringSessionPacket full_sess;
    std::vector<VehicleScoringInfoV01> full_vehs;
    populate_golden_full_scoring(full_sess, full_vehs);

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

    GraphicsPacket gfx;
    populate_golden_graphics(gfx);

    flatbuffers::FlatBufferBuilder ffbBuilder;  // Reused (Clear()'d) for ForceFeedback, sent up to 400Hz.

    unsigned int rules_seq = 0;
    unsigned int pit_seq = 0;

    // Send initial system event (Type 3) - FlatBuffer, no header/chunking.
    {
        flatbuffers::FlatBufferBuilder builder;
        auto root = isimotor::fbs::CreateSystemEvent(builder, 1);
        builder.Finish(root);
        try {
            pubSockets[3].send(zmq::buffer(builder.GetBufferPointer(), builder.GetSize()), zmq::send_flags::dontwait);
        } catch (const zmq::error_t&) {
        }
    }

    int total_frames = hz * duration_sec;
    int scoring_divider = std::max(1, hz / 5);    // 5Hz scoring
    int rules_divider = std::max(1, hz / 3);      // 3Hz track rules
    int weather_divider = std::max(1, hz / 1);    // 1Hz weather
    int ext_divider = std::max(1, hz / 5);        // 5Hz extended state
    int gfx_divider = std::max(1, hz / 60);       // 60Hz graphics
    auto frame_delay = std::chrono::microseconds(1000000 / hz);

    std::cout << "[C++ Mock Host] Streaming ZeroMQ PUB packets on tcp://127.0.0.1:" << base_port
              << "+type (Inbound SUB on :" << inbound_port << ") @ "
              << hz << "Hz for " << duration_sec << "s..." << std::endl;

    for (int frame = 0; frame < total_frames; ++frame) {
        double sim_time = frame * (1.0 / hz);
        telem.mElapsedTime = 125.0 + sim_time;
        telem.mEngineRPM = 7500.0 + std::sin(sim_time * 5.0) * 1200.0;
        telem.mSpeedLimiter = (frame % 200 < 50) ? 1 : 0;

        // Poll inbound commands (FR-07)
        if (inbound_bound) {
            zmq::message_t in_msg;
            while (true) {
                zmq::recv_result_t result;
                try {
                    result = inbound_sock.recv(in_msg, zmq::recv_flags::dontwait);
                } catch (const zmq::error_t&) {
                    break;
                }
                if (!result.has_value()) break;

                // No header/framing: the message IS an isimotor::fbs::InboundCommand
                // FlatBuffer; its CommandPayload union tells HWControl from WeatherControl.
                flatbuffers::Verifier verifier(static_cast<const uint8_t*>(in_msg.data()), in_msg.size());
                if (!isimotor::fbs::VerifyInboundCommandBuffer(verifier)) continue;
                const isimotor::fbs::InboundCommand* in_cmd = isimotor::fbs::GetInboundCommand(in_msg.data());

                if (in_cmd->payload_type() == isimotor::fbs::CommandPayload_HWControlCommand) {
                    const isimotor::fbs::HWControlCommand* cmd = in_cmd->payload_as_HWControlCommand();
                    if (!cmd || !cmd->control_name()) continue;
                    std::cout << "[C++ Mock Host] Received HW Control Command: " << cmd->control_name()->c_str()
                              << " (val=" << cmd->control_value() << ", dur=" << cmd->duration_ms() << "ms)" << std::endl;
                    if (std::strcmp(cmd->control_name()->c_str(), "PitMenuDown") == 0) {
                        pit_menu.choiceIndex = (pit_menu.choiceIndex + 1) % pit_menu.numChoices;
                    }
                } else if (in_cmd->payload_type() == isimotor::fbs::CommandPayload_WeatherControlCommand) {
                    const isimotor::fbs::WeatherControlCommand* cmd = in_cmd->payload_as_WeatherControlCommand();
                    if (!cmd) continue;
                    std::cout << "[C++ Mock Host] Received Weather Control Command: Temp=" << cmd->ambient_temp()
                              << "C, Rain=" << cmd->raining() << std::endl;
                    weather.ambientTempK = cmd->ambient_temp() + 273.15;
                    weather.raining[1][1] = cmd->raining();
                    weather.cloudiness = cmd->dark_cloud();
                    weather.windMaxSpeed = cmd->wind_speed();
                    send_fbs_mock(pubSockets[7], encode_weather_fbs(weather));
                }
            }
        }

        // 1. Send telemetry (Type 1) - FlatBuffer, no header/chunking.
        send_fbs_mock(pubSockets[1], encode_telemetry_fbs(telem));

        // 2. Send PitMenu (Type 6 @ 100Hz)
        send_sliced_udp_mock(pubSockets[6], 6, 0, &pit_menu, sizeof(pit_menu), 0.0, pit_seq);

        // 3. Send Force Feedback (Type 9 @ high frequency up to 400Hz) - FlatBuffer, no header/chunking.
        {
            double forceValue = 0.65 + 0.3 * std::sin(sim_time * 25.0);
            ffbBuilder.Clear();
            auto root = isimotor::fbs::CreateForceFeedback(ffbBuilder, forceValue);
            ffbBuilder.Finish(root);
            try {
                pubSockets[9].send(zmq::buffer(ffbBuilder.GetBufferPointer(), ffbBuilder.GetSize()), zmq::send_flags::dontwait);
            } catch (const zmq::error_t&) {
            }
        }

        // 4. Send Graphics (Type 10 @ 60Hz)
        if (frame % gfx_divider == 0) {
            send_fbs_mock(pubSockets[10], encode_graphics_fbs(gfx));
        }

        // 5. Send Scoring (Compact Type 2 + Full Sliced Type 4 @ 5Hz)
        if (frame % scoring_divider == 0) {
            scoring.currentET = 1250.0 + sim_time;
            send_fbs_mock(pubSockets[2], encode_scoring_fbs(scoring));

            full_sess.currentET = 1250.0 + sim_time;
            send_fbs_mock(pubSockets[4], encode_full_scoring_fbs(full_sess, full_vehs));
        }

        // 6. Send TrackRules (Type 5 Sliced @ 3Hz)
        if (frame % rules_divider == 0) {
            rules_sess.currentET = 1250.0 + sim_time;
            std::memcpy(rules_buf.data(), &rules_sess, sizeof(rules_sess));
            send_sliced_udp_mock(pubSockets[5], 5, static_cast<unsigned short>(rules_parts.size()),
                                rules_buf.data(), rules_buf.size(), rules_sess.currentET, rules_seq);
        }

        // 7. Send Extended State (Type 8 @ 5Hz)
        if (frame % ext_divider == 0) {
            ext_state.accumulatedImpactMagnitude = 3250.75 + sim_time * 10.0;
            send_fbs_mock(pubSockets[8], encode_extended_fbs(ext_state));
        }

        // 8. Send Weather (Type 7 @ 1Hz)
        if (frame % weather_divider == 0) {
            weather.et = 1250.0 + sim_time;
            send_fbs_mock(pubSockets[7], encode_weather_fbs(weather));
        }

        std::this_thread::sleep_for(frame_delay);
    }

    if (inbound_bound) inbound_sock.close();
    for (unsigned char packetType : kMockOutboundPacketTypes) {
        if (pubBound[packetType]) pubSockets[packetType].close();
    }
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
        std::cout << "GraphicsPacket: " << sizeof(GraphicsPacket) << " bytes" << std::endl;
        std::cout << "ForceFeedback/SystemEvent/HWControl/WeatherControl: FlatBuffers (schemas/*.fbs), variable size" << std::endl;
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
