#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 09:01:55 2022

Create thumbnail for 3D nifti files and movie for 4D nifti files

@author: dlevitas
"""

import os
import sys
import shutil
import numpy as np
import pandas as pd
import nibabel as nib
from PIL import Image
from math import floor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.style.use('dark_background')

os.environ['MPLCONFIGDIR'] = os.getcwd() + "/configs/"


# Functions


def create_thumbnail(nifti_file, image):
    """
    Generates a PNG for the 2nd volume of a 4D acquisition.

    Parameters
    ----------

    nifti_file : string
        path of 4D nifti file.

    image: nibabel.nifti1.Nifti1Image
        result of nib.load(nifti_file)
    """

    if image.ndim == 4:
        object_img_array = image.dataobj[..., 1]
    else:
        object_img_array = image.dataobj[:]

    output_file = nifti_file.split(".nii.gz")[0] + ".png"

    slice_x = object_img_array[floor(object_img_array.shape[0] / 2), :, :]
    slice_y = object_img_array[:, floor(object_img_array.shape[1] / 2), :]
    slice_z = object_img_array[:, :, floor(object_img_array.shape[2] / 2)]

    fig, axes = plt.subplots(1, 3, figsize=(9, 3))
    for index, slices in enumerate([slice_x, slice_y, slice_z]):
        axes[index].imshow(slices.T, cmap="gray", origin="lower", aspect="auto")
        axes[index].axis("off")
    plt.tight_layout(pad=0, w_pad=0, h_pad=0)
    plt.close()

    fig.canvas.draw()

    w, h = fig.canvas.get_width_height()
    buf = np.frombuffer(fig.canvas.tostring_argb(), dtype=np.uint8)
    buf.shape = (w, h, 4)

    buf = np.roll(buf, 3, axis=2)

    w, h, d = buf.shape
    png = Image.frombytes("RGBA", (w, h), buf.tobytes())
    png.save(output_file)


def create_DWIshell_thumbnails(nifti_file, image, bval_file):
    """
    Generates a PNG for each unique DWI acquisition shell.

    Parameters
    ----------

    nifti_file : string
        path of 4D nifti file.

    image: nibabel.nifti1.Nifti1Image
        result of nib.load(nifti_file)

    bval_file: string
        path of corresponding nifti file's bval
    """

    output_file = nifti_file.split(".nii.gz")[0] + ".png"
    bvals = [floor(float(x)) for x in pd.read_csv(bval_file, delim_whitespace=True).columns.tolist()]
    modified_bvals = [round(x, -2) for x in bvals]
    unique_bvals = np.unique(modified_bvals).tolist()

    for bval in unique_bvals:
        object_img_array = image.dataobj[..., modified_bvals.index(bval)]

        slice_x = object_img_array[floor(object_img_array.shape[0] / 2), :, :]
        slice_y = object_img_array[:, floor(object_img_array.shape[1] / 2), :]
        slice_z = object_img_array[:, :, floor(object_img_array.shape[2] / 2)]

        fig, axes = plt.subplots(1, 3, figsize=(9, 3))
        for index, slices in enumerate([slice_x, slice_y, slice_z]):
            axes[index].imshow(slices.T, cmap="gray", origin="lower", aspect="auto")
            axes[index].axis("off")
        plt.tight_layout(pad=0, w_pad=0, h_pad=0)
        plt.close()

        fig.canvas.draw()

        w, h = fig.canvas.get_width_height()
        buf = np.frombuffer(fig.canvas.tostring_argb(), dtype=np.uint8)
        buf.shape = (w, h, 4)

        buf = np.roll(buf, 3, axis=2)

        w, h, d = buf.shape
        png = Image.frombytes("RGBA", (w, h), buf.tobytes())
        png.save("{}_shell-{}.png".format(output_file, bval))


# Begin:
data_dir = sys.argv[1]
json_file = sys.argv[2]
os.chdir(data_dir)

json_list = pd.read_csv("list", header=None, lineterminator="\n").to_numpy().flatten().tolist()

nifti_file = json_file.split(".json")[0] + ".nii.gz"
print("")
print(nifti_file)
print("")

if not os.path.isfile("{}/{}".format(data_dir, nifti_file)):  # no corresponding nifti, so don't process
    print("{} does not have a corresponding NIfTI file, cannot process".format(json_file))
else:
    output_dir = nifti_file.split(".nii.gz")[0]
    image = nib.load(nifti_file)

    if len([x for x in image.shape if x < 0]):  # image has negative dimension(s), cannot process
        print("{} has negative dimension(s), cannot process".format(nifti_file))
    else:
        # if image.get_data_dtype() == [('R', 'u1'), ('G', 'u1'), ('B', 'u1')]:
        if image.get_data_dtype() not in ["<i2", "<u2", "<f4", "int16", "uint16"]:
            # Likely non-imaging acquisition. Example: "facMapReg" sequences in NYU_Shanghai dataset
            print(
                f"{nifti_file} doesn't appear to be an"
                "imaging acquisition and therefore will "
                "not be converted to BIDS. Please modify "
                "if incorrect."
            )
        else:
            # object_img_array = image.dataobj[:]

            bval_file = json_file.split(".json")[0].split("./")[-1] + ".bval"
            if not os.path.isfile("{}/{}".format(data_dir, bval_file)):
                bval_file = "N/A"
            else:
                bvals = [x.split(" ") for x in pd.read_csv(bval_file).columns.tolist()][0]
                bvals = [floor(float(x)) for x in bvals if not isinstance(x, str)]

                if len(bvals) <= 1:  # just b0, so unhelpful
                    bval_file = "N/A"

            # Create thumbnail
            if nifti_file != "N/A":
                print("")
                print("Creating thumbnail for {}".format(nifti_file))
                print("")
                create_thumbnail(nifti_file, image)

            # Create thumbnail of each DWI's unique shell
            if bval_file != "N/A":
                print("")
                print("Creating thumbnail(s) for each DWI shell in {}".format(nifti_file))
                print("")
                create_DWIshell_thumbnails(nifti_file, image, bval_file)

        # Remove the folder containing the PNGs for movie generation; don't need them anymore
        if os.path.isdir(output_dir):
            shutil.rmtree(output_dir)
