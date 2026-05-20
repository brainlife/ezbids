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


def normalize_rel_path(p):
    """Normalize relative paths for cross-platform comparisons."""
    return Path(p).as_posix()

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
    img_path = Path(DATA_DIR) / img_file
    if os.path.isfile(str(img_path)) or os.path.isdir(str(img_path)):
        normalized_img = Path(img_file).as_posix()
        for obj in ezBIDS["objects"]:
            for item in obj["items"]:
                path = item["path"]
                normalized_item_path = Path(path).as_posix()
                if normalized_item_path == normalized_img:
                    item_dir = os.path.dirname(normalized_item_path) or "."
                    item_base = os.path.basename(normalized_item_path)
                    files = [
                        (Path(item_dir) / x).as_posix() for x in os.listdir(item_dir)
                    ]

                    if normalized_item_path.endswith('.nii.gz'):
                        ext = ".nii.gz"
                    else:
                        ext = Path(normalized_item_path).suffix

                    png_target = item_base.split(ext)[0] + ".png"
                    png_files = natsorted([x for x in files if os.path.basename(x) == png_target])
                    item["pngPaths"] = png_files

with open("ezBIDS_core.json", "w") as ezBIDS_json:
    json.dump(ezBIDS, ezBIDS_json, indent=3)
