#!/usr/bin/env bash
# Build diagnostic components only. Never installs or changes packaged libraries.
set -eo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_ROOT="${1:?Usage: build_harmonic_overlay.sh NEW_BUILD_DIRECTORY}"
if [ -e "$BUILD_ROOT" ]; then
  echo "Refusing to overwrite an existing directory: $BUILD_ROOT" >&2
  exit 1
fi
mkdir -p "$BUILD_ROOT/src"
BUILD_ROOT="$(cd "$BUILD_ROOT" && pwd)"
while read -r expected relative; do
  mkdir -p "$BUILD_ROOT/src/$(dirname "$relative")"
  curl --fail --location --retry 2 \
    "https://raw.githubusercontent.com/gazebosim/gz-sim/gz-sim8_8.15.0/$relative" \
    --output "$BUILD_ROOT/src/$relative"
done < "$HERE/backport/upstream-files.sha256"
(cd "$BUILD_ROOT/src" && sha256sum --check "$HERE/backport/upstream-files.sha256")
patch -d "$BUILD_ROOT/src" -p1 < "$HERE/backport/harmonic-backport.patch"
cp "$HERE/backport/CMakeLists.txt" "$BUILD_ROOT/src/CMakeLists.txt"
cmake -S "$BUILD_ROOT/src" -B "$BUILD_ROOT/build" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo
nice -n 15 cmake --build "$BUILD_ROOT/build" --parallel 1
printf 'Diagnostic overlay: %s\n' "$BUILD_ROOT/build/overlay"
