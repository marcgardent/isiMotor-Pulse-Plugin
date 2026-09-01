.PHONY: help all build cross test benchmark install uninstall status info clean lint format typecheck check version bump french-drift drift

BUILD_DIR = build
BIN_DIR   = bin

# Autonomous Python & UV resolution
VENV_PYTHON = $(shell if [ -x isimotor-rawudp-manager/.venv/bin/python ]; then echo "isimotor-rawudp-manager/.venv/bin/python"; \
               elif [ -x .venv/bin/python ]; then echo ".venv/bin/python"; \
               elif command -v python >/dev/null 2>&1; then echo "python"; \
               else echo "python3"; fi)
PYTHON ?= $(VENV_PYTHON)
UV ?= $(shell which uv 2>/dev/null || if [ -x $$HOME/.local/bin/uv ]; then echo "$$HOME/.local/bin/uv"; else echo "uv"; fi)

help:
	@echo "=================================================================="
	@echo "  🏎️  isiMotor-RawUDP-Plugin — Build & Tooling Menu"
	@echo "=================================================================="
	@echo "  make                - Display this help menu"
	@echo "  make lint           - Run Ruff fast static linter"
	@echo "  make format         - Auto-format codebase with Ruff"
	@echo "  make typecheck      - Run Mypy strict static type checker"
	@echo "  make check          - Run all static checks (lint + typecheck + test)"
	@echo "  make test           - Run full C++ mock & golden dataset integration tests"
	@echo "  make cross          - Compile standard universal DLL using MinGW-w64"
	@echo "  make build          - Alias for 'make cross' (standard universal build)"
	@echo "  make manager        - Run live Textual telemetry diagnostics & manager"
	@echo "  make benchmark      - Alias for 'make manager'"
	@echo "  make package        - Package Manager into standalone executable with Briefcase"
	@echo "  make briefcase-dev  - Run Manager in Briefcase isolated dev environment"
	@echo "  make briefcase-build- Build Manager standalone native bundle"
	@echo "  make install        - Install plugin DLL into Le Mans Ultimate / rFactor 2"
	@echo "  make uninstall      - Remove plugin DLL from detected game installations"
	@echo "  make status         - Display detected game installations & plugin status"
	@echo "  make info           - Display UDP packet structures & memory layout"
	@echo "  make version VERSION=x.y.z - Bump version across all packages & create Git tag"
	@echo "  make bump VERSION=x.y.z    - Alias for 'make version'"
	@echo "  make french-drift   - Scan codebase for French language drift keywords"
	@echo "  make drift          - Alias for 'make french-drift'"
	@echo "  make clean          - Remove build and bin directories"
	@echo "=================================================================="

all: help

lint:
	@echo "==> Running Ruff static linter..."
	@$(UV) run --with ruff ruff check .

format:
	@echo "==> Auto-formatting codebase with Ruff..."
	@$(UV) run --with ruff ruff format .

typecheck:
	@echo "==> Running Mypy static type checker..."
	@$(UV) run --with mypy --with textual --with rich mypy

check: lint typecheck test
	@echo "==> All static analysis checks and test suites passed successfully!"

test:
	@echo "==> Building C++ mock host and running integration tests..."
	@make -C tests/cpp_mock --silent
	@./tests/cpp_mock/isi_mock_host --dump-truth tests/golden
	@if command -v $(UV) >/dev/null 2>&1; then \
		PYTHONPATH=isimotor-rawudp-client:isimotor-rawudp-manager $(UV) run --with textual --with rich python -m unittest discover -s tests -p "test_*.py" -v; \
	else \
		PYTHONPATH=isimotor-rawudp-client:isimotor-rawudp-manager $(PYTHON) -m unittest discover -s tests -p "test_*.py" -v; \
	fi

cross:
	@which x86_64-w64-mingw32-g++ >/dev/null 2>&1 || ( \
		echo "" && \
		echo "❌ Error: MinGW-w64 compiler (x86_64-w64-mingw32-g++) not found." && \
		echo "   To compile the standard universal DLL on Linux, please install MinGW-w64:" && \
		echo "     • Ubuntu / Debian : sudo apt update && sudo apt install -y mingw-w64 g++-mingw-w64-x86-64" && \
		echo "     • Fedora          : sudo dnf install mingw64-gcc-c++" && \
		echo "     • Arch Linux      : sudo pacman -S mingw-w64-gcc" && \
		echo "" && \
		exit 1 \
	)
	@echo "==> Cross-compiling standard isiMotor_RawUDP.dll with MinGW..."
	@mkdir -p $(BUILD_DIR)
	cmake -S isimotor-rawudp-plugin -B $(BUILD_DIR) -DCMAKE_TOOLCHAIN_FILE=$(CURDIR)/isimotor-rawudp-plugin/toolchain.cmake -DCMAKE_BUILD_TYPE=Release
	cmake --build $(BUILD_DIR) --config Release
	@echo "==> Build complete: $(BUILD_DIR)/isiMotor_RawUDP.dll"

build: cross

manager:
	@echo "==> Launching isiMotor-RawUDP-Manager on UDP port 5000..."
	@$(PYTHON) isimotor-rawudp-manager/sniffer.py

benchmark: manager

sync-resources:
	@echo "==> Syncing compiled DLL and resources into Manager package..."
	@mkdir -p isimotor-rawudp-manager/isimotor_rawudp_manager/resources isimotor-rawudp-manager/resources
	@if [ -f $(BUILD_DIR)/isiMotor_RawUDP.dll ]; then \
		cp $(BUILD_DIR)/isiMotor_RawUDP.dll isimotor-rawudp-manager/isimotor_rawudp_manager/resources/; \
		cp $(BUILD_DIR)/isiMotor_RawUDP.dll isimotor-rawudp-manager/resources/; \
		echo "  ✓ Copied $(BUILD_DIR)/isiMotor_RawUDP.dll to manager resources"; \
	elif [ -f $(BIN_DIR)/isiMotor_RawUDP.dll ]; then \
		cp $(BIN_DIR)/isiMotor_RawUDP.dll isimotor-rawudp-manager/isimotor_rawudp_manager/resources/; \
		cp $(BIN_DIR)/isiMotor_RawUDP.dll isimotor-rawudp-manager/resources/; \
		echo "  ✓ Copied $(BIN_DIR)/isiMotor_RawUDP.dll to manager resources"; \
	elif [ -f isiMotor_RawUDP.dll ]; then \
		cp isiMotor_RawUDP.dll isimotor-rawudp-manager/isimotor_rawudp_manager/resources/; \
		cp isiMotor_RawUDP.dll isimotor-rawudp-manager/resources/; \
		echo "  ✓ Copied isiMotor_RawUDP.dll to manager resources"; \
	fi

package: sync-resources
	@echo "==> Packaging isiMotor-RawUDP-Manager with Briefcase..."
	@cd isimotor-rawudp-manager && $(UV) run --with briefcase briefcase package --no-input

briefcase-dev:
	@echo "==> Running isiMotor-RawUDP-Manager in Briefcase dev mode..."
	@cd isimotor-rawudp-manager && $(UV) run --with briefcase briefcase dev

briefcase-build: sync-resources
	@echo "==> Building isiMotor-RawUDP-Manager with Briefcase..."
	@cd isimotor-rawudp-manager && $(UV) run --with briefcase briefcase build --no-input

install:
	@PYTHONPATH=isimotor-rawudp-manager $(PYTHON) -m isimotor_rawudp_manager.installer

uninstall:
	@PYTHONPATH=isimotor-rawudp-manager $(PYTHON) -m isimotor_rawudp_manager.installer --uninstall

status:
	@PYTHONPATH=isimotor-rawudp-manager $(PYTHON) -m isimotor_rawudp_manager.installer --status

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

version:
	@if [ -z "$(VERSION)" ]; then \
		echo ""; \
		echo "❌ Error: Please specify the version number (e.g. make version VERSION=1.5.0)"; \
		echo ""; \
		exit 1; \
	fi
	@$(PYTHON) scripts/bump_version.py $(VERSION)

bump: version

french-drift:
	@$(PYTHON) scripts/french_drift.py

drift: french-drift

clean:
	@echo "==> Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR) $(BIN_DIR)
	@echo "==> Clean complete."
