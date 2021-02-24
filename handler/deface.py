#!/usr/bin/env python3
"""
Created on Wed Feb 17 08:32:55 2021

Deface anatomical images

@author: dlevitas
"""

import os, sys, json
import nibabel as nib
import matplotlib.pyplot as plt
from math import floor
from multiprocessing import Pool

root = sys.argv[1]

finalized_json = open('{}/finalized.json'.format(root))
finalized_json = json.load(finalized_json, strict=False)

deface_list = []
if finalized_json['deface'] == True:
    for i in range(len(finalized_json['objects'])):
        if 'anat' in finalized_json['objects'][i]['_type'] and finalized_json['objects'][i]['include'] == True:
            sub = finalized_json['objects'][i]['_entities']['subject']
            ses = finalized_json['objects'][i]['_entities']['session']
            br_type = finalized_json['objects'][i]['_type']
            
#             anat_path = [x for x in finalized_json['objects'][i]['paths'] if '.nii' in x][0]
#             anat_path = root + '/' + anat_path.split('./')[-1]
            anat_path = finalized_json['objects'][i]['paths'][-1]

            deface_list.append([anat_path, br_type, sub, ses])
 
print('deface list is : {}'.format([x[0] for x in deface_list]))

# Functions
def deface(deface_list):
    anat_path = deface_list[0]
    # Skull strip and deface
    print('Performing defacing on {}'.format(anat_path), file = sys.stdout)
    os.system('runROBEX.sh {} {}'.format(anat_path, anat_path.split('.nii.gz')[0] + '_mask.nii.gz'))
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
#     print('Defaced anat thumbnail: {}.png'.format(anat_path.split('.nii.gz')[0]), file = sys.stdout)
    if ses == '':
        pass
    else:
        print("thumbnail {'path': {}, 'name': {} defaced for sub-{}/ses-{}".format(anat_path.split('.nii.gz')[0] + '.png', br_type, sub, ses), file=sys.stdout}

    
def deface_parallel():
    pool = Pool(processes=len(deface_list))
    pool.map(deface, deface_list)
    

if __name__ == '__main__':
    deface_parallel()


            
                
