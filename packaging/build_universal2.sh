#!/usr/bin/env bash
set -euo pipefail

# Builds Freestyle Limón.app as a universal2 (arm64 + x86_64) bundle that runs on
# macOS 10.13+, using python.org's official universal2 Python instead of a
# pyenv-built interpreter (which is single-arch and targets whatever macOS
# version it was compiled on - see README.md's "Standalone macOS app" section
# for why this matters and where to get that installer).
#
# Two of this project's pinned build dependencies - Pillow and pydantic_core (a
# transitive FastAPI dependency) - don't publish universal2 wheels on PyPI, only
# separate arm64/x86_64 ones, which makes PyInstaller abort with
# IncompatibleBinaryArchError. This script downloads both arch wheels for each
# and merges them with `delocate-merge` before building. If a future dependency
# bump introduces a new thin binary, PyInstaller's own error will name the
# offending file - add its package name to THIN_PACKAGES below.

PYTHON="${PYTHON_ORG_BIN:-/usr/local/bin/python3.12}"
PY_TAG="cp312"
ARM64_PLATFORM="macosx_11_0_arm64"
X86_64_PLATFORM="macosx_10_13_x86_64"
THIN_PACKAGES=(Pillow pydantic_core)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv-build"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

if [ ! -x "$PYTHON" ]; then
  echo "error: $PYTHON not found." >&2
  echo "Install python.org's official universal2 installer first - see README.md's" >&2
  echo "'Standalone macOS app' section - or set PYTHON_ORG_BIN to point at it." >&2
  exit 1
fi

echo "==> Creating build venv at $VENV_DIR"
rm -rf "$VENV_DIR"
"$PYTHON" -m venv "$VENV_DIR"
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

echo "==> Installing runtime + build dependencies"
# Deliberately not using requirements.txt's uvicorn[standard] extra: uvloop /
# httptools / websockets / watchfiles are perf-only accelerators uvicorn falls
# back from gracefully when absent, and several don't ship universal2 wheels -
# skipping them avoids merging wheels for accelerators the packaged app (a
# single local user hitting localhost) doesn't meaningfully benefit from.
pip install -q fastapi uvicorn pylibrelinkup python-dotenv -r "$REPO_ROOT/requirements-build.txt"

for package in "${THIN_PACKAGES[@]}"; do
  version="$(pip show "$package" 2>/dev/null | awk -F': ' '/^Version/{print $2}')"
  if [ -z "$version" ]; then
    echo "==> $package not installed, skipping merge"
    continue
  fi
  echo "==> Merging $package==$version (arm64 + x86_64 -> universal2)"
  wheel_dir="$WORK_DIR/$package-wheels"
  merged_dir="$WORK_DIR/$package-merged"
  mkdir -p "$wheel_dir" "$merged_dir"
  pip download --no-deps --dest "$wheel_dir" --platform "$ARM64_PLATFORM" \
    --python-version 312 --implementation cp --abi "$PY_TAG" --only-binary=:all: "$package==$version" -q
  pip download --no-deps --dest "$wheel_dir" --platform "$X86_64_PLATFORM" \
    --python-version 312 --implementation cp --abi "$PY_TAG" --only-binary=:all: "$package==$version" -q
  delocate-merge "$wheel_dir"/*.whl -w "$merged_dir"
  pip install --force-reinstall --no-deps "$merged_dir"/*.whl -q
done

echo "==> Running PyInstaller"
cd "$REPO_ROOT"

# Same identifier/version derivation as build.sh - see its comments for why this
# matters (a missing/zero CFBundleVersion breaks macOS's "prefer the newer
# build" tie-break between bundles sharing an identifier). Run after cd'ing to
# REPO_ROOT so `git` resolves this repo regardless of the invoking directory.
BUNDLE_ID_PREFIX="dev.stansick.freestyle-limon"
VERSION="0.1.0"
BUILD="$(git rev-list --count HEAD)"
BUNDLE_ID="$BUNDLE_ID_PREFIX"
if [ "$(git rev-parse --git-dir)" != "$(git rev-parse --git-common-dir)" ]; then
  BUNDLE_ID="${BUNDLE_ID_PREFIX}.worktree"
fi
export FL_BUNDLE_ID="$BUNDLE_ID"
export FL_VERSION="$VERSION"
export FL_BUILD="$BUILD"

pyinstaller -y freestyle-limon.spec

echo "==> Verifying architectures"
lipo -info "dist/Freestyle Limón.app/Contents/MacOS/freestyle-limon"
echo "LSMinimumSystemVersion: $(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' 'dist/Freestyle Limón.app/Contents/Info.plist')"

echo "==> Done: dist/Freestyle Limón.app"
