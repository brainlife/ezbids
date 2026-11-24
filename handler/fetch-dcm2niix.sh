#!/usr/bin/env bash
#
# Downloads the pinned dcm2niix (handler/dcm2niix.env) from the official rordenlab/dcm2niix release,
# checks the asset's sha256, installs it as <out_dir>/dcm2niix-<platform>-<arch>[.exe] (plus the DLLs that
# come with the Windows build) and, when the binary can run here, fails unless `dcm2niix -v` prints the
# pinned version. Used by handler/Dockerfile (linux amd64) and by fetch-binaries.sh (desktop app).
#
#   handler/fetch-dcm2niix.sh <platform> <arch> <out_dir>      platform: linux | darwin | windows; arch: amd64 | arm64
#
# Requires: curl, unzip, sha256sum or shasum.

set -euo pipefail

platform="${1:-}"
arch="${2:-}"
out="${3:-}"
if [[ -z "$platform" || -z "$arch" || -z "$out" ]]; then
    echo "usage: $0 <linux|darwin|windows> <amd64|arm64> <out_dir>" >&2
    exit 1
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=dcm2niix.env
. "${DCM2NIIX_ENV:-$HERE/dcm2niix.env}"

asset_var="DCM2NIIX_ASSET_${platform}_${arch}"
sha_var="DCM2NIIX_SHA256_${platform}_${arch}"
asset="${!asset_var:-}"
want_sha="${!sha_var:-}"
if [[ -z "$asset" || -z "$want_sha" ]]; then
    echo "dcm2niix ${DCM2NIIX_VERSION}: the official release has no asset for ${platform}-${arch}" >&2
    exit 1
fi

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
url="https://github.com/rordenlab/dcm2niix/releases/download/${DCM2NIIX_VERSION}/${asset}"
echo "dcm2niix ${DCM2NIIX_VERSION} for ${platform}-${arch}: ${url}"
curl -fsSL -o "$tmp/$asset" "$url"
got_sha="$(sha256 "$tmp/$asset")"
if [[ "$got_sha" != "$want_sha" ]]; then
    echo "dcm2niix: sha256 mismatch for ${asset}: got ${got_sha}, want ${want_sha}" >&2
    exit 1
fi
unzip -q -o "$tmp/$asset" -d "$tmp/x"

mkdir -p "$out"
exe=""
[[ "$platform" == windows ]] && exe=".exe"
dest="$out/dcm2niix-${platform}-${arch}${exe}"
rm -f "$dest"
cp "$tmp/x/dcm2niix${exe}" "$dest"
chmod u+rwx,go+rx "$dest"
if [[ "$platform" == windows ]]; then
    # dcm2niix.exe loads these MSVC runtime DLLs from its own folder
    find "$tmp/x" -maxdepth 1 -iname '*.dll' -exec cp {} "$out/" \;
fi

host_platform=linux
case "$(uname -s)" in Darwin) host_platform=darwin ;; MINGW* | MSYS* | CYGWIN*) host_platform=windows ;; esac
if [[ "$platform" == "$host_platform" ]]; then
    printed="$("$dest" -v 2>&1 || true)"
    if [[ "$printed" != *"${DCM2NIIX_VERSION}"* ]]; then
        echo "dcm2niix: $dest -v does not print ${DCM2NIIX_VERSION}: ${printed}" >&2
        exit 1
    fi
    echo "ok: $dest prints ${DCM2NIIX_VERSION}"
else
    echo "note: ${platform} binary not run on this ${host_platform} host (its version is checked where it is built)"
fi
