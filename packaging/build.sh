#!/usr/bin/env bash
set -euo pipefail

# Builds Freestyle Limón.app.
#
# --clean is used as plain hygiene: it discards PyInstaller's local build/
# directory and its global cache (~/Library/Application Support/pyinstaller/,
# which is shared across every PyInstaller project on the machine) so a build
# can't be influenced by leftover state from an earlier build or another
# project. Builds are only ~20s, so there's no reason not to.
#
# After building, this checks for *other* copies of the app bundle installed
# elsewhere. macOS LaunchServices resolves apps by CFBundleIdentifier, not by
# path - so if a second bundle with the same identifier exists (e.g. an older
# copy in /Applications), double-clicking the freshly-built one can silently
# launch the stale copy instead. That produced a genuinely baffling debugging
# session: the new build was correct and verifiable on disk, but the running
# app was a three-day-old binary missing a whole feature.

BUNDLE_ID_PREFIX="dev.stansick.freestyle-limon"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Every release gets its own bundle identifier, suffixed with the commit it was
# built from. macOS resolves an app's identity - Dock tile, activation, which
# window comes forward - by CFBundleIdentifier, not by path. Two bundles sharing
# one identifier are therefore two processes claiming to be the same app, and a
# stale copy can surface in place of the one you just built. Suffixing per commit
# makes each build a distinct app to macOS, so old and new coexist unambiguously.
#
# The suffix is derived from the commit rather than the wall clock so that
# rebuilding the same commit reproduces the same identifier.
VERSION="0.1.0"
BUILD="$(git rev-list --count HEAD)"
SHA="$(git rev-parse --short HEAD)"
git diff --quiet HEAD 2>/dev/null || SHA="${SHA}-dirty"
BUNDLE_ID="${BUNDLE_ID_PREFIX}.${BUILD}-${SHA}"

export FL_BUNDLE_ID="$BUNDLE_ID"
export FL_VERSION="$VERSION"
export FL_BUILD="$BUILD"

echo "==> Bundle identifier: $BUNDLE_ID"

echo "==> Installing build dependencies"
source .venv/bin/activate
pip install -q -r requirements-build.txt

echo "==> Running PyInstaller"
pyinstaller --clean -y freestyle-limon.spec

echo "==> Checking for other copies of this app"
built_app="$REPO_ROOT/dist/Freestyle Limón.app"

# Queried via lsregister, not mdfind. mdfind reads the Spotlight index, which
# never covers dot-directories - so a build sitting in .claude/worktrees/*/dist
# was invisible to this check while remaining fully visible to LaunchServices
# (lsregister descends into invisible directories). That false all-clear let a
# stale bundle sit around unnoticed. lsregister is the database macOS actually
# resolves against, so ask that one.
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

# Within an lsregister record the path line precedes the identifier line, so
# carry the most recent path forward and emit it when the identifier matches.
others=()
while IFS=$'\t' read -r found_id candidate; do
  [ -n "$candidate" ] || continue
  [ "$candidate" -ef "$built_app" ] && continue
  others+=("$found_id  ->  $candidate")
done < <("$LSREG" -dump 2>/dev/null | awk -v prefix="$BUNDLE_ID_PREFIX" '
    /^path:/ { p=$0; sub(/^path:[ \t]*/,"",p); sub(/ \(0x[0-9a-f]+\)$/,"",p) }
    /^identifier:/ { if (index($2, prefix)==1 && p!="") print $2 "\t" p }
  ' | sort -u)

if [ ${#others[@]} -gt 0 ]; then
  echo
  echo "NOTE: other builds of this app are registered with macOS:"
  printf '  %s\n' "${others[@]}"
  echo
  echo "Each carries its own identifier, so they coexist with this build rather"
  echo "than competing with it for Dock tile, activation, or window focus."
  echo "Delete any you no longer want."
else
  echo "    none found - the build in dist/ is the only copy."
fi

echo
echo "==> Done: dist/Freestyle Limón.app"
