cmake_minimum_required(VERSION 3.20)
project(isiMotor_RawUDP VERSION 0.6.2 LANGUAGES CXX)

# libzmq's own CMakeLists still declares an old cmake_minimum_required();
# newer CMake refuses that outright unless a policy floor is set here.
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)

# --- C++ Standard ---
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- Default to Release build ---
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# --- ZeroMQ transport (libzmq + cppzmq) ---
# Vendored via FetchContent and linked statically, so the resulting DLL stays
# a standalone, zero-runtime-dependency artifact (same goal as before, now
# fulfilled with a pinned ZeroMQ version instead of raw Winsock/BSD sockets).
include(FetchContent)

set(ZMQ_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(WITH_LIBSODIUM OFF CACHE BOOL "" FORCE)
set(ENABLE_CURVE OFF CACHE BOOL "" FORCE)
set(WITH_PERF_TOOL OFF CACHE BOOL "" FORCE)
set(ENABLE_CPACK OFF CACHE BOOL "" FORCE)
set(ENABLE_DRAFTS OFF CACHE BOOL "" FORCE)

# Under MinGW cross-compilation, CMAKE_SYSTEM_VERSION is unset, so libzmq's
# own auto-detection resolves _WIN32_WINNT to an empty string, which breaks
# version-gated declarations in <wincrypt.h>/<bcrypt.h>/<ncrypt.h> (NTSTATUS
# / BCRYPT_KEY_HANDLE errors). Pin it explicitly (Windows Vista+ / Server 2008+).
set(ZMQ_WIN32_WINNT "0x0600" CACHE STRING "" FORCE)

# We only need TCP transport. libzmq's IPC (AF_UNIX) support detection for
# MinGW targets is broken (ipc_address.hpp unconditionally includes the
# POSIX <sys/socket.h> even when built for Windows) - force it off since it
# is unused here rather than working around that upstream bug.
set(ZMQ_HAVE_IPC 0 CACHE INTERNAL "" FORCE)

FetchContent_Declare(
    libzmq
    GIT_REPOSITORY https://github.com/zeromq/libzmq.git
    GIT_TAG        v4.3.5
    GIT_SHALLOW    TRUE
)
FetchContent_Declare(
    cppzmq
    GIT_REPOSITORY https://github.com/zeromq/cppzmq.git
    GIT_TAG        v4.10.0
    GIT_SHALLOW    TRUE
)

set(CPPZMQ_BUILD_TESTS OFF CACHE BOOL "" FORCE)

if(MINGW)
    # Without WIN32_LEAN_AND_MEAN, <windows.h> pulls in <wincrypt.h>, which
    # conflicts with <bcrypt.h>/<ncrypt.h> on some mingw-w64 header versions
    # (NTSTATUS/BCRYPT_KEY_HANDLE redefinition errors) when libzmq's own
    # windows.hpp includes <iphlpapi.h>/<mswsock.h>. Defining it globally
    # before building libzmq avoids pulling in the conflicting headers.
    add_definitions(-DWIN32_LEAN_AND_MEAN)
endif()

FetchContent_MakeAvailable(libzmq cppzmq)

# --- FlatBuffers (message payload serialization) ---
# Header-only C++ runtime; the flatc compiler is NOT needed at build time,
# since the *_generated.h headers in include/generated/ are already checked
# into the repo (regenerate them with `make generate-schemas` after editing
# a .fbs file under schemas/).
set(FLATBUFFERS_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(FLATBUFFERS_BUILD_FLATC OFF CACHE BOOL "" FORCE)
set(FLATBUFFERS_BUILD_FLATHASH OFF CACHE BOOL "" FORCE)
set(FLATBUFFERS_BUILD_FLATLIB ON CACHE BOOL "" FORCE)
set(FLATBUFFERS_INSTALL OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    flatbuffers
    GIT_REPOSITORY https://github.com/google/flatbuffers.git
    GIT_TAG        v23.5.26
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(flatbuffers)

# --- Source Files ---
set(SOURCES
    src/main.cpp
    include/InternalsPlugin.hpp
    include/PluginObjects.hpp
)

# --- Shared Library (DLL) ---
add_library(isiMotor_RawUDP SHARED ${SOURCES})

target_include_directories(isiMotor_RawUDP PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR}/include/generated)
target_link_libraries(isiMotor_RawUDP PRIVATE libzmq-static cppzmq flatbuffers)

if(WIN32)
    target_link_libraries(isiMotor_RawUDP PRIVATE ws2_32 iphlpapi rpcrt4)
endif()

# --- Static linking for zero-dependency standalone DLL ---
if(MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    foreach(flag_var CMAKE_CXX_FLAGS CMAKE_CXX_FLAGS_RELEASE CMAKE_CXX_FLAGS_DEBUG)
        string(REPLACE "/MD" "/MT" ${flag_var} "${${flag_var}}")
    endforeach()
elseif(MINGW)
    target_link_options(isiMotor_RawUDP PRIVATE -static -static-libgcc -static-libstdc++)
endif()

# Remove 'lib' prefix on Windows DLL (produces isiMotor_RawUDP.dll instead of libisiMotor_RawUDP.dll)
set_target_properties(isiMotor_RawUDP PROPERTIES PREFIX "")

# Output directory for built binaries (places directly in target build folder)
set_target_properties(isiMotor_RawUDP PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
    LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}"
    LIBRARY_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}"
)
