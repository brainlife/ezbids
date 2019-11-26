#!/bin/bash

module load pigz

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

./expand.sh $root
ls $root

echo processing $root
(cd $root && find . -print > raw.list)

#find leaf directories
for dir in $(python find_dicomdir.py $root);
do
        (cd $root && dcm2niix -z yes -f 'time-%t-sn-%s' -v 1 $dir)
done

(cd $root && find . -type f \( -name "*.json" -o -name "*.nii.gz" \) > list)

