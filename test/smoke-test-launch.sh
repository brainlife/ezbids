#!/usr/bin/env bash
#
# Launches the packed desktop app (after npm run electron:pack-test) with its window, checks that the backend it
# starts answers HTTP and that the app is still running 15 s later, then kills it. Linux runs it under xvfb-run with
# --no-sandbox (an --dir build's chrome-sandbox is not setuid root). No clicks: GUI flows are not tested here.
#
#   ./test/smoke-test-launch.sh [release_dir]      default: electron/release

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE_DIR="${1:-${EZBIDS_RELEASE_DIR:-$ROOT/electron/release}}"
LOG="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/ezbids-launch-$$.log"

case "$(uname -s)" in
    Darwin) os=darwin; exe="$(find "$RELEASE_DIR" -maxdepth 5 -path '*.app/Contents/MacOS/*' -type f | head -n 1)" ;;
    Linux) os=linux; exe="$(find "$RELEASE_DIR"/linux*-unpacked -maxdepth 1 -type f -perm -u+x ! -name '*.so*' ! -name 'chrome*' | head -n 1)" ;;
    *) os=windows; exe="$(find "$RELEASE_DIR"/win*-unpacked -maxdepth 1 -type f -iname '*.exe' ! -iname 'elevate.exe' | head -n 1)" ;;
esac
[[ -n "$exe" && -f "$exe" ]] || { echo "no packed executable under $RELEASE_DIR" >&2; exit 1; }
echo "launching $exe (log: $LOG)"

unset ELECTRON_RUN_AS_NODE
if [[ "$os" == linux ]]; then
    xvfb-run -a "$exe" --no-sandbox >"$LOG" 2>&1 &
else
    "$exe" >"$LOG" 2>&1 &
fi

stop() {
    if [[ "$os" == windows ]]; then
        taskkill //F //T //IM "$(basename "$exe")" >/dev/null 2>&1 || true
    else
        pkill -f "$exe" 2>/dev/null || true
        sleep 2
        pkill -9 -f "$exe" 2>/dev/null || true
    fi
}
trap stop EXIT

port=""
for _ in $(seq 1 90); do
    port="$(sed -n 's/.*Backend spawned on port \([0-9][0-9]*\).*/\1/p' "$LOG" | head -n 1)"
    [[ -n "$port" ]] && curl -s -o /dev/null --max-time 2 "http://127.0.0.1:${port}/" && break
    sleep 1
done
if [[ -z "$port" ]] || ! curl -s -o /dev/null --max-time 2 "http://127.0.0.1:${port}/"; then
    echo "--- app log ---"; grep -v '^ *[A-Z_]*:' "$LOG" | tail -n 80
    echo "smoke-test-launch FAILED: the backend did not answer" >&2
    exit 1
fi
echo "backend answers on port $port"
sleep 15
grep -E 'Starting frontend|Handler spawned|Backend spawned' "$LOG" || true
if ! curl -s -o /dev/null --max-time 2 "http://127.0.0.1:${port}/"; then
    echo "--- app log ---"; tail -n 80 "$LOG"
    echo "smoke-test-launch FAILED: the app stopped within 15 s" >&2
    exit 1
fi
if grep -qiE 'Uncaught exception|crashed|Failed to load' "$LOG"; then
    echo "--- app log ---"; tail -n 80 "$LOG"
    echo "smoke-test-launch FAILED: errors in the app log" >&2
    exit 1
fi
echo "smoke-test-launch: the app started and kept running"
