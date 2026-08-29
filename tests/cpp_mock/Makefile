CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Icompat -I../../isimotor-rawudp-plugin/include

TARGET = isi_mock_host
SRCS = isi_mock_host.cpp

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CXX) $(CXXFLAGS) $(SRCS) -o $(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all clean
