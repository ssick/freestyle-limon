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

BUNDLE_ID="dev.stansick.freestyle-limon"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Installing build dependencies"
source .venv/bin/activate
pip install -q -r requirements-build.txt

echo "==> Running PyInstaller"
pyinstaller --clean -y freestyle-limon.spec

echo "==> Checking for duplicate installed copies"
built_app="$REPO_ROOT/dist/Freestyle Limón.app"

# Compared with -ef (same inode) rather than string equality: macOS stores
# "Limón" decomposed (NFD) on disk while this script's string literal is
# precomposed (NFC), so the two spellings never compare equal as text even
# when they name the same directory.
others=()
while IFS= read -r candidate; do
  [ -n "$candidate" ] || continue
  [ "$candidate" -ef "$built_app" ] && continue
  others+=("$candidate")
done < <(mdfind "kMDItemCFBundleIdentifier == '$BUNDLE_ID'" 2>/dev/null)

if [ ${#others[@]} -gt 0 ]; then
  echo
  echo "WARNING: other bundles share the identifier '$BUNDLE_ID':"
  printf '  %s\n' "${others[@]}"
  echo
  echo "macOS may launch one of those instead of the build you just made,"
  echo "even if you double-click this one. Delete or replace them first."
else
  echo "    none found - the build in dist/ is the only copy."
fi

echo
echo "==> Done: dist/Freestyle Limón.app"
