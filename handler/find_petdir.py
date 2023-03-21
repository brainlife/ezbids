#!/usr/bin/env python3

import os
import sys
import subprocess

# if pet2bids is installed we use it wherever PET dicoms live
try:
    import pypet2bids
    pet2bidsInstalled = True
except (ImportError, ModuleNotFoundError):
    pet2bidsInstalled = False
    print(f"pet2bids is not installed, using dcm2niix on PET directories instead")
    sys.exit(1)

# change to input directory
os.chdir(sys.argv[1])
pet_folders_subprocess = subprocess.run(['ispet', '.'], capture_output=True, text=True)

# parse output of ispet into list of directories
pet_folders = [os.path.relpath(x, sys.argv[1]) for x in pet_folders_subprocess.stdout.splitlines() if x != '']

# format from expanded paths to relative paths to match output of find_dicomdir.py
pet_folders = [os.path.join('.', x) for x in pet_folders]

# if folders print them out
if pet_folders:
    for pet_folder in pet_folders:
        print(pet_folder)

sys.exit(pet_folders_subprocess.returncode)