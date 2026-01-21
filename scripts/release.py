#!/usr/bin/env python3
"""Release automation script for CodeCrew.

This script automates the release process:
1. Validates the release version
2. Updates version in __init__.py
3. Updates CHANGELOG.md
4. Creates a git tag
5. Optionally pushes to remote

Usage:
    python scripts/release.py 1.0.1
    python scripts/release.py 1.0.1 --push
    python scripts/release.py 1.0.1 --dry-run
"""

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def validate_version(version: str) -> bool:
    """Validate semantic version format."""
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$"
    return bool(re.match(pattern, version))


def get_current_version() -> str:
    """Get the current version from __init__.py."""
    init_file = get_project_root() / "codecrew" / "__init__.py"
    content = init_file.read_text()
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    raise ValueError("Could not find version in __init__.py")


def update_version(new_version: str, dry_run: bool = False) -> None:
    """Update version in __init__.py."""
    init_file = get_project_root() / "codecrew" / "__init__.py"
    content = init_file.read_text()

    new_content = re.sub(
        r'(__version__\s*=\s*["\'])[^"\']+(["\'])',
        rf'\g<1>{new_version}\g<2>',
        content,
    )

    if dry_run:
        print(f"Would update __init__.py version to {new_version}")
    else:
        init_file.write_text(new_content)
        print(f"Updated __init__.py version to {new_version}")


def update_pyproject_version(new_version: str, dry_run: bool = False) -> None:
    """Update version in pyproject.toml."""
    pyproject_file = get_project_root() / "pyproject.toml"
    content = pyproject_file.read_text()

    new_content = re.sub(
        r'(version\s*=\s*["\'])[^"\']+(["\'])',
        rf'\g<1>{new_version}\g<2>',
        content,
        count=1,
    )

    if dry_run:
        print(f"Would update pyproject.toml version to {new_version}")
    else:
        pyproject_file.write_text(new_content)
        print(f"Updated pyproject.toml version to {new_version}")


def update_changelog(new_version: str, dry_run: bool = False) -> None:
    """Update CHANGELOG.md with release date."""
    changelog_file = get_project_root() / "CHANGELOG.md"
    content = changelog_file.read_text()

    today = date.today().isoformat()

    # Update [Unreleased] section header
    new_content = re.sub(
        r"## \[Unreleased\]",
        f"## [Unreleased]\n\n## [{new_version}] - {today}",
        content,
    )

    # Update comparison links at the bottom
    old_version = get_current_version()
    new_content = re.sub(
        r"\[Unreleased\]: (https://github\.com/[^/]+/[^/]+)/compare/v([^.]+)\.\.\.HEAD",
        rf"[Unreleased]: \g<1>/compare/v{new_version}...HEAD\n[{new_version}]: \g<1>/compare/v{old_version}...v{new_version}",
        new_content,
    )

    if dry_run:
        print(f"Would update CHANGELOG.md for version {new_version}")
    else:
        changelog_file.write_text(new_content)
        print(f"Updated CHANGELOG.md for version {new_version}")


def run_tests() -> bool:
    """Run the test suite."""
    print("Running tests...")
    result = subprocess.run(
        ["pytest", "tests/", "-v", "--tb=short"],
        cwd=get_project_root(),
    )
    return result.returncode == 0


def run_linting() -> bool:
    """Run linting checks."""
    print("Running linting...")
    result = subprocess.run(
        ["ruff", "check", "codecrew", "tests"],
        cwd=get_project_root(),
    )
    return result.returncode == 0


def git_commit(version: str, dry_run: bool = False) -> None:
    """Create a git commit for the release."""
    message = f"chore: Release v{version}"

    if dry_run:
        print(f"Would create commit: {message}")
        return

    subprocess.run(
        ["git", "add", "codecrew/__init__.py", "pyproject.toml", "CHANGELOG.md"],
        cwd=get_project_root(),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=get_project_root(),
        check=True,
    )
    print(f"Created commit: {message}")


def git_tag(version: str, dry_run: bool = False) -> None:
    """Create a git tag for the release."""
    tag = f"v{version}"

    if dry_run:
        print(f"Would create tag: {tag}")
        return

    subprocess.run(
        ["git", "tag", "-a", tag, "-m", f"Release {tag}"],
        cwd=get_project_root(),
        check=True,
    )
    print(f"Created tag: {tag}")


def git_push(dry_run: bool = False) -> None:
    """Push commits and tags to remote."""
    if dry_run:
        print("Would push to remote with tags")
        return

    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=get_project_root(),
        check=True,
    )
    subprocess.run(
        ["git", "push", "origin", "--tags"],
        cwd=get_project_root(),
        check=True,
    )
    print("Pushed to remote")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Release automation for CodeCrew")
    parser.add_argument("version", help="New version number (e.g., 1.0.1)")
    parser.add_argument("--push", action="store_true", help="Push to remote after release")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")

    args = parser.parse_args()

    # Validate version
    if not validate_version(args.version):
        print(f"Error: Invalid version format: {args.version}")
        print("Expected format: X.Y.Z or X.Y.Z-suffix")
        return 1

    current_version = get_current_version()
    print(f"Current version: {current_version}")
    print(f"New version: {args.version}")

    if args.dry_run:
        print("\n=== DRY RUN MODE ===\n")

    # Run tests
    if not args.skip_tests and not args.dry_run:
        if not run_tests():
            print("Error: Tests failed")
            return 1
        if not run_linting():
            print("Warning: Linting issues found (continuing anyway)")

    # Update files
    update_version(args.version, args.dry_run)
    update_pyproject_version(args.version, args.dry_run)
    update_changelog(args.version, args.dry_run)

    # Git operations
    git_commit(args.version, args.dry_run)
    git_tag(args.version, args.dry_run)

    if args.push:
        git_push(args.dry_run)

    print(f"\n{'Would release' if args.dry_run else 'Released'} version {args.version}")

    if not args.push and not args.dry_run:
        print("\nTo push the release:")
        print("  git push origin main")
        print("  git push origin --tags")

    return 0


if __name__ == "__main__":
    sys.exit(main())
