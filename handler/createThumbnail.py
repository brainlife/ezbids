#!/usr/bin/env python3
"""
Created on Wed Feb 17 08:32:55 2021

Deface anatomical image(s)

@author: dlevitas
"""

import os, sys
import nibabel as nib
import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.style.use('dark_background')
from math import floor
from PIL import Image

os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'

print("loading image to create thumbnail "+sys.argv[1])
image = nib.load(sys.argv[1])
output_image = sys.argv[2]

object_img_array = image.dataobj[:]

slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]

fig, axes = plt.subplots(1, 3, figsize=(9, 3))
for index, slices in enumerate([slice_x, slice_y, slice_z]):
    axes[index].imshow(slices.T, cmap="gray", origin="lower", aspect="auto")
    axes[index].axis("off")
plt.tight_layout(pad=0, w_pad=0, h_pad=0)

fig.canvas.draw()

w,h = fig.canvas.get_width_height()
buf = np.fromstring(fig.canvas.tostring_argb(), dtype=np.uint8)
buf.shape = (w,h,4)

buf = np.roll(buf,3,axis=2)

w,h,d = buf.shape
png = Image.frombytes("RGBA", (w,h), buf.tostring())
png.save(output_image)


