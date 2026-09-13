"""
Unit tests for scripts/verify_version.py.
Validates workspace-wide version consistency checks and mismatch detection.

Copyright 2026 Marc GARDENT
Licensed under the Apache License, Version 2.0.
"""

import sys
import tempfile
import unittest
from pathlib import Path

# Add project root and scripts to sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
_scripts_dir = _project_root / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from verify_version import verify_versions


class TestVerifyVersion(unittest.TestCase):
    """Test suite for version consistency verification across all workspace files."""

    def _setup_mock_project(self, tmp_root: Path, version: str) -> None:
        """Helper to create a complete mock project structure with a given version."""
        # 1. Root pyproject.toml
        (tmp_root / "pyproject.toml").write_text(
            f'[project]\nname = "workspace"\nversion = "{version}"\n', encoding="utf-8"
        )

        # 2. Client
        client_dir = tmp_root / "isimotor-pulse-client" / "isimotor_pulse_client"
        client_dir.mkdir(parents=True, exist_ok=True)
        (tmp_root / "isimotor-pulse-client" / "pyproject.toml").write_text(
            f'[project]\nname = "client"\nversion = "{version}"\n', encoding="utf-8"
        )
        (client_dir / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")

        # 2b. Types
        types_dir = tmp_root / "binding" / "python" / "isimotor-pulse-types" / "isimotor_pulse_types"
        types_dir.mkdir(parents=True, exist_ok=True)
        (tmp_root / "binding" / "python" / "isimotor-pulse-types" / "pyproject.toml").write_text(
            f'[project]\nname = "types"\nversion = "{version}"\n', encoding="utf-8"
        )
        (types_dir / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")

        # 3. Manager
        manager_dir = tmp_root / "isimotor-pulse-manager" / "isimotor_pulse_manager"
        manager_dir.mkdir(parents=True, exist_ok=True)
        (tmp_root / "isimotor-pulse-manager" / "pyproject.toml").write_text(
            f'[project]\nname = "manager"\nversion = "{version}"\n\n[tool.briefcase]\nversion = "{version}"\n',
            encoding="utf-8",
        )
        (manager_dir / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")

        # 4. Plugin CMakeLists.txt
        plugin_dir = tmp_root / "isimotor-pulse-plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        cmake_ver = version.split("-")[0]
        (plugin_dir / "CMakeLists.txt").write_text(
            f"project(isiMotor_Pulse VERSION {cmake_ver} LANGUAGES CXX)\n", encoding="utf-8"
        )

        # 5. USER_NOTICE.md
        (tmp_root / "USER_NOTICE.md").write_text(f"# Notice\n> **Version**: {version}  \n", encoding="utf-8")

    def test_verify_synchronized_workspace(self) -> None:
        """Tests that a fully synchronized workspace passes verification."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            self._setup_mock_project(tmp_root, "1.5.0")

            is_valid, resolved, file_versions = verify_versions(tmp_root)
            self.assertTrue(is_valid)
            self.assertEqual(resolved, "1.5.0")
            self.assertEqual(len(file_versions), 10)
            for v in file_versions.values():
                self.assertIn(v, ["1.5.0", "1.5.0"])

    def test_verify_with_matching_target_tag(self) -> None:
        """Tests that verifying against a matching Git tag (e.g. v1.5.0) succeeds."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            self._setup_mock_project(tmp_root, "1.5.0")

            is_valid, resolved, _ = verify_versions(tmp_root, target_version="v1.5.0")
            self.assertTrue(is_valid)
            self.assertEqual(resolved, "1.5.0")

    def test_verify_with_mismatching_target_tag(self) -> None:
        """Tests that verifying against a different Git tag (e.g. v2.0.0 when files are 1.5.0) fails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            self._setup_mock_project(tmp_root, "1.5.0")

            is_valid, resolved, _ = verify_versions(tmp_root, target_version="v2.0.0")
            self.assertFalse(is_valid)
            self.assertEqual(resolved, "2.0.0")

    def test_verify_internal_desynchronization(self) -> None:
        """Tests that when one package has a different version, verification fails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            self._setup_mock_project(tmp_root, "1.5.0")

            # Desynchronize client pyproject.toml
            (tmp_root / "isimotor-pulse-client" / "pyproject.toml").write_text(
                '[project]\nname = "client"\nversion = "1.4.0"\n', encoding="utf-8"
            )

            is_valid, _, file_versions = verify_versions(tmp_root)
            self.assertFalse(is_valid)
            self.assertEqual(file_versions["isimotor-pulse-client/pyproject.toml"], "1.4.0")

    def test_verify_missing_file_detection(self) -> None:
        """Tests that missing required files are detected as invalid."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            # Empty directory
            is_valid, _, _ = verify_versions(tmp_root)
            self.assertFalse(is_valid)


if __name__ == "__main__":
    unittest.main()
