#!/usr/bin/env bash
#
# Headless end-to-end check of the packed desktop app (after npm run electron:pack-test): classic ezBIDS preprocess
# and the AI import engine (scan -> plan -> approve -> execute -> validated) on a synthetic DICOM series, run by the
# packed app's own Electron binary as node. See test/smoke-test-aimport.ts.
#
#   ./test/smoke-test-aimport.sh [release_dir]      default: electron/release

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE_DIR="${1:-${EZBIDS_RELEASE_DIR:-$ROOT/electron/release}}"
TMP="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/ezbids-smoke-$$"
mkdir -p "$TMP"

case "$(uname -s)" in
    Darwin) exe="$(find "$RELEASE_DIR" -maxdepth 5 -path '*.app/Contents/MacOS/*' -type f | head -n 1)" ;;
    Linux) exe="$(find "$RELEASE_DIR"/linux*-unpacked -maxdepth 1 -type f -perm -u+x ! -name '*.so*' ! -name 'chrome*' | head -n 1)" ;;
    *) exe="$(find "$RELEASE_DIR"/win*-unpacked -maxdepth 1 -type f -iname '*.exe' ! -iname 'elevate.exe' | head -n 1)" ;;
esac
[[ -n "$exe" && -f "$exe" ]] || { echo "no packed executable under $RELEASE_DIR" >&2; exit 1; }
echo "packed executable: $exe"
ELECTRON_RUN_AS_NODE=1 "$exe" --version

"$ROOT/node_modules/.bin/esbuild" "$ROOT/test/smoke-test-aimport.ts" --bundle --platform=node --format=cjs \
    --target=node20 --outfile="$TMP/smoke-test-aimport.cjs" --log-level=warning

# offline: outbound HTTP(S) from the engine, ezBIDS and the validator goes to a closed port; loopback is direct
export HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 ALL_PROXY=http://127.0.0.1:9 NO_PROXY=127.0.0.1,localhost
export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY" all_proxy="$ALL_PROXY" no_proxy="$NO_PROXY"
unset ANTHROPIC_API_KEY OPENAI_API_KEY DASHSCOPE_API_KEY OLLAMA_BASE_URL
ELECTRON_RUN_AS_NODE=1 "$exe" "$TMP/smoke-test-aimport.cjs" "$TMP/run" "$ROOT/test/make-synthetic-dicom.py"
