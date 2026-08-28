/**
 * isiMotor C++ Mock Host & Struct Layout Introspector
 * 
 * Provides:
 * 1. Exact memory layout & offset dumping for C++ structs (TelemInfoV01, CompactScoring, SystemEvent, FullScoring).
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
    uint8_t       packetType;        // 1=Telemetry, 2=CompactScoring, 3=SystemEvent, 4=FullScoring
    uint16_t      payloadSize;       // Size of chunk payload following header
    uint32_t      sequenceNumber;    // Monotonic stream sequence counter
    double        sessionET;         // Current session elapsed time in seconds
    uint8_t       chunkIndex;        // 0-based chunk index
    uint8_t       totalChunks;       // Total chunks count
    uint16_t      subTypeOrId;       // Active vehicle count or slot ID
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
    vehicles[0].mFinishStatus = 0; // Running
    vehicles[0].mLapDist = 8450.0;
    vehicles[0].mPathLateral = -0.25;
    vehicles[0].mTrackEdge = 7.5;
    vehicles[0].mBestSector1 = 40.820;
    vehicles[0].mBestSector2 = 123.500;
    vehicles[0].mBestLapTime = 204.850;
    vehicles[0].mLastSector1 = 40.950;
    vehicles[0].mLastSector2 = 123.850;
    vehicles[0].mLastLapTime = 205.420;
    vehicles[0].mCurSector1 = 41.250;
    vehicles[0].mCurSector2 = 124.500;
    vehicles[0].mNumPitstops = 1;
    vehicles[0].mNumPenalties = 0;
    vehicles[0].mIsPlayer = true;
    vehicles[0].mControl = 0; // Player
    vehicles[0].mInPits = false;
    vehicles[0].mPlace = 1;
    vehicles[0].mTimeBehindNext = 0.0;
    vehicles[0].mLapsBehindNext = 0;
    vehicles[0].mTimeBehindLeader = 0.0;
    vehicles[0].mLapsBehindLeader = 0;
    vehicles[0].mLapStartET = 1045.0;
    vehicles[0].mPos.Set(-1250.5, 45.25, 3420.75);
    vehicles[0].mLocalVel.Set(-1.5, 0.2, -78.5);
    vehicles[0].mLocalAccel.Set(-2.4, 9.81, 14.2);
    vehicles[0].mOri[0].Set(1.0, 0.0, 0.0);
    vehicles[0].mOri[1].Set(0.0, 1.0, 0.0);
    vehicles[0].mOri[2].Set(0.0, 0.0, 1.0);
    vehicles[0].mHeadlights = 1;
    vehicles[0].mPitState = 0;
    vehicles[0].mServerScored = 1;
    vehicles[0].mQualification = 1;
    vehicles[0].mTimeIntoLap = 205.456;
    vehicles[0].mEstimatedLapTime = 205.0;
    std::strncpy(vehicles[0].mPitGroup, "AF Corse", sizeof(vehicles[0].mPitGroup) - 1);
    vehicles[0].mCountLapFlag = 2;

    // Car 2 (Toyota GR010 #7 - P2)
    vehicles[1].mID = 7;
    std::strncpy(vehicles[1].mDriverName, "Kamui Kobayashi", sizeof(vehicles[1].mDriverName) - 1);
    std::strncpy(vehicles[1].mVehicleName, "Toyota GR010 #7", sizeof(vehicles[1].mVehicleName) - 1);
    std::strncpy(vehicles[1].mVehicleClass, "Hypercar", sizeof(vehicles[1].mVehicleClass) - 1);
    vehicles[1].mTotalLaps = 8;
    vehicles[1].mSector = 2;
    vehicles[1].mFinishStatus = 0;
    vehicles[1].mLapDist = 8320.0;
    vehicles[1].mBestSector1 = 40.910;
    vehicles[1].mBestSector2 = 123.650;
    vehicles[1].mBestLapTime = 205.110;
    vehicles[1].mLastLapTime = 205.650;
    vehicles[1].mNumPitstops = 1;
    vehicles[1].mIsPlayer = false;
    vehicles[1].mControl = 2; // Remote / AI
    vehicles[1].mPlace = 2;
    vehicles[1].mTimeBehindNext = 1.450;
    vehicles[1].mLapsBehindNext = 0;
    vehicles[1].mTimeBehindLeader = 1.450;
    vehicles[1].mLapsBehindLeader = 0;
    vehicles[1].mPos.Set(-1265.0, 45.10, 3310.5);
    vehicles[1].mLocalVel.Set(-1.2, 0.1, -78.1);
    vehicles[1].mPlace = 2;

    // Car 3 (Porsche 963 #6 - P3, in pits)
    vehicles[2].mID = 6;
    std::strncpy(vehicles[2].mDriverName, "Kevin Estre", sizeof(vehicles[2].mDriverName) - 1);
    std::strncpy(vehicles[2].mVehicleName, "Porsche 963 #6", sizeof(vehicles[2].mVehicleName) - 1);
    std::strncpy(vehicles[2].mVehicleClass, "Hypercar", sizeof(vehicles[2].mVehicleClass) - 1);
    vehicles[2].mTotalLaps = 7;
    vehicles[2].mSector = 0;
    vehicles[2].mFinishStatus = 0;
    vehicles[2].mLapDist = 120.0;
    vehicles[2].mBestLapTime = 205.350;
    vehicles[2].mLastLapTime = 206.100;
    vehicles[2].mNumPitstops = 2;
    vehicles[2].mIsPlayer = false;
    vehicles[2].mControl = 2;
    vehicles[2].mInPits = true;
    vehicles[2].mPitState = 3; // Stopped in box
    vehicles[2].mPlace = 3;
    vehicles[2].mTimeBehindNext = 3.200;
    vehicles[2].mLapsBehindNext = 1;
    vehicles[2].mTimeBehindLeader = 4.650;
    vehicles[2].mLapsBehindLeader = 1;
    vehicles[2].mPos.Set(45.0, 12.0, 150.0);
    vehicles[2].mLocalVel.Set(0.0, 0.0, 0.0);
}

void populate_golden_event(SystemEventPacket &ev, uint8_t type = 1) {
    std::memset(&ev, 0, sizeof(ev));
    ev.magic[0] = 'S'; ev.magic[1] = 'I'; ev.magic[2] = 'M'; ev.magic[3] = 'P';
    ev.packetType = 3;
    ev.eventType = type;
}

// ── JSON & Binary Dumper ──────────────────────────────────────────────────────

void dump_truth(const std::string &bin_telem_path, const std::string &json_telem_path,
                const std::string &bin_scoring_path, const std::string &json_scoring_path,
                const std::string &bin_full_scoring_path, const std::string &json_full_scoring_path,
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

    // 4. Event
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

    TelemInfoV01 telem;
    populate_golden_telemetry(telem);

    CompactScoringPacket scoring;
    populate_golden_scoring(scoring);

    FullScoringSessionPacket full_sess;
    std::vector<VehicleScoringInfoV01> full_vehs;
    populate_golden_full_scoring(full_sess, full_vehs);

    // Buffer for full scoring serialization
    std::vector<char> full_scoring_buf(sizeof(full_sess) + full_vehs.size() * sizeof(VehicleScoringInfoV01));
    std::memcpy(full_scoring_buf.data(), &full_sess, sizeof(full_sess));
    std::memcpy(full_scoring_buf.data() + sizeof(full_sess), full_vehs.data(), full_vehs.size() * sizeof(VehicleScoringInfoV01));

    SystemEventPacket ev;
    populate_golden_event(ev, 1);

    unsigned int full_scoring_seq = 0;

    // Send initial system event
    sendto(sock, reinterpret_cast<const char*>(&ev), sizeof(ev), 0,
           reinterpret_cast<sockaddr*>(&dest), sizeof(dest));

    int total_frames = hz * duration_sec;
    int scoring_divider = std::max(1, hz / 5); // 5Hz scoring
    auto frame_delay = std::chrono::microseconds(1000000 / hz);

    std::cout << "[C++ Mock Host] Streaming UDP packets to 127.0.0.1:" << port
              << " @ " << hz << "Hz for " << duration_sec << "s..." << std::endl;

    for (int frame = 0; frame < total_frames; ++frame) {
        double sim_time = frame * (1.0 / hz);
        telem.mElapsedTime = 125.0 + sim_time;
        telem.mEngineRPM = 7500.0 + std::sin(sim_time * 5.0) * 1200.0;
        telem.mSpeedLimiter = (frame % 200 < 50) ? 1 : 0;

        // Send telemetry (1888 bytes)
        sendto(sock, reinterpret_cast<const char*>(&telem), sizeof(telem), 0,
               reinterpret_cast<sockaddr*>(&dest), sizeof(dest));

        // Send scoring (Compact + Full Sliced @ 5Hz)
        if (frame % scoring_divider == 0) {
            scoring.currentET = 1250.0 + sim_time;
            sendto(sock, reinterpret_cast<const char*>(&scoring), sizeof(scoring), 0,
                   reinterpret_cast<sockaddr*>(&dest), sizeof(dest));

            full_sess.currentET = 1250.0 + sim_time;
            std::memcpy(full_scoring_buf.data(), &full_sess, sizeof(full_sess));
            send_sliced_udp_mock(sock, dest, 4, static_cast<unsigned short>(full_vehs.size()),
                                full_scoring_buf.data(), full_scoring_buf.size(), full_sess.currentET, full_scoring_seq);
        }

        std::this_thread::sleep_for(frame_delay);
    }

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
        std::cout << "SystemEventPacket: " << sizeof(SystemEventPacket) << " bytes" << std::endl;
        return 0;
    }

    if (mode == "--dump-truth" && argc >= 3) {
        std::string dir = argv[2];
        dump_truth(
            dir + "/telemetry_golden.bin", dir + "/telemetry_golden.json",
            dir + "/scoring_golden.bin", dir + "/scoring_golden.json",
            dir + "/full_scoring_golden.bin", dir + "/full_scoring_golden.json",
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
