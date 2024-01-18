#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 25 13:55:10 2022

update ezBIDS_core.json with pngPaths

@author: dlevitas
"""

import os
import sys
import json
import pandas as pd
from pathlib import Path
from natsort import natsorted

# Begin:
DATA_DIR = sys.argv[1]
os.chdir(DATA_DIR)

json_list = pd.read_csv("list", header=None, lineterminator="\n").to_numpy().flatten().tolist()
MEG_extensions = [".ds", ".fif", ".sqd", ".con", ".raw", ".ave", ".mrk", ".kdf", ".mhd", ".trg", ".chn", ".dat"]

# place paths to image thumbnails in ezBIDS_core.json
with open("ezBIDS_core.json", "r") as ezBIDS_json:
    ezBIDS = json.load(ezBIDS_json)

for json_file in json_list:
    if any(x in json_file for x in MEG_extensions):
        nifti_file = json_file
    else:
        nifti_file = json_file.split(".json")[0] + ".nii.gz"

    if os.path.isfile(f"{DATA_DIR}/{nifti_file}") or os.path.isdir(f"{DATA_DIR}/{nifti_file}"):
        for obj in ezBIDS["objects"]:
            for item in obj["items"]:
                path = item["path"]
                if path == nifti_file:
                    files = [
                        os.path.join(os.path.dirname(nifti_file), x) for x in os.listdir(os.path.dirname(nifti_file))
                    ]

                    if nifti_file.endswith(tuple(MEG_extensions)):
                        ext = Path(nifti_file).suffix
                    else:
                        ext = ".nii.gz"

                    png_files = natsorted([x for x in files if nifti_file.split(ext)[0] in x and ".png" in x])
                    item["pngPaths"] = png_files

with open("ezBIDS_core.json", "w") as ezBIDS_json:
    json.dump(ezBIDS, ezBIDS_json, indent=3)
