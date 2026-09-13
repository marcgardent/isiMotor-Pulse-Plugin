#!/usr/bin/env python3
"""
isiMotor-Pulse-Plugin — Automated Version Bump & Git Release Tagger.
Propagates semantic version numbers across all workspace packages,
validates Git clean state preconditions, commits changes, and creates signed/annotated release tags.

Copyright 2026 Marc GARDENT
Licensed under the Apache License, Version 2.0.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERSION_REGEX = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")


def get_project_root() -> Path:
    """Returns absolute path to repository root."""
    return Path(__file__).resolve().parent.parent


def check_git_preconditions(root: Path, target_version: str, allow_dirty: bool = False) -> None:
    """Verifies that git repository is clean and tag doesn't already exist."""
    # 1. Check if inside git work tree
    res = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print("❌ Error: Not a valid Git repository.", file=sys.stderr)
        sys.exit(1)

    # 2. Check for uncommitted changes
    if not allow_dirty:
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if status_res.stdout.strip():
            print("❌ Error: Git working directory is not clean.", file=sys.stderr)
            print("   Please commit or stash your changes before bumping version:\n", file=sys.stderr)
            print(status_res.stdout, file=sys.stderr)
            sys.exit(1)

    # 3. Check if tag already exists
    tag_name = f"v{target_version}" if not target_version.startswith("v") else target_version
    tag_res = subprocess.run(
        ["git", "tag", "-l", tag_name],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if tag_res.stdout.strip():
        print(f"❌ Error: Git tag '{tag_name}' already exists.", file=sys.stderr)
        sys.exit(1)


def update_file(path: Path, pattern: str, replacement: str, count: int = 0, flags: int = 0) -> bool:
    """Replaces regex pattern in file and returns True if file was modified."""
    if not path.exists():
        print(f"⚠️ Warning: File not found: {path}", file=sys.stderr)
        return False
    content = path.read_text(encoding="utf-8")
    new_content, num_subs = re.subn(pattern, replacement, content, count=count, flags=flags)
    if num_subs > 0 and new_content != content:
        path.write_text(new_content, encoding="utf-8")
        return True
    return False


def bump_all_files(root: Path, new_version: str) -> list[Path]:
    """Updates version number across all packages and configuration files."""
    cmake_version = new_version.split("-")[0]  # CMake prefers major.minor.patch
    updated_files: list[Path] = []

    # 1. Root pyproject.toml
    root_pyproject = root / "pyproject.toml"
    if update_file(root_pyproject, r'(?m)^version\s*=\s*"[^"]+"', f'version = "{new_version}"', count=1):
        updated_files.append(root_pyproject)

    # 2. isimotor-pulse-client/pyproject.toml
    client_pyproject = root / "isimotor-pulse-client" / "pyproject.toml"
    if update_file(client_pyproject, r'(?m)^version\s*=\s*"[^"]+"', f'version = "{new_version}"', count=1):
        updated_files.append(client_pyproject)

    # 3. isimotor-pulse-client/isimotor_pulse_client/__init__.py
    client_init = root / "isimotor-pulse-client" / "isimotor_pulse_client" / "__init__.py"
    if update_file(client_init, r'(?m)^__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"'):
        updated_files.append(client_init)

    # 3b. binding/python/isimotor-pulse-types/pyproject.toml
    types_pyproject = root / "binding" / "python" / "isimotor-pulse-types" / "pyproject.toml"
    if update_file(types_pyproject, r'(?m)^version\s*=\s*"[^"]+"', f'version = "{new_version}"', count=1):
        updated_files.append(types_pyproject)

    # 3c. binding/python/isimotor-pulse-types/isimotor_pulse_types/__init__.py
    types_init = root / "binding" / "python" / "isimotor-pulse-types" / "isimotor_pulse_types" / "__init__.py"
    if update_file(types_init, r'(?m)^__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"'):
        updated_files.append(types_init)

    # 4. isimotor-pulse-manager/pyproject.toml (under [project] and [tool.briefcase])
    manager_pyproject = root / "isimotor-pulse-manager" / "pyproject.toml"
    if update_file(manager_pyproject, r'(?m)^version\s*=\s*"[^"]+"', f'version = "{new_version}"'):
        updated_files.append(manager_pyproject)

    # 5. isimotor-pulse-manager/isimotor_pulse_manager/__init__.py
    manager_init = root / "isimotor-pulse-manager" / "isimotor_pulse_manager" / "__init__.py"
    if update_file(manager_init, r'(?m)^__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"'):
        updated_files.append(manager_init)

    # 6. isimotor-pulse-plugin/CMakeLists.txt
    cmake_file = root / "isimotor-pulse-plugin" / "CMakeLists.txt"
    if update_file(
        cmake_file,
        r"project\(isiMotor_Pulse\s+(?:VERSION\s+[\d.]+\s+)?LANGUAGES\s+CXX\)",
        f"project(isiMotor_Pulse VERSION {cmake_version} LANGUAGES CXX)",
    ):
        updated_files.append(cmake_file)

    # 7. USER_NOTICE.md
    user_notice = root / "USER_NOTICE.md"
    if update_file(user_notice, r"(?m)^>\s*\*\*Version\*\*:\s*.*$", f"> **Version**: {new_version}  "):
        updated_files.append(user_notice)

    # 7b. binding/rust/isimotor-pulse-schemas/Cargo.toml
    rust_schemas_cargo = root / "binding" / "rust" / "isimotor-pulse-schemas" / "Cargo.toml"
    if update_file(rust_schemas_cargo, r'(?m)^version\s*=\s*"[^"]+"', f'version = "{new_version}"', count=1):
        updated_files.append(rust_schemas_cargo)

    # 8. Update uv.lock if uv is available
    uv_bin = shutil.which("uv")
    if uv_bin:
        subprocess.run([uv_bin, "lock"], cwd=root, capture_output=True, text=True)
        uv_lock = root / "uv.lock"
        if uv_lock.exists():
            updated_files.append(uv_lock)

    return updated_files


def commit_and_tag(root: Path, target_version: str, files: list[Path]) -> str:
    """Stages updated files, commits with standard message, and creates annotated Git tag."""
    tag_name = f"v{target_version}" if not target_version.startswith("v") else target_version
    version_clean = target_version.lstrip("v")

    # 1. Git Add
    file_strs = [str(f.relative_to(root)) for f in files if f.exists()]
    subprocess.run(["git", "add", *file_strs], cwd=root, check=True)

    # 2. Git Commit
    commit_msg = f"chore(release): bump version to v{version_clean}"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=root, check=True)

    # 3. Git Tag
    subprocess.run(["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"], cwd=root, check=True)

    return tag_name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="isiMotor-Pulse-Plugin — Version Bump & Release Tagger",
    )
    parser.add_argument("version", help="New semantic version number (e.g. 1.5.0, 2.0.0-rc1)")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Bypass Git clean working directory check (not recommended for release)",
    )
    parser.add_argument(
        "--no-tag",
        action="store_true",
        help="Update version files without creating git commit and tag",
    )

    args = parser.parse_args()
    raw_version = args.version.strip()
    clean_version = raw_version.lstrip("v")

    if not VERSION_REGEX.match(clean_version):
        print(
            f"❌ Error: Invalid version format '{raw_version}'. Expected format: X.Y.Z (e.g. 1.5.0)",
            file=sys.stderr,
        )
        sys.exit(1)

    root = get_project_root()

    # Verify preconditions
    if not args.no_tag:
        check_git_preconditions(root, clean_version, allow_dirty=args.allow_dirty)

    print("==================================================================")
    print(f"  🏎️  isiMotor-Pulse-Plugin — Version Bump to v{clean_version}")
    print("==================================================================")

    # Update files
    updated = bump_all_files(root, clean_version)
    for f in updated:
        print(f"  ✓ Updated : {f.relative_to(root)}")

    if not updated:
        print("  - No files required modification.")

    # Commit and tag
    if not args.no_tag:
        tag_name = commit_and_tag(root, clean_version, updated)
        print(f"  ✓ Git Commit : chore(release): bump version to {tag_name}")
        print(f"  ✓ Git Tag    : {tag_name}")
        print("==================================================================")
        print("🎉 Version bump completed successfully!")
        print("To push changes and trigger the release pipeline on GitHub:")
        print(f"  git push origin main && git push origin {tag_name}")
        print("==================================================================")
    else:
        print("==================================================================")
        print(f"✓ Version updated to {clean_version} (skipped git commit and tag).")
        print("==================================================================")


if __name__ == "__main__":
    main()
