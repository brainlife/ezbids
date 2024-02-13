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

    # MRI
    for x in sorted(os.listdir(dir)):
        full_path = os.path.join(dir, x)
        if os.path.isdir(full_path):
            for f in sorted(os.listdir(full_path)):
                try:
                    read_file = dcmread(f"{full_path}/{f}")
                    if read_file.Modality == "MR":
                        mri_dcm_dirs_list.append(full_path)
                        hasDicoms = True
                        break
                except:
                    # Doesn't appear to be DICOM data, so skip
                    # pass
                    break

    # Complete search
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


# PET
pet_folders = [str(folder) for folder in is_pet.pet_folder(Path(root).resolve())]

# parse output of ispet into list of directories
pet_folders = [os.path.relpath(x, root) for x in pet_folders if x != '']

# format from expanded paths to relative paths to match output of find_dicomdir.py
pet_folders = [os.path.join('.', x) for x in pet_folders]
if pet_folders:
    for pet_folder in pet_folders:
        print(pet_folders)
        # See if we're dealing ECAT-formatted file(s)
        ecats = [x for x in os.listdir(pet_folder) if x.endswith(tuple(['.v', '.v.gz']))]
        if len(ecats):
            for ecat in ecats:
                if ecat not in pet_ecat_files_list:
                    pet_ecat_files_list.append(f'{pet_folder}/{ecat}')
        # See if we're dealing with DICOM files
        dcms = [
            x for x in os.listdir(pet_folder)
            if not x.endswith(tuple(['.nii', '.nii.gz', '.v', '.v.gz', '.json', '.tsv']))
        ]
        if len(dcms) and pet_folder not in pet_dcm_dirs_list:
            pet_dcm_dirs_list.append(pet_folder)

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
