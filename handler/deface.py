#!/usr/bin/env python3
"""
Created on Wed Feb 17 08:32:55 2021

Deface anatomical images

@author: dlevitas
"""

import os, sys, json
import nibabel as nib

root = sys.argv[1]

finalized_json = open('{}/finalized.json'.format(root))
finalized_json = json.load(finalized_json, strict=False)

if finalized_json['deface'] == True:
    for i in range(len(finalized_json['objects'])):
        if 'anat' in finalized_json['objects'][i]['_type'] and finalized_json['objects'][i]['include'] == True:
            anat_path = [x for x in finalized_json['objects'][i]['paths'] if '.nii' in x][0]
            anat_path = root + '/' + anat_path.split('./')[-1]
            print('Performing defacing on {}'.format(anat_path), file = sys.stdout)
            os.system('runROBEX.sh {} {}'.format(anat_path, anat_path.split('.nii.gz')[0] + '_mask.nii.gz'))
            os.system('quickshear {} {} {}'.format(anat_path, anat_path.split('.nii.gz')[0] + '_mask.nii.gz', anat_path))
            #os.remove(anat_path.split('.nii.gz')[0] + '_mask.nii.gz')
            print('Defaced anatomical file is {}'.format(anat_path), file = sys.stdout)
