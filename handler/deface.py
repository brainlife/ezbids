#!/usr/bin/env python3
"""
Created on Wed Feb 17 08:32:55 2021

Reorient & deface anatomical images

@author: dlevitas
"""

import os, sys, json, deepdefacer
import nibabel as nib

root = sys.argv[1]

print(root, file = sys.stderr)

finalize_json = open('{}/finalize.json'.format(root))
finalize_json = json.load(finalize_json, strict=False)

if finalize_json['deface'] == True:
    print('here we go', file = sys.stdout)
    for i in range(len(finalize_json['objects'])):
        if 'anat' in finalize_json['objects'][i]['_type'] and finalize_json['objects'][i]['_exclude'] == False:
            anat_path = [x for x in finalize_json['objects'][i]['paths'] if '.nii' in x][0]
            # anat_path = root + '/' + anat_path.split('./')[-1]
            img = nib.load(anat_path)
            new_img = nib.as_closest_canonical(img)
            nib.save(new_img, anat_path)

            os.system('deepdefacer --input_file {} --defaced_output_path {}'.format(anat_path, anat_path.split('.nii')[0] + '_defaced' + '.nii.gz'))
