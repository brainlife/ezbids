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

try:
    img_list = natsorted(pd.read_csv("list", header=None, lineterminator="\n").to_numpy().flatten().tolist())
except:
    # Need for [rare] instances where a comma (or other escape character) is in the file path
    img_list = natsorted(pd.read_csv("list", sep=' ', header=None, lineterminator='\n').to_numpy().flatten().tolist())

MEG_extensions = [".ds", ".fif", ".sqd", ".con", ".raw", ".ave", ".mrk", ".kdf", ".mhd", ".trg", ".chn", ".dat"]

# place paths to image thumbnails in ezBIDS_core.json
with open("ezBIDS_core.json", "r") as ezBIDS_json:
    ezBIDS = json.load(ezBIDS_json)


for img_file in img_list:
    if os.path.isfile(f"{DATA_DIR}/{img_file}") or os.path.isdir(f"{DATA_DIR}/{img_file}"):
        for obj in ezBIDS["objects"]:
            for item in obj["items"]:
                path = item["path"]
                if path == img_file:
                    files = [
                        os.path.join(os.path.dirname(img_file), x) for x in os.listdir(os.path.dirname(img_file))
                    ]

                    if img_file.endswith('.nii.gz'):
                        ext = ".nii.gz"
                    else:
                        ext = Path(img_file).suffix

                    png_files = natsorted([x for x in files if img_file.split(ext)[0] + ".png" == x])
                    item["pngPaths"] = png_files

with open("ezBIDS_core.json", "w") as ezBIDS_json:
    json.dump(ezBIDS, ezBIDS_json, indent=3)
