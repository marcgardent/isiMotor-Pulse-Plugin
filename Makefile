.PHONY: help all build cross test benchmark install uninstall status info clean lint format format-check typecheck check version bump verify-version check-version french-drift drift generate-schemas briefcase-wheels

BUILD_DIR = build
BIN_DIR   = bin

# Autonomous Python & UV resolution
VENV_PYTHON = $(shell if [ -x isimotor-pulse-manager/.venv/bin/python ]; then echo "isimotor-pulse-manager/.venv/bin/python"; \
               elif [ -x .venv/bin/python ]; then echo ".venv/bin/python"; \
               elif command -v python >/dev/null 2>&1; then echo "python"; \
               else echo "python3"; fi)
PYTHON ?= $(VENV_PYTHON)
UV ?= $(shell which uv 2>/dev/null || if [ -x $$HOME/.local/bin/uv ]; then echo "$$HOME/.local/bin/uv"; else echo "uv"; fi)

help:
	@echo "=================================================================="
	@echo "  🏎️  isiMotor-Pulse-Plugin — Build & Tooling Menu"
	@echo "=================================================================="
	@echo "  make                - Display this help menu"
	@echo "  make lint           - Run Ruff fast static linter"
	@echo "  make format         - Auto-format codebase with Ruff"
	@echo "  make format-check   - Check codebase formatting with Ruff (no changes)"
	@echo "  make typecheck      - Run Mypy strict static type checker"
	@echo "  make check          - Run all static checks (lint + format-check + typecheck + test)"
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
	@echo "  make verify-version [VERSION=x.y.z] - Verify workspace version consistency"
	@echo "  make check-version  [VERSION=x.y.z] - Alias for 'make verify-version'"
	@echo "  make french-drift   - Scan codebase for French language drift keywords"
	@echo "  make drift          - Alias for 'make french-drift'"
	@echo "  make generate-schemas - Regenerate C++/Python code from schemas/*.fbs (requires flatc)"
	@echo "  make clean          - Remove build and bin directories"
	@echo "=================================================================="

all: help

lint:
	@echo "==> Running Ruff static linter..."
	@$(UV) run --with ruff ruff check .

format:
	@echo "==> Auto-formatting codebase with Ruff..."
	@$(UV) run --with ruff ruff format .

format-check:
	@echo "==> Checking codebase formatting with Ruff..."
	@$(UV) run --with ruff ruff format --check .

typecheck:
	@echo "==> Running Mypy static type checker..."
	@$(UV) run --with mypy --with textual --with rich mypy

check: lint format-check typecheck test
	@echo "==> All static analysis checks and test suites passed successfully!"

test:
	@echo "==> Building C++ mock host and running integration tests..."
	@make -C tests/cpp_mock --silent
	@./tests/cpp_mock/isi_mock_host --dump-truth tests/golden
	@if command -v $(UV) >/dev/null 2>&1; then \
		PYTHONPATH=isimotor-pulse-client:isimotor-pulse-manager:isimotor-pulse-types $(UV) run --with textual --with rich python -m unittest discover -s tests -p "test_*.py" -v; \
	else \
		PYTHONPATH=isimotor-pulse-client:isimotor-pulse-manager:isimotor-pulse-types $(PYTHON) -m unittest discover -s tests -p "test_*.py" -v; \
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
	@echo "==> Cross-compiling standard isiMotor_Pulse.dll with MinGW..."
	@mkdir -p $(BUILD_DIR)
	cmake -S isimotor-pulse-plugin -B $(BUILD_DIR) -DCMAKE_TOOLCHAIN_FILE=$(CURDIR)/isimotor-pulse-plugin/toolchain.cmake -DCMAKE_BUILD_TYPE=Release
	cmake --build $(BUILD_DIR) --config Release
	@echo "==> Build complete: $(BUILD_DIR)/isiMotor_Pulse.dll"

build: cross

manager:
	@echo "==> Launching isiMotor-Pulse-Manager on UDP port 5000..."
	@$(PYTHON) isimotor-pulse-manager/sniffer.py

benchmark: manager

sync-resources:
	@echo "==> Syncing compiled DLL and resources into Client package..."
	@mkdir -p isimotor-pulse-client/isimotor_pulse_client/resources
	@if [ -f $(BUILD_DIR)/isiMotor_Pulse.dll ]; then \
		cp $(BUILD_DIR)/isiMotor_Pulse.dll isimotor-pulse-client/isimotor_pulse_client/resources/; \
		echo "  ✓ Copied $(BUILD_DIR)/isiMotor_Pulse.dll to client resources"; \
	elif [ -f $(BIN_DIR)/isiMotor_Pulse.dll ]; then \
		cp $(BIN_DIR)/isiMotor_Pulse.dll isimotor-pulse-client/isimotor_pulse_client/resources/; \
		echo "  ✓ Copied $(BIN_DIR)/isiMotor_Pulse.dll to client resources"; \
	elif [ -f isiMotor_Pulse.dll ]; then \
		cp isiMotor_Pulse.dll isimotor-pulse-client/isimotor_pulse_client/resources/; \
		echo "  ✓ Copied isiMotor_Pulse.dll to client resources"; \
	fi

briefcase-wheels:
	@echo "==> Building local wheels for Briefcase (isimotor-pulse-client/types aren't on PyPI)..."
	@rm -rf isimotor-pulse-manager/.briefcase-wheels
	@$(UV) build --package isimotor-pulse-types --wheel -o isimotor-pulse-manager/.briefcase-wheels --clear
	@$(UV) build --package isimotor-pulse-client --wheel -o isimotor-pulse-manager/.briefcase-wheels

package: sync-resources briefcase-wheels
	@echo "==> Packaging isiMotor-Pulse-Manager with Briefcase..."
	@cd isimotor-pulse-manager && $(UV) run --with briefcase briefcase package --no-input

briefcase-dev: briefcase-wheels
	@echo "==> Running isiMotor-Pulse-Manager in Briefcase dev mode..."
	@cd isimotor-pulse-manager && $(UV) run --with briefcase briefcase dev

briefcase-build: sync-resources briefcase-wheels
	@echo "==> Building isiMotor-Pulse-Manager with Briefcase..."
	@cd isimotor-pulse-manager && $(UV) run --with briefcase briefcase build --no-input

standalone-linux: sync-resources
	@echo "==> Building standalone Linux manager binary with PyInstaller..."
	@PYTHONPATH=isimotor-pulse-client:isimotor-pulse-manager:isimotor-pulse-types $(UV) run --with pyinstaller --with textual --with rich pyinstaller --onefile --clean --name "isiMotor-Pulse-Manager-x86_64" --add-data "isimotor-pulse-client/isimotor_pulse_client/resources:isimotor_pulse_client/resources" --collect-all textual --collect-all rich --collect-all isimotor_pulse_manager --collect-all isimotor_pulse_client --collect-all isimotor_pulse_types scripts/entrypoint_manager.py

standalone-windows: sync-resources
	@echo "==> Building standalone Windows manager binary with PyInstaller..."
	@PYTHONPATH=isimotor-pulse-client:isimotor-pulse-manager:isimotor-pulse-types $(UV) run --with pyinstaller --with textual --with rich pyinstaller --onefile --clean --name "isiMotor_Pulse_Manager" --add-data "isimotor-pulse-client/isimotor_pulse_client/resources;isimotor_pulse_client/resources" --collect-all textual --collect-all rich --collect-all isimotor_pulse_manager --collect-all isimotor_pulse_client --collect-all isimotor_pulse_types scripts/entrypoint_manager.py

install:
	@PYTHONPATH=isimotor-pulse-client:isimotor-pulse-types $(PYTHON) -m isimotor_pulse_client.install.cli

uninstall:
	@PYTHONPATH=isimotor-pulse-client:isimotor-pulse-types $(PYTHON) -m isimotor_pulse_client.install.cli --uninstall

status:
	@PYTHONPATH=isimotor-pulse-client:isimotor-pulse-types $(PYTHON) -m isimotor_pulse_client.install.cli --status

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

verify-version:
	@$(PYTHON) scripts/verify_version.py $(VERSION)

check-version: verify-version

french-drift:
	@$(PYTHON) scripts/french_drift.py

drift: french-drift

# Regenerates the checked-in FlatBuffers bindings from schemas/*.fbs.
# Requires `flatc` (the FlatBuffers schema compiler, NOT a build-time
# dependency otherwise — see isimotor-pulse-plugin/CMakeLists.txt and
# tests/cpp_mock/Makefile, which only vendor the header-only runtime):
#   • Ubuntu / Debian : sudo apt install flatbuffers-compiler
#   • Or download a prebuilt binary from the flatbuffers GitHub releases page.
generate-schemas:
	@which flatc >/dev/null 2>&1 || ( \
		echo "" && \
		echo "❌ Error: flatc (FlatBuffers compiler) not found." && \
		echo "   Install it, e.g.: sudo apt install flatbuffers-compiler" && \
		echo "   or download a prebuilt binary from https://github.com/google/flatbuffers/releases" && \
		echo "" && \
		exit 1 \
	)
	@echo "==> Generating C++ bindings into isimotor-pulse-plugin/include/generated/..."
	@flatc --cpp --gen-object-api -o isimotor-pulse-plugin/include/generated schemas/*.fbs
	@echo "==> Generating Python bindings into isimotor-pulse-types/isimotor_pulse_types/fbs_generated/..."
	@rm -rf isimotor-pulse-types/isimotor_pulse_types/fbs_generated/isimotor
	@flatc --python -o isimotor-pulse-types/isimotor_pulse_types/fbs_generated schemas/*.fbs
	@touch isimotor-pulse-types/isimotor_pulse_types/fbs_generated/__init__.py
	@touch isimotor-pulse-types/isimotor_pulse_types/fbs_generated/isimotor/__init__.py
	@echo "==> Fixing cross-file imports (flatc emits 'from isimotor.fbs.X import X', which"
	@echo "    only resolves if isimotor_pulse_types/fbs_generated/ is put on sys.path;"
	@echo "    rewrite to the fully-qualified package path instead)..."
	@grep -rl "from isimotor\.fbs\." isimotor-pulse-types/isimotor_pulse_types/fbs_generated/ 2>/dev/null | \
		xargs -r sed -i 's/from isimotor\.fbs\./from isimotor_pulse_types.fbs_generated.isimotor.fbs./'
	@echo "==> Schema generation complete. Review the diff before committing."

clean:
	@echo "==> Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR) $(BIN_DIR)
	@echo "==> Clean complete."


# Removes Co-authored-by/Claude-Session trailers from commit messages —
# this history is not free advertising space for a tool.
strip-attribution:
	$(PYTHON) ./scripts/strip_commit_attribution.py
	git gc --prune=now