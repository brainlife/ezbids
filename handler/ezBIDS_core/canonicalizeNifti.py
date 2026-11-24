#!/usr/bin/env python3
"""Rewrite a NIfTI in closest canonical orientation (nibabel as_closest_canonical), in place."""
import os
import sys
import tempfile

import nibabel as nib
from nibabel import as_closest_canonical

if __name__ == '__main__':
    path = os.path.abspath(sys.argv[1])
    img = nib.load(path)
    canonical = as_closest_canonical(img)

    directory = os.path.dirname(path) or '.'
    fd, tmp_path = tempfile.mkstemp(
        prefix='.canonicalize_',
        suffix='.tmp.nii.gz',
        dir=directory,
    )
    os.close(fd)
    try:
        nib.save(canonical, tmp_path)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
