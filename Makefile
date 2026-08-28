.PHONY: help all build cross benchmark benchmark-mock info clean

BUILD_DIR = build
BIN_DIR   = bin

# Autonomous Python resolution (uses benchmark's dedicated .venv)
VENV_PYTHON = $(shell if [ -x benchmark/.venv/bin/python ]; then echo "benchmark/.venv/bin/python"; \
               elif [ -x .venv/bin/python ]; then echo ".venv/bin/python"; \
               else echo "python3"; fi)
PYTHON ?= $(VENV_PYTHON)

help:
	@echo "=================================================================="
	@echo "  🏎️  isiMotor-RawUDP-Plugin — Build & Tooling Menu"
	@echo "=================================================================="
	@echo "  make                - Display this help menu"
	@echo "  make cross          - Cross-compile DLL using MinGW-w64 (on Linux)"
	@echo "  make build          - Native compile DLL (on Windows MSVC / MinGW)"
	@echo "  make test           - Run full C++ mock & golden dataset integration tests"
	@echo "  make benchmark      - Run live Textual UDP packet sniffer & frequency benchmark"
	@echo "  make benchmark-mock - Run benchmark in simulation mode (with mock telemetry)"
	@echo "  make info           - Display UDP packet structures & memory layout"
	@echo "  make clean          - Remove build and bin directories"
	@echo "=================================================================="

all: help

test:
	@echo "==> Building C++ mock host and running integration tests..."
	@make -C tests/cpp_mock --silent
	@./tests/cpp_mock/isi_mock_host --dump-truth tests/golden
	@PYTHONPATH=isimotor-rawudp-client $(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

cross:
	@echo "==> Cross-compiling isiMotor_RawUDP.dll with MinGW..."
	@mkdir -p $(BUILD_DIR)
	cmake -B $(BUILD_DIR) -DCMAKE_TOOLCHAIN_FILE=toolchain.cmake -DCMAKE_BUILD_TYPE=Release
	cmake --build $(BUILD_DIR) --config Release
	@echo "==> Build complete: $(BUILD_DIR)/isiMotor_RawUDP.dll"

build:
	@echo "==> Compiling isiMotor_RawUDP.dll natively..."
	@mkdir -p $(BUILD_DIR)
	cmake -B $(BUILD_DIR) -DCMAKE_BUILD_TYPE=Release
	cmake --build $(BUILD_DIR) --config Release
	@echo "==> Build complete: $(BUILD_DIR)/isiMotor_RawUDP.dll"

benchmark:
	@echo "==> Launching Rich telemetry sniffer on UDP port 5000..."
	@$(PYTHON) benchmark/sniffer.py

benchmark-mock:
	@echo "==> Launching Rich telemetry sniffer with mock data generator..."
	@$(PYTHON) benchmark/sniffer.py --mock

info:
	@echo "=================================================================="
	@echo "  📡 UDP Binary Protocol Specifications (Port 5000)"
	@echo "=================================================================="
	@echo "  1. Telemetry Packet (TelemInfoV01):"
	@echo "     • Size: 1888 bytes"
	@echo "     • Rate: 60Hz - 100Hz (per physics tick)"
	@echo "     • Format: Direct struct dump (#pragma pack(4))"
	@echo ""
	@echo "  2. Compact Scoring Packet (SIMP Type 2):"
	@echo "     • Size: 168 bytes"
	@echo "     • Rate: 1Hz - 5Hz"
	@echo "     • Format: Magic 'SIMP' + Type 2 + Timing/Sector Data"
	@echo ""
	@echo "  3. System Event Packet (SIMP Type 3):"
	@echo "     • Size: 6 bytes"
	@echo "     • Format: Magic 'SIMP' + Type 3 + Event ID"
	@echo "=================================================================="

clean:
	@echo "==> Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR) $(BIN_DIR)
	@echo "==> Clean complete."
