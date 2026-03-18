#!/usr/bin/env bash
#
# Fetches ezbids-binaries release assets for a given platform and extracts them
# into handler/bin with one subfolder per library.
#
# You can fetch any platform from any host (e.g. on a Mac, run with win32 to
# download and package Windows binaries for later use or distribution).
#
# Usage:
#   ./fetch-binaries.sh <platform> [arch]
#
# Examples:
#   ./fetch-binaries.sh darwin
#   ./fetch-binaries.sh darwin amd64
#   ./fetch-binaries.sh linux arm64
#   ./fetch-binaries.sh win32          # e.g. fetch Windows binaries from Mac
#
# Platform: darwin | linux | win32
# Arch (optional): amd64 | arm64 (default: amd64 on x64, arm64 on arm64)
#
# Requires: curl, jq, tar, unzip
# For private repos, set GITHUB_TOKEN in the environment.

set -e

REPO="brainlife/ezbids-binaries"
RELEASE_TAG="v0.0.4"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_BASE="$SCRIPT_DIR/handler/bin"

usage() {
    echo "Usage: $0 <platform> [arch]" >&2
    echo "  platform: darwin | linux | win32 (target platform; can fetch any platform from any host)" >&2
    echo "  arch:     amd64 | arm64 (default: amd64 for x64, arm64 for arm64)" >&2
    exit 1
}

to_lower() {
    echo "$1" | tr '[:upper:]' '[:lower:]'
}

# Default arch from current machine (only used when arch not passed)
default_arch() {
    case "$(uname -m)" in
        arm64|aarch64) echo "arm64" ;;
        *) echo "amd64" ;;
    esac
}

platform="$(to_lower "${1:-}")"
arch="$(to_lower "${2:-$(default_arch)}")"

if [[ -z "$platform" ]] || [[ ! "$platform" =~ ^(darwin|linux|win32)$ ]]; then
    echo "Error: first argument must be darwin, linux, or win32" >&2
    usage
fi
if [[ ! "$arch" =~ ^(amd64|arm64)$ ]]; then
    echo "Error: arch must be amd64 or arm64" >&2
    usage
fi

# Asset names in the release use "windows", not "win32"
platform_filter="$platform"
[[ "$platform" == "win32" ]] && platform_filter="windows"
echo "Fetching binaries for ${platform}-${arch} and saving into ${BIN_BASE}"

API_URL="https://api.github.com/repos/${REPO}/releases/tags/${RELEASE_TAG}"
CURL_ARGS=(-sL -H "Accept: application/vnd.github+json")
[[ -n "${GITHUB_TOKEN:-}" ]] && CURL_ARGS+=(-H "Authorization: Bearer ${GITHUB_TOKEN}")

release_json=$(curl "${CURL_ARGS[@]}" "$API_URL") || true
if [[ -z "$release_json" ]] || echo "$release_json" | jq -e '.message == "Not Found"' >/dev/null 2>&1; then
    echo "Release ${RELEASE_TAG} not found. Repo may be private - set GITHUB_TOKEN if needed." >&2
    exit 1
fi

# Filter assets whose name contains platform and arch (case-insensitive)
matching=$(
    echo "$release_json" | jq -r --arg p "$platform_filter" --arg a "$arch" '
        .assets[] | select(.name | ascii_downcase | contains($p)) | select(.name | ascii_downcase | contains($a)) | "\(.name)\t\(.url)"
    '
)

if [[ -z "$matching" ]]; then
    echo "No assets found for ${platform}-${arch}. Available assets:" >&2
    echo "$release_json" | jq -r '.assets[].name' | sed 's/^/  - /' >&2
    exit 1
fi

# Derive library name from asset filename:
#   7z-darwin-arm64, 7z-windows-amd64.exe, dcm2niix-linux-amd64 -> 7z, dcm2niix
#   python-runtime-darwin-arm64.tar.gz -> python-runtime
library_from_name() {
    local name="$1"

    local suffix="-${platform_filter}-${arch}"
    local base="$name"
    base="${base%.tar.gz}"
    base="${base%.zip}"
    base="${base%.tgz}"
    base="${base%.exe}"
    base="${base%.dll}"
    if [[ "$base" == *"$suffix" ]]; then
        echo "${base%"$suffix"}"
    else
        echo ""
    fi
}

extract_archive() {
    local archive="$1"
    local out_dir="$2"
    mkdir -p "$out_dir"
    echo "Extracting $archive to $out_dir"
    case "$(to_lower "$archive")" in
        *.tar.gz|*.tgz) tar -xzf "$archive" -C "$out_dir" ;;
        *.zip)           unzip -o -q "$archive" -d "$out_dir" ;;
        *)               echo "Unsupported archive format: $archive" >&2; exit 1 ;;
    esac
}

is_archive() {
    case "$(echo "$1")" in
        *.tar.gz|*.tgz|*.zip) return 0 ;;
        *) return 1 ;;
    esac
}

DOWNLOAD_ARGS=(-sL -H "Accept: application/octet-stream")
[[ -n "${GITHUB_TOKEN:-}" ]] && DOWNLOAD_ARGS+=(-H "Authorization: Bearer ${GITHUB_TOKEN}")

while IFS=$'\t' read -r name url; do
    [[ -z "$name" ]] && continue
    lib=$(library_from_name "$name")
    [[ -z "$lib" ]] && continue
    subdir="$BIN_BASE/$lib"
    mkdir -p "$subdir"
    echo "Created Directory: $subdir"
    if is_archive "$name"; then
        echo "Expanding $name"
        tmpfile="$subdir/tmp_download/$name"
        mkdir -p "$(dirname "$tmpfile")"
        echo "fetching $url"
        curl "${DOWNLOAD_ARGS[@]}" -o "$tmpfile" "$url"
        extract_archive "$tmpfile" "$subdir"
        rm -rf "$(dirname "$tmpfile")"
    else
        echo "Downloading $name"
        curl "${DOWNLOAD_ARGS[@]}" -o "$subdir/$name" "$url"
    fi
done <<< "$matching"

echo "Done."
