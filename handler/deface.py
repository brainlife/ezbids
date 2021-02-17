#!/usr/bin/env python3
"""
Created on Wed Feb 17 08:32:55 2021

Reorient & deface anatomical images

@author: dlevitas
"""

import os, sys, json, deepdefacer
import nibabel as nib

root = sys.argv[1]

finalized_json = open('{}/finalized.json'.format(root))
finalized_json = json.load(finalized_json, strict=False)

if finalized_json['deface'] == True:
    for i in range(len(finalized_json['objects'])):
        if 'anat' in finalized_json['objects'][i]['_type'] and finalized_json['objects'][i]['_exclude'] == False:
            anat_path = [x for x in finalized_json['objects'][i]['paths'] if '.nii' in x][0]
            print('Performing defacing on {}'.format(anat_path), file = sys.stdout)
            img = nib.load(anat_path)
            new_img = nib.as_closest_canonical(img)
            nib.save(new_img, anat_path)

            os.system('deepdefacer --input_file {} --defaced_output_path {}'.format(anat_path, anat_path.split('.nii')[0] + '_defaced' + '.nii.gz'))
