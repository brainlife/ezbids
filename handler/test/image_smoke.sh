#!/bin/bash
# Smoke checks for the tools the handler image pins. Run inside the built image:
#   docker build --platform linux/amd64 -t ezbids-handler:local handler/
#   docker run --rm --platform linux/amd64 -v $PWD/handler/test:/t --entrypoint bash ezbids-handler:local /t/image_smoke.sh
set -euo pipefail

fail() { echo "FAIL: $*"; exit 1; }

# dcm2niix is the pinned release, not "latest"
want=v1.0.20261029
got=$(dcm2niix --version 2>&1 || true)
[[ "$got" == *"$want"* ]] || fail "dcm2niix is not $want: $got"
echo "ok: dcm2niix $want"

# FSL's python helpers (tmpnam, used by fslreorient2std) need a python with a working stdlib
fslpython -c 'import math, tempfile' || fail "fslpython cannot import math/tempfile"
echo "ok: fslpython imports math, tempfile"

# fslreorient2std reorients a non-standard image without any error output
work=$(mktemp -d)
cd "$work"
python3 - <<'PY'
import numpy as np, nibabel as nib
# voxel axes stored as (S, R, A): not the MNI152 orientation, so fslreorient2std has to swap them
aff = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]], dtype=float)
nib.save(nib.Nifti1Image(np.arange(4 * 5 * 6, dtype=np.int16).reshape(4, 5, 6), aff), "in.nii.gz")
PY
fslreorient2std in.nii.gz out.nii.gz 2> err.txt || { cat err.txt; fail "fslreorient2std exited non-zero"; }
[ -s err.txt ] && { cat err.txt; fail "fslreorient2std wrote to stderr"; }
[ -e _nii.mat ] && fail "fslreorient2std wrote _nii.mat in the working directory (tmpnam failed)"
python3 - <<'PY' || fail "out.nii.gz is not in the standard orientation"
import nibabel as nib
cin = nib.aff2axcodes(nib.load("in.nii.gz").affine)
cout = nib.aff2axcodes(nib.load("out.nii.gz").affine)
print("in", cin, "out", cout)
assert cout[1:] == ("A", "S") and cout[0] in ("L", "R"), cout
PY
echo "ok: fslreorient2std"
rm -rf "$work"
echo "all handler image checks passed"
