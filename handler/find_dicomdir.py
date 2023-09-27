#!/usr/bin/env python3

import os
import sys
import pydicom


def find_dicomdir(dir):
    """
    Finds all directories that contain DICOM (or other) raw imaging data.
    If dcm2niix output (NIfTI, JSON files) uploaded instead, ezBIDS has separate process for detecting those files.

    Parameters
    ----------
    dir : string
        root-level directory of uploaded data
    """

    hasDicoms = False

    for x in sorted(os.listdir(dir)):
        full_path = os.path.join(dir, x)

        if os.path.isdir(full_path):
            for f in sorted(os.listdir(full_path)):
                if (f.lower().endswith(".dcm") or f.lower().endswith(".ima") or f.lower().endswith(".img")
                        or f.lower().startswith("mr.")):
                    hasDicoms = True
                    print(full_path)
                    break
                else:
                    # no explicit raw data (e.g., DICOM) extension, check using pydicom
                    try:
                        read_file = pydicom.dcmread(f"{full_path}/{f}")
                        if read_file.Modality == "MR":  # eventually need to expand this to other imaging modalities
                            hasDicoms = True
                            print(full_path)
                            break
                        else:
                            # Not MRI imaging modality, ignore for now
                            pass
                    except:
                        # Doesn't appear to be DICOM (or other raw imaging) data
                        pass

    if not hasDicoms:
        for x in sorted(os.listdir(dir)):
            full_path = os.path.join(dir, x)
            if os.path.isdir(full_path):
                find_dicomdir(full_path)


os.chdir(sys.argv[1])

find_dicomdir('.')
