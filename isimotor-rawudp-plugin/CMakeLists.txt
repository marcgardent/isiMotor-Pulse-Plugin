cmake_minimum_required(VERSION 3.20)
project(isiMotor_RawUDP VERSION 0.1.3 LANGUAGES CXX)

# --- C++ Standard ---
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- Default to Release build ---
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# --- Source Files ---
set(SOURCES
    src/main.cpp
    include/InternalsPlugin.hpp
    include/PluginObjects.hpp
)

# --- Shared Library (DLL) ---
add_library(isiMotor_RawUDP SHARED ${SOURCES})

target_include_directories(isiMotor_RawUDP PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(isiMotor_RawUDP PRIVATE ws2_32)

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
