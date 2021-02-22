#!/usr/bin/env python3
"""
Created on Wed Feb 17 08:32:55 2021

Deface anatomical images

@author: dlevitas
"""

import os, sys, json, warnings
import nibabel as nib
import matplotlib.pyplot as plt
from math import floor

warnings.filterwarnings("ignore")
os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'

root = sys.argv[1]

finalized_json = open('{}/finalized.json'.format(root))
finalized_json = json.load(finalized_json, strict=False)

if finalized_json['deface'] == True:
    for i in range(len(finalized_json['objects'])):
        if 'anat' in finalized_json['objects'][i]['_type'] and finalized_json['objects'][i]['include'] == True:
            # Skull strip and deface
            anat_path = [x for x in finalized_json['objects'][i]['paths'] if '.nii' in x][0]
            anat_path = root + '/' + anat_path.split('./')[-1]
            print('Performing defacing on {}'.format(anat_path), file = sys.stdout)
            os.system('runROBEX.sh {} {} 1'.format(anat_path, anat_path.split('.nii.gz')[0] + '_mask.nii.gz'))
            os.system('quickshear {} {} {}'.format(anat_path, anat_path.split('.nii.gz')[0] + '_mask.nii.gz', anat_path))
            print('Defaced anatomical file is {}'.format(anat_path), file = sys.stdout)
            
            # Create PNG file of defaced image
            image = nib.load(anat_path)
            object_img_array = image.dataobj[:]
            
            slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
            slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
            slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]

            fig, axes = plt.subplots(1,3, figsize=(9,3))
            for i, slice in enumerate([slice_x, slice_y, slice_z]):
                axes[i].imshow(slice.T, cmap="gray", origin="lower", aspect='auto')
                axes[i].axis('off')
            plt.subplots_adjust(wspace=0, hspace=0)
            plt.savefig('{}.png'.format(anat_path.split('.nii.gz')[0]), bbox_inches='tight')
            print('Defaced anat thumbnail: {}.png'.format(anat_path.split('.nii.gz')[0]), file = sys.stdout)

