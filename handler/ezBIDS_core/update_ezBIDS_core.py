#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 25 13:55:10 2022

update ezBIDS_core.json with pngPaths and moviePath

@author: dlevitas
"""

import os
import sys
import json
import pandas as pd
from natsort import natsorted

# Begin:
data_dir = sys.argv[1]
os.chdir(data_dir)

json_list = pd.read_csv("list", header=None, lineterminator="\n").to_numpy().flatten().tolist()

# place paths to thumbnails and movies in ezBIDS_core.json
with open("ezBIDS_core.json", "r") as ezBIDS_json:
    ezBIDS = json.load(ezBIDS_json)

for json_file in json_list:
    nifti_file = json_file.split(".json")[0] + ".nii.gz"

    if os.path.isfile("{}/{}".format(data_dir, nifti_file)):
        for obj in ezBIDS["objects"]:
            for item in obj["items"]:
                path = item["path"]
                if path == nifti_file:
                    files = [os.path.join(os.path.dirname(nifti_file), x) for x in os.listdir(os.path.dirname(nifti_file))]

                    png_files = natsorted([x for x in files if nifti_file.split("nii.gz")[0] in x and ".png" in x])
                    item["pngPaths"] = png_files

                    mp4_file = [x for x in files if nifti_file.split(".nii.gz")[0] in x and ".mp4" in x]
                    if len(mp4_file):
                        item["moviePath"] = mp4_file

with open("ezBIDS_core.json", "w") as ezBIDS_json:
    json.dump(ezBIDS, ezBIDS_json, indent=3)



