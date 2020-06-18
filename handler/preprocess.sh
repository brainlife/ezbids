#!/bin/bash

#module load pigz

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

time ./expand.sh $root
ls $root

echo processing $root
#(cd $root && find . -print > raw.list)

#find leaf directories
#for dir in $(python find_dicomdir.py $root);
#do
#        (cd $root && time dcm2niix -z o -f 'time-%t-sn-%s' -v 1 $dir)
#done

./find_dicomdir.py $root | parallel --wd $root -j 4 dcm2niix -v 1 -z o -f 'time-%t-sn-%s' {}

(cd $root && find . -type f \( -name "*.json" -o -name "*.nii.gz" \) > list)

./analyzer/run.sh $root

echo "done preprocessing"
