#!/usr/bin/env python3
"""
Created on Wed Feb 17 08:32:55 2021
Create list of anatomical images to deface
@author: dlevitas
"""

import os, sys, json
import numpy as np

os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'

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
            anat_orig = root + '/' + finalized_json['objects'][i]['paths'][-1].split('./')[-1]
            deface_list.append([anat_orig, br_type, sub, ses])

            
np.savetxt('{}/deface_list.txt'.format(root), np.array(deface_list), fmt="%s")
 

    



