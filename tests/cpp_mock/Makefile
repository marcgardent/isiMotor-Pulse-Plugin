CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Icompat -Izmq-headers -I../../isimotor-rawudp-plugin/include

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

all: $(TARGET)

$(ZMQ_H):
	@mkdir -p zmq-headers
	curl -fsSL -o $(ZMQ_H) https://raw.githubusercontent.com/zeromq/libzmq/$(LIBZMQ_TAG)/include/zmq.h

$(CPPZMQ_H):
	@mkdir -p zmq-headers
	curl -fsSL -o $(CPPZMQ_H) https://raw.githubusercontent.com/zeromq/cppzmq/$(CPPZMQ_TAG)/zmq.hpp

$(TARGET): $(SRCS) $(ZMQ_H) $(CPPZMQ_H)
	$(CXX) $(CXXFLAGS) $(SRCS) -o $(TARGET) $(ZMQ_LIBS)

clean:
	rm -f $(TARGET)

.PHONY: all clean
