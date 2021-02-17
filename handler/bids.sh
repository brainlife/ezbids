#!/bin/bash

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

rm -rf $root/bids

echo "reorienting anatomical images to RAS+ and defacing"
export root
python_code=$(cat <<END
import os, json, deepdefacer
import nibabel as nib


root = os.environ['root']
finalize_json = open('{}/finalize.json'.format(root))
finalize_json = json.load(finalize_json, strict=False)

for i in range(len(finalize_json['objects'])):
    if 'anat' in finalize_json['objects'][i]['_type']:
        anat_path = [x for x in finalize_json['objects'][i]['paths'] if '.nii' in x][0]
        
        anat_path = root + '/' + anat_path.split('./')[-1]
        img = nib.load(anat_path)
        new_img = nib.as_closest_canonical(img)
        nib.save(new_img, anat_path)
        
        os.system('deepdefacer --input_file {} --defaced_output_path {}'.format(anat_path, anat_path.split('.nii')[0] + '_defaced' + '.nii.gz'))
END
)
run="$(python3 -c "$python_code")"

echo "converting output to bids"
./convert.js $root

echo "output bids directory structure"
tree $root/bids
