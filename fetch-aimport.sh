#!/usr/bin/env bash
#
# Builds the aimport engine runtime for the desktop app into electron/aimport/runtime
# (packaged by electron-builder as Resources/aimport). Builds for the host platform only:
# run it on each CI runner (mac arm64, Windows x64, Linux x64), like fetch-binaries.sh.
#
#   runtime/python/            Python 3.11 (python-build-standalone, installed by a pinned uv) with
#                              aimport's deps exactly as aimport/uv.lock pins them (--require-hashes)
#   runtime/bids-validator[.exe]  @bids/validator 2.4.1 compiled with a pinned, sha256-checked Deno
#   runtime/schema.json        BIDS 1.11.2 schema exported from aimport/bids-specification (bst export)
#   runtime/neuroglancer-client/  the QA viewer client, built from aimport/viewer-client (npm ci, lockfile hashes)
#   runtime/aimport_desktop.py the desktop shim (electron/aimport/aimport_desktop.py)
#
# Usage: ./fetch-aimport.sh <platform> [arch]     platform: darwin | linux | windows; arch: amd64 | arm64
# Requires: curl, unzip, uv (any version: a pinned one is run through uvx), node + npm, git submodules.

set -euo pipefail

UV_VERSION=0.13.9
PYTHON_VERSION=3.11.18
DENO_VERSION=2.5.6
BIDS_VALIDATOR_VERSION=2.4.1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AIMPORT_SRC="$SCRIPT_DIR/aimport"
OUT="$SCRIPT_DIR/electron/aimport/runtime"

platform="${1:-}"
arch="${2:-}"
[[ -z "$arch" ]] && case "$(uname -m)" in arm64|aarch64) arch=arm64 ;; *) arch=amd64 ;; esac

# Deno release target and the sha256 of its zip (from the release's .sha256sum files, checked 2026-11-24)
case "$platform-$arch" in
    darwin-arm64)  deno_target=aarch64-apple-darwin;      deno_sha=32a5b2bcf49432715719c7c769529269fbd08cafdc059b7cecd42f9d771059ab ;;
    darwin-amd64)  deno_target=x86_64-apple-darwin;       deno_sha=bd2a862509f930c5dee2aaef4939d6c161d833a7fec8d385d0c6e55c3136c4c2 ;;
    windows-amd64) deno_target=x86_64-pc-windows-msvc;    deno_sha=1327356cd63e23d0da7d11d5f5ca6b45902b1b62ee2debd4fbbd0aad2aab9786 ;;
    linux-amd64)   deno_target=x86_64-unknown-linux-gnu;  deno_sha=fd4f6abc1b6a134fa9a4dba56519f1631f44c88e04e4e3e9a8ff5975dfa66e1a ;;
    linux-arm64)   deno_target=aarch64-unknown-linux-gnu; deno_sha=f5e60ae3dfceb61e5e5a41f22129e40a8bc17f6393b59e75d7ca19ceef32d824 ;;
    *) echo "usage: $0 <darwin|linux|windows> [amd64|arm64]" >&2; exit 1 ;;
esac

host_platform=windows
[[ "$(uname -s)" == Darwin ]] && host_platform=darwin
[[ "$(uname -s)" == Linux ]] && host_platform=linux
if [[ "$platform" != "$host_platform" ]]; then
    echo "fetch-aimport.sh builds for the host only (host: $host_platform, asked: $platform)" >&2
    exit 1
fi

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
uvp() { uvx --from "uv==${UV_VERSION}" uv "$@"; }

test -f "$AIMPORT_SRC/bids-specification/src/schema/objects/datatypes.yaml" || {
    echo "aimport/bids-specification is empty: git submodule update --init aimport/bids-specification" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
rm -rf "$OUT"
mkdir -p "$OUT"

echo "== Python ${PYTHON_VERSION} (uv ${UV_VERSION})"
uvp python install "$PYTHON_VERSION" --install-dir "$TMP/py" --no-bin
pydir=$(find "$TMP/py" -mindepth 1 -maxdepth 1 -type d -name "cpython-${PYTHON_VERSION}-*" | head -n 1)
mv "$pydir" "$OUT/python"
if [[ "$platform" == windows ]]; then PY="$OUT/python/python.exe"; else PY="$OUT/python/bin/python3"; fi

echo "== aimport dependencies from uv.lock (hash-checked)"
(cd "$AIMPORT_SRC" && uvp export --locked --no-dev --no-emit-project --format requirements-txt -o "$TMP/requirements.txt")
uvp pip install --python "$PY" --break-system-packages --require-hashes -r "$TMP/requirements.txt"
# aimport itself, without resolving anything again (copied so the source tree gets no build files)
mkdir -p "$TMP/aimport-src"
cp -R "$AIMPORT_SRC/pyproject.toml" "$AIMPORT_SRC/README.md" "$AIMPORT_SRC/src" "$TMP/aimport-src/"
uvp pip install --python "$PY" --break-system-packages --no-deps "$TMP/aimport-src"
cp "$SCRIPT_DIR/electron/aimport/aimport_desktop.py" "$OUT/"

echo "== BIDS 1.11.2 schema"
"$PY" -I -m bidsschematools export --schema "$AIMPORT_SRC/bids-specification/src/schema" --output "$OUT/schema.json"

echo "== @bids/validator ${BIDS_VALIDATOR_VERSION} (Deno ${DENO_VERSION})"
curl -fsSL -o "$TMP/deno.zip" "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-${deno_target}.zip"
[[ "$(sha256 "$TMP/deno.zip")" == "$deno_sha" ]] || { echo "deno zip sha256 mismatch" >&2; exit 1; }
unzip -q -o "$TMP/deno.zip" -d "$TMP/deno"
exe=""; [[ "$platform" == windows ]] && exe=".exe"
DENO_DIR="$TMP/deno-cache" DENO_NO_UPDATE_CHECK=1 "$TMP/deno/deno$exe" compile -ERWN --no-check \
    --output "$OUT/bids-validator$exe" "jsr:@bids/validator@${BIDS_VALIDATOR_VERSION}"

echo "== Neuroglancer QA client"
mkdir -p "$TMP/ng" && cp "$AIMPORT_SRC/viewer-client/"{package.json,package-lock.json,build.mjs,index.html} "$TMP/ng/"
(cd "$TMP/ng" && npm ci --ignore-scripts --no-audit --no-fund && node build.mjs "$OUT/neuroglancer-client")

# Trim what the app never runs (tests, caches, headers, pip/idle/tk)
find "$OUT/python" -type d \( -name __pycache__ -o -name tests -o -name test \) -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf "$OUT/python/include" "$OUT/python/share"
for d in idlelib tkinter turtledemo ensurepip lib2to3; do
    rm -rf "$OUT/python/lib/python3.11/$d" "$OUT/python/Lib/$d"
done

cat > "$OUT/VERSIONS.txt" <<EOF
python ${PYTHON_VERSION} (uv ${UV_VERSION}), deps from aimport/uv.lock
@bids/validator ${BIDS_VALIDATOR_VERSION} (deno ${DENO_VERSION} compile)
schema: aimport/bids-specification $(git -C "$AIMPORT_SRC/bids-specification" rev-parse --short HEAD)
neuroglancer client: aimport/viewer-client/package-lock.json
EOF
du -sh "$OUT" "$OUT"/* | sed 's/^/  /'
echo "Done: $OUT"
