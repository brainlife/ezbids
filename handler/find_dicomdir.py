#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from pydicom import dcmread
# if pet2bids is installed we use it wherever PET data live
try:
    # import pypet2bids
    pet2bidsInstalled = True
    from pypet2bids import is_pet
except (ImportError, ModuleNotFoundError):
    pet2bidsInstalled = False
    print("pet2bids is not installed, using dcm2niix on PET directories instead")
    sys.exit(1)


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
                if f.lower().endswith(tuple(['.dcm', '.ima', '.img', '_'])) or f.lower().startswith('mr.'):
                    # Are these MRI or PET DICOMS

                    # MRI
                    try:
                        read_file = dcmread(f"{full_path}/{f}")
                        if read_file.Modality == "MR":
                            mri_dcm_dirs_list.append(full_path)
                            break
                        elif read_file.Modality == "PT":
                            pet_dcm_dirs_list.append(full_path)
                            break
                        else:
                            pass
                    except:
                        pass

                elif f.lower().endswith('.v'):
                    # PET ECAT-formatted raw data
                    pet_ecat_files_list.append(f'{full_path}/{f}')
                    break
                else:
                    # any nifti files?
                    niftis = [x for x in os.listdir(full_path) if x.endswith('nii') or x.endswith('nii.gz')]
                    if not len(niftis):
                        pet_folders = [str(folder) for folder in is_pet.pet_folder(Path(full_path).resolve())]
                        if len(pet_folders):
                            pet_dcm_dirs_list.append(full_path)
                            break

    if not hasDicoms:
        for x in sorted(os.listdir(dir)):
            full_path = os.path.join(dir, x)
            if os.path.isdir(full_path):
                find_dicomdir(full_path)


# change to input directory
root = sys.argv[1]
os.chdir(root)

pet_ecat_files_list = []
pet_dcm_dirs_list = []
mri_dcm_dirs_list = []

find_dicomdir('.')

# Save the MRI and PET lists (if they exist) to separate files
file = open(f'{root}/dcm2niix.list', 'w')
if len(mri_dcm_dirs_list):
    for dcm in mri_dcm_dirs_list:
        file.write(dcm + "\n")
file.close()

if len(pet_dcm_dirs_list):
    file = open(f'{root}/pet2bids_dcm.list', 'w')
    for dcm in pet_dcm_dirs_list:
        file.write(dcm + "\n")
    file.close()

if len(pet_ecat_files_list):
    file = open(f'{root}/pet2bids_ecat.list', 'w')
    for ecat in pet_ecat_files_list:
        file.write(ecat + "\n")
    file.close()
