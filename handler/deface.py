#!/usr/bin/env python3
"""
Created on Wed Feb 17 08:32:55 2021

Deface anatomical images

@author: dlevitas
"""

import os, sys, json
import nibabel as nib
import matplotlib.pyplot as plt
plt.style.use('dark_background')
from math import floor
from multiprocessing import Pool

os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'

root = sys.argv[1]

if not os.path.isfile('{}/deface.out'.format(root)):
    os.system('touch {}/deface.out'.format(root))
log_file = '{}/deface.out'.format(root)

finalized_json = open('{}/finalized.json'.format(root))
finalized_json = json.load(finalized_json, strict=False)

deface_list = []
if finalized_json['deface'] == True:
    for i in range(len(finalized_json['objects'])):
        if 'anat' in finalized_json['objects'][i]['_type'] and finalized_json['objects'][i]['include'] == True:
            sub = finalized_json['objects'][i]['_entities']['subject']
            ses = finalized_json['objects'][i]['_entities']['session']
            br_type = finalized_json['objects'][i]['_type']
            anat_orig = root + '/' + finalized_json['objects'][i]['paths'][-1].split('./')[-1]
            deface_list.append([anat_orig, br_type, sub, ses])
 
print('deface list is : {}'.format([x[0] for x in deface_list]))

# Functions
def deface(deface_list):
    anat_orig = deface_list[0]
    br_type = deface_list[1]
    sub = deface_list[2]
    ses = deface_list[3]
    anat_mask = anat_orig.split('.nii.gz')[0] + '_mask.nii.gz'
    anat_defaced = anat_orig.split('.nii.gz')[0] + '_defaced.nii.gz'
    # Skull strip and deface
    print('Performing defacing on {}'.format(anat_orig), file = sys.stdout)
    os.system('runROBEX.sh {} {}'.format(anat_orig, anat_mask))
    os.system('quickshear {} {} {}'.format(anat_orig, anat_mask, anat_defaced))
    print('Defaced anatomical file is {}'.format(anat_defaced), file = sys.stdout)

    # Create PNG file of defaced image
    for anat in [anat_orig, anat_defaced]:
        image = nib.load(anat)
        object_img_array = image.dataobj[:]

        slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
        slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
        slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]

        fig, axes = plt.subplots(1,3, figsize=(9,3))
        for i, slice in enumerate([slice_x, slice_y, slice_z]):
            axes[i].imshow(slice.T, cmap="gray", origin="lower", aspect='auto')
            axes[i].axis('off')
        plt.subplots_adjust(wspace=0, hspace=0)
        plt.savefig('{}.png'.format(anat.split('.nii.gz')[0]), bbox_inches='tight')

    if ses == '':
        dic = {'id': 1, 'defaced': anat_defaced, 'defaced_thumb': anat_defaced.split(root)[-1].split('.nii.gz')[0] + '.png', 'info': 'type {} is defaced for sub-{}'.format(br_type, sub)}
    else:
        dic = {'id': 1, 'defaced': anat_defaced, 'defaced_thumb': anat_defaced.split(root)[-1].split('.nii.gz')[0] + '.png', 'info': 'type {} is defaced for sub-{}/ses-{}'.format(br_type, sub, ses)}

    file = open(log_file, "w")
    file.write(repr(dic) + "\n")
    file.close()
    print("thumbnail {}".format(dic), file=sys.stdout)
    
def deface_parallel():
    pool = Pool(processes=len(deface_list))
    pool.map(deface, deface_list)
    

if __name__ == '__main__':
    deface_parallel()


