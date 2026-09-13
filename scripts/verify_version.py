#!/usr/bin/env python3
"""
isiMotor-Pulse-Plugin — Workspace Version Consistency Validator.
Verifies that all subpackages, CMake configurations, Python packages,
and documentation reflect a single, consistent semantic version number.

Can be run standalone to check internal consistency, or against a target version
(e.g., in CI release pipelines when a Git tag is pushed).

Copyright 2026 Marc GARDENT
Licensed under the Apache License, Version 2.0.
"""

import argparse
import re
import sys
from pathlib import Path

VERSION_REGEX = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")


def get_project_root() -> Path:
    """Returns absolute path to repository root."""
    return Path(__file__).resolve().parent.parent


def extract_regex_first_group(path: Path, pattern: str) -> str | None:
    """Extracts first capturing group of regex pattern from file."""
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    match = re.search(pattern, content)
    return match.group(1).strip() if match else None


def collect_file_versions(root: Path) -> dict[str, str | None]:
    """Collects version strings defined across all project files."""
    versions: dict[str, str | None] = {}

    # 1. Root pyproject.toml
    root_pyproject = root / "pyproject.toml"
    versions["pyproject.toml (workspace)"] = extract_regex_first_group(root_pyproject, r'(?m)^version\s*=\s*"([^"]+)"')

    # 2. Client pyproject.toml
    client_pyproject = root / "isimotor-pulse-client" / "pyproject.toml"
    versions["isimotor-pulse-client/pyproject.toml"] = extract_regex_first_group(
        client_pyproject, r'(?m)^version\s*=\s*"([^"]+)"'
    )

    # 3. Client __init__.py
    client_init = root / "isimotor-pulse-client" / "isimotor_pulse_client" / "__init__.py"
    versions["isimotor_pulse_client/__init__.py"] = extract_regex_first_group(
        client_init, r'(?m)^__version__\s*=\s*"([^"]+)"'
    )

    # 3b. Types pyproject.toml
    types_pyproject = root / "binding" / "python" / "isimotor-pulse-types" / "pyproject.toml"
    versions["binding/python/isimotor-pulse-types/pyproject.toml"] = extract_regex_first_group(
        types_pyproject, r'(?m)^version\s*=\s*"([^"]+)"'
    )

    # 3c. Types __init__.py
    types_init = root / "binding" / "python" / "isimotor-pulse-types" / "isimotor_pulse_types" / "__init__.py"
    versions["isimotor_pulse_types/__init__.py"] = extract_regex_first_group(
        types_init, r'(?m)^__version__\s*=\s*"([^"]+)"'
    )

    # 4. Manager pyproject.toml (project.version)
    manager_pyproject = root / "isimotor-pulse-manager" / "pyproject.toml"
    versions["isimotor-pulse-manager/pyproject.toml [project]"] = extract_regex_first_group(
        manager_pyproject, r'(?m)^version\s*=\s*"([^"]+)"'
    )

    # 5. Manager pyproject.toml (tool.briefcase.version)
    if manager_pyproject.exists():
        content = manager_pyproject.read_text(encoding="utf-8")
        briefcase_match = re.search(r'(?s)\[tool\.briefcase\].*?version\s*=\s*"([^"]+)"', content)
        versions["isimotor-pulse-manager/pyproject.toml [tool.briefcase]"] = (
            briefcase_match.group(1).strip() if briefcase_match else None
        )
    else:
        versions["isimotor-pulse-manager/pyproject.toml [tool.briefcase]"] = None

    # 6. Manager __init__.py
    manager_init = root / "isimotor-pulse-manager" / "isimotor_pulse_manager" / "__init__.py"
    versions["isimotor_pulse_manager/__init__.py"] = extract_regex_first_group(
        manager_init, r'(?m)^__version__\s*=\s*"([^"]+)"'
    )

    # 7. Plugin CMakeLists.txt
    cmake_file = root / "isimotor-pulse-plugin" / "CMakeLists.txt"
    versions["isimotor-pulse-plugin/CMakeLists.txt"] = extract_regex_first_group(
        cmake_file, r"project\(isiMotor_Pulse\s+VERSION\s+([\d.]+)\s+LANGUAGES\s+CXX\)"
    )

    # 8. USER_NOTICE.md
    user_notice = root / "USER_NOTICE.md"
    versions["USER_NOTICE.md"] = extract_regex_first_group(user_notice, r"(?m)^>\s*\*\*Version\*\*:\s*([^\s]+)")

    return versions


def verify_versions(root: Path, target_version: str | None = None) -> tuple[bool, str, dict[str, str | None]]:
    """
    Checks if all project files have matching versions.
    If target_version is given, validates that all files match target_version.
    Returns (is_valid, resolved_version, versions_dict).
    """
    versions = collect_file_versions(root)

    expected_version = target_version.lstrip("v").strip() if target_version else None

    # If no target version specified, use root pyproject.toml as reference
    if not expected_version:
        expected_version = versions.get("pyproject.toml (workspace)")

    if not expected_version or not VERSION_REGEX.match(expected_version):
        return False, expected_version or "Unknown", versions

    cmake_expected = expected_version.split("-")[0]

    all_valid = True
    for file_desc, ver in versions.items():
        if ver is None:
            all_valid = False
            continue
        if "CMakeLists.txt" in file_desc:
            if ver != cmake_expected:
                all_valid = False
        else:
            if ver != expected_version:
                all_valid = False

    return all_valid, expected_version, versions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="isiMotor-Pulse-Plugin — Workspace Version Consistency Validator",
    )
    parser.add_argument(
        "target_version",
        nargs="?",
        default=None,
        help="Optional expected semantic version or Git tag (e.g. 0.1.2 or v0.1.2)",
    )

    args = parser.parse_args()
    root = get_project_root()

    print("==================================================================")
    print("  🔍  isiMotor-Pulse-Plugin — Version Consistency Check")
    print("==================================================================")

    if args.target_version:
        clean_target = args.target_version.lstrip("v").strip()
        print(f"  Target Version (from argument/tag) : v{clean_target}")
    else:
        print("  Mode : Validating internal consistency across workspace")

    is_valid, expected, file_versions = verify_versions(root, args.target_version)
    cmake_expected = expected.split("-")[0]

    print("------------------------------------------------------------------")
    for file_desc, ver in file_versions.items():
        exp = cmake_expected if "CMakeLists.txt" in file_desc else expected
        if ver is None:
            print(f"  ❌ {file_desc:<50} : NOT FOUND (Expected: {exp})")
        elif ver == exp:
            print(f"  ✓  {file_desc:<50} : {ver}")
        else:
            print(f"  ❌ {file_desc:<50} : {ver} (Expected: {exp})")
    print("==================================================================")

    if not is_valid:
        print(f"\n❌ Error: Version inconsistency detected! Expected version: {expected}")
        if args.target_version:
            print(f"   The workspace files do NOT match the release tag '{args.target_version}'.")
            print("   To synchronize all package versions before releasing, run:\n")
            print(f"     make version VERSION={args.target_version.lstrip('v')}\n")
        else:
            print("   Workspace files contain differing versions.")
            print("   To harmonize all packages, run:\n")
            print("     make version VERSION=<desired_version>\n")
        sys.exit(1)

    print(f"🎉 All workspace packages & configs are consistently synchronized at version v{expected}!\n")


if __name__ == "__main__":
    main()
