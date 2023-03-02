#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 09:01:55 2022

Create thumbnail for 3D nifti files and movie for 4D nifti files

@author: dlevitas
"""

import os
import sys
import json
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

os.environ[ 'MPLCONFIGDIR' ] = os.getcwd() + "/configs/"


###### functions #########
def create_movie_thumbnails(nifti_file, output_dir, object_img_array, v):
    """
    Generates a PNG for each volume of a 4D acquisition.

    Parameters
    ----------

    nifti_file : string
        path of 4D nifti file.

    output_dir: string
        path of folder where movie PNG files will be stored

    object_img_array: numpy.darray
        result of nib.load(nifti_file).dataobj

    v: int
        volume index
    """

    max_len = len(str(object_img_array.shape[3]))

    if not os.path.isfile("{}/{}.png".format(output_dir, v)):

        slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :, v]
        slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :, v]
        slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2), v]

        fig, axes = plt.subplots(1, 3, figsize=(9, 3))
        for index, slices in enumerate([slice_x, slice_y, slice_z]):
            axes[index].imshow(slices.T, cmap="gray", origin="lower", aspect="auto")
            axes[index].axis("off")
        plt.tight_layout(pad=0, w_pad=0, h_pad=0)
        plt.close()

        fig.canvas.draw()

        w,h = fig.canvas.get_width_height()
        buf = np.frombuffer(fig.canvas.tostring_argb(), dtype=np.uint8)
        buf.shape = (w,h,4)

        buf = np.roll(buf,3,axis=2)

        w,h,d = buf.shape
        png = Image.frombytes("RGBA", (w,h), buf.tobytes())

        # Sort files in Linux-friendly way (i.e. zero pad)
        v_len = len(str(v))
        new_v = "0"*(max_len - v_len) + str(v)

        png.save("{}/{}.png".format(output_dir,new_v))


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

    slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
    slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
    slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]

    fig, axes = plt.subplots(1, 3, figsize=(9, 3))
    for index, slices in enumerate([slice_x, slice_y, slice_z]):
        axes[index].imshow(slices.T, cmap="gray", origin="lower", aspect="auto")
        axes[index].axis("off")
    plt.tight_layout(pad=0, w_pad=0, h_pad=0)
    plt.close()

    fig.canvas.draw()

    w,h = fig.canvas.get_width_height()
    buf = np.frombuffer(fig.canvas.tostring_argb(), dtype=np.uint8)
    buf.shape = (w,h,4)

    buf = np.roll(buf,3,axis=2)

    w,h,d = buf.shape
    png = Image.frombytes("RGBA", (w,h), buf.tobytes())
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
    pngPaths = []
    bvals = [floor(float(x)) for x in pd.read_csv(bval_file, delim_whitespace=True).columns.tolist()]
    modified_bvals = [round(x, -2) for x in bvals]
    unique_bvals = np.unique(modified_bvals).tolist()

    for bval in unique_bvals:
        object_img_array = image.dataobj[..., modified_bvals.index(bval)]

        slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
        slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
        slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]

        fig, axes = plt.subplots(1, 3, figsize=(9, 3))
        for index, slices in enumerate([slice_x, slice_y, slice_z]):
            axes[index].imshow(slices.T, cmap="gray", origin="lower", aspect="auto")
            axes[index].axis("off")
        plt.tight_layout(pad=0, w_pad=0, h_pad=0)
        plt.close()

        fig.canvas.draw()

        w,h = fig.canvas.get_width_height()
        buf = np.frombuffer(fig.canvas.tostring_argb(), dtype=np.uint8)
        buf.shape = (w,h,4)

        buf = np.roll(buf,3,axis=2)

        w,h,d = buf.shape
        png = Image.frombytes("RGBA", (w,h), buf.tobytes())
        png.save("{}_shell-{}.png".format(output_file, bval))


# Begin:
data_dir = sys.argv[1]
json_file = sys.argv[2]
os.chdir(data_dir)

json_list = pd.read_csv("list", header=None, sep="\n").to_numpy().flatten().tolist()

nifti_file = json_file.split(".json")[0] + ".nii.gz"

if not os.path.isfile("{}/{}".format(data_dir, nifti_file)): # no corresponding nifti, so don't process
    nifti_file = "N/A"
else:
    output_dir = nifti_file.split(".nii.gz")[0]
    image = nib.load(nifti_file)
    object_img_array = image.dataobj[:]


    bval_file = json_file.split(".json")[0].split("./")[-1] + ".bval"
    if not os.path.isfile("{}/{}".format(data_dir, bval_file)):
        bval_file = "N/A"
    else:
        bvals = [x.split(" ") for x in pd.read_csv(bval_file).columns.tolist()][0]
        bvals = [floor(float(x)) for x in bvals if type(x) != str]
        
        if len(bvals) <= 1: # just b0, so unhelpful
            bval_file = "N/A"


    # # create movie of each volume in 4D acquisition
    # if image.ndim == 4 and nifti_file != "N/A": # 4D
    #     print("")
    #     print("Creating movie of all volumes for {}".format(nifti_file))
    #     print("")
    #     max_len = len(str(object_img_array.shape[3]))

    #     if not os.path.isdir(output_dir):
    #         os.mkdir(output_dir)

    #     for v in range(object_img_array.shape[3]):
    #         create_movie_thumbnails(nifti_file, output_dir, object_img_array, v)
    #     # Parallel(n_jobs=6)(delayed(create_movie)(nifti_file=nifti_file, output_dir=output_dir, object_img_array=object_img_array, v=v) for v in range(object_img_array.shape[3]))

    #     # Combine volume PNGs into movie
    #     os.system("ffmpeg -framerate 30 -pattern_type glob -i {}/'*.png' {}_movie.mp4".format(output_dir, output_dir))


    # Some acquisitions may not have a proper dtype, strongly indicating a non-MRI acquisition
    if image.get_data_dtype() == [('R', 'u1'), ('G', 'u1'), ('B', 'u1')]:
        print("{} doesn't appear to be an MRI acquisition, has dtype value of {}".format(nifti_file, [('R', 'u1'), ('G', 'u1'), ('B', 'u1')]))
    else:
        # create thumbnail
        if nifti_file != "N/A":
            print("")
            print("Creating thumbnail for {}".format(nifti_file))
            print("")
            create_thumbnail(nifti_file, image)

        # create thumbnail of each DWI's unique shell
        if bval_file != "N/A":
            print("")
            print("Creating thumbnail(s) for each DWI shell in {}".format(nifti_file))
            print("")
            create_DWIshell_thumbnails(nifti_file, image, bval_file)

    # remove the folder containing the PNGs for movie generation; don't need them anymore
    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)













