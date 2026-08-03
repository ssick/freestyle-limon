#!/usr/bin/env bash
set -euo pipefail

# Builds Freestyle Limón.app from a clean state.
#
# PyInstaller keeps two caches that can go stale and silently produce a
# binary that doesn't reflect recent source changes, even though the build
# itself reports success: the local build/ directory (per-repo
# intermediate artifacts) and a *global*, cross-repo cache at
# ~/Library/Application Support/pyinstaller/ (cached bootloaders and
# module-analysis results, shared across every PyInstaller project on this
# machine). A build using a stale copy of that global cache is how a
# native menu item ended up silently missing from a build despite the
# source tree being correct and unchanged. --clean purges both caches
# before building, which is the only reliable way to guarantee a build
# actually reflects the current source tree.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Installing build dependencies"
source .venv/bin/activate
pip install -q -r requirements-build.txt

echo "==> Running PyInstaller (--clean forces a fully fresh build, ignoring all caches)"
pyinstaller --clean -y freestyle-limon.spec

echo "==> Done: dist/Freestyle Limón.app"
