"""
Unit tests for scripts/bump_version.py.
Validates version regex matching, multi-file propagation, and git preconditions.

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

from bump_version import VERSION_REGEX, bump_all_files, check_git_preconditions, update_file


class TestBumpVersion(unittest.TestCase):
    """Test suite for semantic version bumping and git tagging automation."""

    def test_version_regex_validation(self) -> None:
        """Tests that semantic versioning regex matches valid versions and rejects invalid."""
        valid_versions = ["1.0.0", "1.4.0", "1.5.0", "2.0.0-rc1", "0.1.0-alpha.2", "10.20.30"]
        for v in valid_versions:
            self.assertIsNotNone(VERSION_REGEX.match(v), f"Expected '{v}' to be valid semantic version")

        invalid_versions = ["1", "1.0", "v1.0.0", "1.0.0.0", "rc1", "1.0-beta", "abc"]
        for inv in invalid_versions:
            self.assertIsNone(VERSION_REGEX.match(inv), f"Expected '{inv}' to be invalid semantic version")

    def test_bump_all_files_mock_workspace(self) -> None:
        """Tests that bump_all_files updates all relevant files across mock project structure."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)

            # 1. Root pyproject.toml
            root_pyproject = tmp_root / "pyproject.toml"
            root_pyproject.write_text('[project]\nname = "workspace"\nversion = "1.4.0"\n', encoding="utf-8")

            # 2. Client pyproject.toml and __init__.py
            client_dir = tmp_root / "isimotor-rawudp-client" / "isimotor_rawudp_client"
            client_dir.mkdir(parents=True)
            (tmp_root / "isimotor-rawudp-client" / "pyproject.toml").write_text(
                '[project]\nname = "client"\nversion = "1.4.0"\n', encoding="utf-8"
            )
            (client_dir / "__init__.py").write_text('__version__ = "1.4.0"\n', encoding="utf-8")

            # 3. Manager pyproject.toml and __init__.py
            manager_dir = tmp_root / "isimotor-rawudp-manager" / "isimotor_rawudp_manager"
            manager_dir.mkdir(parents=True)
            (tmp_root / "isimotor-rawudp-manager" / "pyproject.toml").write_text(
                '[project]\nname = "manager"\nversion = "1.4.0"\n\n[tool.briefcase]\nversion = "1.4.0"\n',
                encoding="utf-8",
            )
            (manager_dir / "__init__.py").write_text('__version__ = "1.4.0"\n', encoding="utf-8")

            # 4. Plugin CMakeLists.txt
            plugin_dir = tmp_root / "isimotor-rawudp-plugin"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "CMakeLists.txt").write_text(
                "project(isiMotor_RawUDP VERSION 1.4.0 LANGUAGES CXX)\n", encoding="utf-8"
            )

            # 5. USER_NOTICE.md
            user_notice = tmp_root / "USER_NOTICE.md"
            user_notice.write_text("# Notice\n> **Version**: 1.4.0  \n", encoding="utf-8")

            # Run bump
            updated = bump_all_files(tmp_root, "2.0.0")

            # Verify files were updated
            self.assertIn(root_pyproject, updated)
            self.assertIn(tmp_root / "isimotor-rawudp-client" / "pyproject.toml", updated)
            self.assertIn(client_dir / "__init__.py", updated)
            self.assertIn(tmp_root / "isimotor-rawudp-manager" / "pyproject.toml", updated)
            self.assertIn(manager_dir / "__init__.py", updated)
            self.assertIn(plugin_dir / "CMakeLists.txt", updated)
            self.assertIn(user_notice, updated)

            # Check contents
            self.assertIn('version = "2.0.0"', root_pyproject.read_text(encoding="utf-8"))
            self.assertIn(
                'version = "2.0.0"',
                (tmp_root / "isimotor-rawudp-client" / "pyproject.toml").read_text(encoding="utf-8"),
            )
            self.assertIn('__version__ = "2.0.0"', (client_dir / "__init__.py").read_text(encoding="utf-8"))
            self.assertIn('__version__ = "2.0.0"', (manager_dir / "__init__.py").read_text(encoding="utf-8"))
            self.assertIn(
                "project(isiMotor_RawUDP VERSION 2.0.0 LANGUAGES CXX)",
                (plugin_dir / "CMakeLists.txt").read_text(encoding="utf-8"),
            )
            self.assertIn("> **Version**: 2.0.0", user_notice.read_text(encoding="utf-8"))

    def test_update_file_helper(self) -> None:
        """Tests update_file regex helper behavior on existing and missing files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "test.txt"
            f.write_text("key = 123\n", encoding="utf-8")
            modified = update_file(f, r"key = \d+", "key = 456")
            self.assertTrue(modified)
            self.assertEqual(f.read_text(encoding="utf-8"), "key = 456\n")

            # Non-existent file
            missing = Path(tmp_dir) / "missing.txt"
            self.assertFalse(update_file(missing, r"foo", "bar"))

    def test_check_git_preconditions_not_a_git_repo(self) -> None:
        """Tests that check_git_preconditions exits when directory is not a git repo."""
        with tempfile.TemporaryDirectory() as tmp_dir, self.assertRaises(SystemExit):
            check_git_preconditions(Path(tmp_dir), "1.5.0")


if __name__ == "__main__":
    unittest.main()
