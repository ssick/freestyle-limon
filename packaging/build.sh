#!/usr/bin/env bash
set -euo pipefail

# Builds Freestyle Limón.app as a quick single-arch build using this repo's own
# pyenv-managed .venv - only runs on the same OS version and CPU architecture as
# this machine. For a portable universal2 build that runs on macOS 10.13+ on both
# Intel and Apple Silicon, use build_universal2.sh instead.
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

# The identifier varies by *where* the app is built, and is otherwise stable.
#
# macOS resolves an app's identity - Dock tile, activation, which window comes
# forward - by CFBundleIdentifier, not by path. Two bundles sharing one
# identifier are two processes claiming to be the same app, so a stale copy in a
# worktree can steal focus from the build you just made: the new process starts
# correctly while the old one's window is raised. Giving worktree builds their
# own identifier stops that.
#
# It deliberately does NOT vary per build or per commit. A bundle identifier
# macOS has never seen before is refused on its first Finder launch (the bare
# "can't be opened" dialog from CoreServicesUIAgent) while `open` from a shell
# still works - so a per-build identifier would demand a fresh approval after
# every single build. Few stable identifiers, approved once, is the workable
# shape; per-build identity is not.
# The suffix shows up as-is in the standard About panel (e.g. "Version 0.1.0-dev-arm64"),
# so this build is never mistaken for the universal2 release build it sits next to - both
# that it isn't meant to be distributed, and which single arch it actually contains.
# `uname -m`, not $FREESTYLE_LIMON_TARGET_ARCH: that env var isn't exported yet at this
# point in the script, and target_arch=None (empty override, set further down) means
# "whatever arch is running this interpreter" - which is exactly what `uname -m` reports.
VERSION="0.1.0-dev-$(uname -m)"
BUILD="$(git rev-list --count HEAD)"
BUNDLE_ID="$BUNDLE_ID_PREFIX"
if [ "$(git rev-parse --git-dir)" != "$(git rev-parse --git-common-dir)" ]; then
  BUNDLE_ID="${BUNDLE_ID_PREFIX}.worktree"
fi

export FL_BUNDLE_ID="$BUNDLE_ID"
export FL_VERSION="$VERSION"
export FL_BUILD="$BUILD"

echo "==> Bundle identifier: $BUNDLE_ID"

echo "==> Installing build dependencies"
source .venv/bin/activate
pip install -q -r requirements-build.txt

echo "==> Running PyInstaller"
export FREESTYLE_LIMON_TARGET_ARCH=
export FREESTYLE_LIMON_MIN_MACOS=11.0
pyinstaller --clean -y freestyle-limon.spec

built_app="$REPO_ROOT/dist/Freestyle Limón.app"

LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

# PyInstaller builds with --clean, which deletes and recreates the .app rather
# than updating it in place. A Finder window left open on dist/ (or any cached
# LaunchServices record) then refers to a directory that no longer exists, and
# double-clicking the app can fail with a bare "cannot be opened" while
# `open dist/...` from a shell - which resolves the path afresh - still works.
# Registering the new bundle explicitly makes LaunchServices point at what was
# actually just built.
echo "==> Registering the new bundle with LaunchServices"
"$LSREG" -f "$built_app"

echo "==> Checking for other copies of this app"

# Queried via lsregister, not mdfind. mdfind reads the Spotlight index, which
# never covers dot-directories - so a build sitting in .claude/worktrees/*/dist
# was invisible to this check while remaining fully visible to LaunchServices
# (lsregister descends into invisible directories). That false all-clear let a
# stale bundle sit around unnoticed. lsregister is the database macOS actually
# resolves against, so ask that one.
#
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
