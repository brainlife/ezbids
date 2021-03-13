#!/usr/bin/env python3
"""
Created on Wed Feb 17 08:32:55 2021

Deface anatomical image(s)

@author: dlevitas
"""

import os, sys
import nibabel as nib

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt

plt.style.use('dark_background')
from math import floor

os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'

print("loading image to create thumbnail "+sys.argv[1])
image = nib.load(sys.argv[1])
output_image = sys.argv[2]

object_img_array = image.dataobj[:]

slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]

fig, axes = plt.subplots(1,3, figsize=(9,3))
for i, slice in enumerate([slice_x, slice_y, slice_z]):
    print("creating thumbnail "+str(i))
    axes[i].imshow(slice.T, cmap="gray", origin="lower", aspect='auto')
    axes[i].axis('off')
plt.subplots_adjust(wspace=0, hspace=0)
plt.savefig(output_image, bbox_inches='tight')

