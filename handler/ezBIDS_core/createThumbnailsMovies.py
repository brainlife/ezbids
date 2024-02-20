#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 09:01:55 2022

Create thumbnail for 3D nifti files and movie for 4D nifti files

@author: dlevitas
"""
import matplotlib
import matplotlib.pyplot as plt
import os
import sys
import shutil
import numpy as np
import pandas as pd
import nibabel as nib
from PIL import Image
from math import floor
from pathlib import Path
matplotlib.use('Agg')
plt.style.use('dark_background')

os.environ['MPLCONFIGDIR'] = os.getcwd() + "/configs/"

# Functions


def create_MEG_thumbnail(meg_img_file):
    """
    Generate a simple visualization of the MEG data.
    """
    import mne.viz

    ext = Path(meg_img_file).suffix
    fname = meg_img_file
    raw = mne.io.read_raw(fname, verbose=0)
    mne.viz.set_browser_backend('matplotlib', verbose=None)

    png_types = ["channels", "psd"]
    for png_type in png_types:
        output_file = fname.split(ext)[0] + f"_{png_type}.png"

        if png_type == "channels":
            fig = raw.plot()
        elif png_type == "psd":
            fig = raw.compute_psd().plot()

        fig.savefig(output_file, bbox_inches='tight')


def create_thumbnail(img_file, image):
    """
    Generates a PNG screenshot of a NIfTI data file. If data is 4D,
    the 2nd volume is used.

    Parameters
    ----------

    img_file : string
        path of 4D NIfTI file.

    image: nibabel.nifti1.Nifti1Image
        result of nib.load(img_file).
    """

    if image.ndim == 4:
        try:
            object_img_array = image.dataobj[..., 1]
        except:
            # weird issue where an improper singleton 4D dimension is added for otherwise 3D data (see with PET)
            image = nib.funcs.squeeze_image(image)
            object_img_array = image.dataobj[:]
            image.to_filename(img_file)
    else:
        object_img_array = image.dataobj[:]

    output_file = img_file.split(".nii.gz")[0] + ".png"

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


def create_DWIshell_thumbnails(img_file, image, bval_file):
    """
    Generates a PNG for each unique DWI acquisition shell.

    Parameters
    ----------

    img_file : string
        path of 4D NIfTI file.

    image: nibabel.nifti1.Nifti1Image
        result of nib.load(img_file).

    bval_file: string
        path of corresponding NIfTI file's bval.
    """

    output_file = img_file.split(".nii.gz")[0] + ".png"
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
        png.save(f"{output_file}_shell-{bval}.png")


# Begin:
data_dir = sys.argv[1]
img_file = sys.argv[2]
MEG_extensions = [".ds", ".fif", ".sqd", ".con", ".raw", ".ave", ".mrk", ".kdf", ".mhd", ".trg", ".chn", ".dat"]
os.chdir(data_dir)

if img_file.endswith(tuple(MEG_extensions)):
    print("")
    print(f"Creating thumbnails for {img_file}")
    print("")
    create_MEG_thumbnail(img_file)
else:
    if not img_file.endswith('blood.json'):
        output_dir = img_file.split(".nii.gz")[0]
        image = nib.load(img_file)

        if len([x for x in image.shape if x < 0]):  # image has negative dimension(s), cannot process
            print(f"{img_file} has negative dimension(s), cannot process")
        else:
            # if image.get_data_dtype() == [('R', 'u1'), ('G', 'u1'), ('B', 'u1')]:
            if image.get_data_dtype() not in ["<i2", "<u2", "<f4", "int16", "uint16"]:
                # Likely non-imaging acquisition. Example: "facMapReg" sequences in NYU_Shanghai dataset
                print(
                    f"{img_file} doesn't appear to be an "
                    "imaging acquisition and therefore will "
                    "not be converted to BIDS. Please modify "
                    "if incorrect."
                )
            else:
                # object_img_array = image.dataobj[:]

                bval_file = img_file.split(".nii.gz")[0].split("./")[-1] + ".bval"
                if not os.path.isfile(f"{data_dir}/{bval_file}"):
                    bval_file = "n/a"
                else:
                    bvals = [x.split(" ") for x in pd.read_csv(bval_file).columns.tolist()][0]
                    bvals = [floor(float(x)) for x in bvals if not isinstance(x, str)]

                    if len(bvals) <= 1:  # just b0, so unhelpful
                        bval_file = "n/a"

                # Create thumbnail
                if img_file != "n/a":
                    print("")
                    print(f"Creating thumbnail for {img_file}")
                    print("")
                    create_thumbnail(img_file, image)

                # Create thumbnail of each DWI's unique shell
                if bval_file != "n/a":
                    print("")
                    print(f"Creating thumbnail(s) for each DWI shell in {img_file}")
                    print("")
                    create_DWIshell_thumbnails(img_file, image, bval_file)

            # Remove the folder containing the PNGs for movie generation; don't need them anymore
            if os.path.isdir(output_dir):
                shutil.rmtree(output_dir)
