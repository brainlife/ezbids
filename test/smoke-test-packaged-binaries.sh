#!/usr/bin/env bash
#
# Smoke-test native binaries inside an electron-builder --dir output.
# Run after: npm run electron:pack-test (or build:electron + app:dir).
#
# Verifies fetch-binaries assets were copied to Resources/resources/bin and
# that key executables run (--version / --help).
#
# Optional env overrides (CI matrix sets these explicitly):
#   EZBIDS_PLATFORM  darwin | linux | windows
#   EZBIDS_ARCH      amd64 | arm64
#   EZBIDS_RELEASE_DIR  path to electron/release (default: electron/release)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE_DIR="${EZBIDS_RELEASE_DIR:-$ROOT/electron/release}"

platform="${EZBIDS_PLATFORM:-}"
arch="${EZBIDS_ARCH:-}"

if [[ -z "$platform" ]]; then
    case "$(uname -s)" in
        Darwin) platform="darwin" ;;
        Linux) platform="linux" ;;
        MINGW* | MSYS* | CYGWIN*) platform="windows" ;;
        *)
            echo "Unsupported OS: $(uname -s)" >&2
            exit 1
            ;;
    esac
fi

if [[ -z "$arch" ]]; then
    case "$(uname -m)" in
        arm64 | aarch64) arch="arm64" ;;
        x86_64 | amd64) arch="amd64" ;;
        *)
            echo "Unsupported architecture: $(uname -m)" >&2
            exit 1
            ;;
    esac
fi

fail() {
    echo "smoke-test FAILED: $*" >&2
    exit 1
}

require_file() {
    local label="$1"
    local file_path="$2"
    if [[ ! -f "$file_path" ]]; then
        fail "${label} not found at ${file_path}"
    fi
    echo "  ok: ${label} -> ${file_path}"
}

# run_check <label> <output_pattern> <command...>
# output_pattern: extended regex matched against combined stdout+stderr.
run_check() {
    local label="$1"
    local pattern="$2"
    shift 2
    echo "==> ${label}"
    local out
    out="$("$@" 2>&1 || true)"
    if ! echo "$out" | grep -qiE "$pattern"; then
        fail "${label}: expected output matching /${pattern}/, got:${out:+$'\n'}${out}"
    fi
    echo "$out"
}

find_packaged_bin_dir() {
    local candidate
    candidate="$(find "$RELEASE_DIR" -path '*/Contents/Resources/bin' -type d 2>/dev/null | head -n 1 || true)"
    if [[ -n "$candidate" ]]; then
        echo "$candidate"
        return 0
    fi
    candidate="$(find "$RELEASE_DIR" -path '*/resources/bin' -type d 2>/dev/null | head -n 1 || true)"
    if [[ -n "$candidate" ]]; then
        echo "$candidate"
        return 0
    fi
    return 1
}

find_packaged_app_dir() {
    local candidate
    candidate="$(find "$RELEASE_DIR" -path '*/Contents/Resources/app' -type d 2>/dev/null | head -n 1 || true)"
    if [[ -n "$candidate" ]]; then
        echo "$candidate"
        return 0
    fi
    candidate="$(find "$RELEASE_DIR" -path '*/resources/app' -type d 2>/dev/null | head -n 1 || true)"
    if [[ -n "$candidate" ]]; then
        echo "$candidate"
        return 0
    fi
    return 1
}

if [[ ! -d "$RELEASE_DIR" ]]; then
    fail "release directory not found: ${RELEASE_DIR} (run npm run electron:pack-test first)"
fi

BIN_DIR="$(find_packaged_bin_dir || true)"
if [[ -z "$BIN_DIR" ]]; then
    echo "Contents of ${RELEASE_DIR}:"
    find "$RELEASE_DIR" -maxdepth 4 -type d 2>/dev/null | sed 's/^/  /' || true
    fail "could not find packaged bin directory under ${RELEASE_DIR}"
fi

APP_DIR="$(find_packaged_app_dir || true)"
if [[ -z "$APP_DIR" ]]; then
    fail "could not find packaged app directory under ${RELEASE_DIR}"
fi

echo "smoke-test: platform=${platform} arch=${arch}"
echo "smoke-test: bin_dir=${BIN_DIR}"
echo "smoke-test: app_dir=${APP_DIR}"

# --- dcm2niix (fetch-binaries) ---
if [[ "$platform" == "windows" ]]; then
    dcm2niix_exe="${BIN_DIR}/dcm2niix/dcm2niix-${platform}-${arch}.exe"
else
    dcm2niix_exe="${BIN_DIR}/dcm2niix/dcm2niix-${platform}-${arch}"
fi
if [[ "$platform" != "windows" ]]; then
    chmod +x "$dcm2niix_exe" 2>/dev/null || true
fi
require_file "dcm2niix" "$dcm2niix_exe"
run_check "dcm2niix --version" 'dcm2niix|dcm2niiX' "$dcm2niix_exe" --version

# --- 7z (fetch-binaries) ---
if [[ "$platform" == "windows" ]]; then
    sevenz_exe="${BIN_DIR}/7z/7z-${platform}-${arch}.exe"
    sevenz_dll="${BIN_DIR}/7z/7z.dll"
    require_file "7z.dll" "$sevenz_dll"
else
    sevenz_exe="${BIN_DIR}/7z/7z-${platform}-${arch}"
fi
if [[ "$platform" != "windows" ]]; then
    chmod +x "$sevenz_exe" 2>/dev/null || true
fi
require_file "7z" "$sevenz_exe"
run_check "7z (usage)" '7-[Zz]ip|7z' bash -c "\"$sevenz_exe\" 2>&1 | head -n 5"

# --- allineate (fetch-binaries) ---
if [[ "$platform" == "windows" ]]; then
    allineate_exe="${BIN_DIR}/allineate/allineate-${platform}-${arch}.exe"
else
    allineate_exe="${BIN_DIR}/allineate/allineate-${platform}-${arch}"
fi
if [[ "$platform" != "windows" ]]; then
    chmod +x "$allineate_exe" 2>/dev/null || true
fi
require_file "allineate" "$allineate_exe"
run_check "allineate" 'allineate|Usage' bash -c "\"$allineate_exe\" 2>&1 | head -n 5"

# --- python runtime + pet tools (fetch-binaries) ---
py_root="${BIN_DIR}/python-runtime"
if [[ "$platform" == "windows" ]]; then
    python_exe="${py_root}/python/python.exe"
    site_packages="${py_root}/venv/Lib/site-packages"
else
    python_exe="${py_root}/python/bin/python3"
    site_packages="${py_root}/venv/lib/python3.8/site-packages"
fi
if [[ "$platform" != "windows" ]]; then
    chmod +x "$python_exe" 2>/dev/null || true
fi
require_file "python" "$python_exe"
if [[ ! -d "$site_packages" ]]; then
    fail "python site-packages not found at ${site_packages}"
fi
echo "  ok: python site-packages -> ${site_packages}"

export PYTHONHOME="${py_root}/python"
export PYTHONPATH="${site_packages}"
if [[ -n "${dcm2niix_exe:-}" && -f "$dcm2niix_exe" ]]; then
    export DCM2NIIX_PATH="$dcm2niix_exe"
fi

run_check "python --version" 'Python' "$python_exe" --version
run_check "dcm2niix4pet --help" 'dcm2niix4pet|usage:' "$python_exe" -m pypet2bids.dcm2niix4pet --help
run_check "ecatpet2bids --help" 'ecat_cli|usage:' "$python_exe" -m pypet2bids.ecat_cli --help

# --- bids-validator (npm dependency bundled in the desktop app) ---
if [[ "$platform" == "windows" ]]; then
    validator_bin="${APP_DIR}/node_modules/bids-validator/bin/bids-validator"
else
    validator_bin="${APP_DIR}/node_modules/bids-validator/bin/bids-validator"
fi
require_file "bids-validator" "$validator_bin"
# bids-validator is a Node CLI; electron runs it via process.execPath in production.
run_check "bids-validator --version" '^[0-9]+\.[0-9]' node "$validator_bin" --version

echo "smoke-test: all checks passed"
