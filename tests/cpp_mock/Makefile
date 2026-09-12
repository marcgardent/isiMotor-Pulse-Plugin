CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Icompat -Izmq-headers -Ifbs-headers -I../../isimotor-rawudp-plugin/include -I../../isimotor-rawudp-plugin/include/generated

TARGET = isi_mock_host
SRCS = isi_mock_host.cpp

# ZeroMQ: link against the system's libzmq runtime (libzmq.so.5, widely
# preinstalled or available via `apt install libzmq5`), using vendored
# headers pinned to the same libzmq/cppzmq versions as the plugin's own
# CMake FetchContent, so no -dev package is required to build the mock.
ZMQ_H = zmq-headers/zmq.h
CPPZMQ_H = zmq-headers/zmq.hpp
LIBZMQ_TAG = v4.3.5
CPPZMQ_TAG = v4.10.0
ZMQ_LIBS ?= $(shell pkg-config --libs libzmq 2>/dev/null || echo -l:libzmq.so.5)

# FlatBuffers: header-only C++ runtime, vendored the same way (pinned to the
# same tag as the plugin's CMake FetchContent). Only the runtime headers are
# needed - message schemas are pre-generated into isimotor-rawudp-plugin's
# include/generated/ (see schemas/*.fbs and `make generate-schemas`).
FBS_TAG = v23.5.26
FBS_STAMP = fbs-headers/.stamp-$(FBS_TAG)

all: $(TARGET)

$(ZMQ_H):
	@mkdir -p zmq-headers
	curl -fsSL -o $(ZMQ_H) https://raw.githubusercontent.com/zeromq/libzmq/$(LIBZMQ_TAG)/include/zmq.h

$(CPPZMQ_H):
	@mkdir -p zmq-headers
	curl -fsSL -o $(CPPZMQ_H) https://raw.githubusercontent.com/zeromq/cppzmq/$(CPPZMQ_TAG)/zmq.hpp

$(FBS_STAMP):
	@rm -rf fbs-headers
	@mkdir -p fbs-headers
	curl -fsSL https://github.com/google/flatbuffers/archive/refs/tags/$(FBS_TAG).tar.gz \
		| tar -xz -C fbs-headers --strip-components=2 "flatbuffers-23.5.26/include/flatbuffers"
	@touch $(FBS_STAMP)

$(TARGET): $(SRCS) $(ZMQ_H) $(CPPZMQ_H) $(FBS_STAMP)
	$(CXX) $(CXXFLAGS) $(SRCS) -o $(TARGET) $(ZMQ_LIBS)

clean:
	rm -f $(TARGET)

.PHONY: all clean
