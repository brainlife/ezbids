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
#ls $root

echo processing $root
#(cd $root && find . -print > raw.list)

#find leaf directories
#for dir in $(python find_dicomdir.py $root);
#do
#        (cd $root && time dcm2niix -z o -f 'time-%t-sn-%s' -v 1 $dir)
#done

echo "finding dicom directories"
./find_dicomdir.py $root > $root/dcm2niix.list
cat $root/dcm2niix.list

echo "running dcm2niix"
true > $root/dcm2niix.done
function d2n {
    path=$1
    echo "----------------------- $path ------------------------"
    dcm2niix -v 1 -ba n -z o -f 'time-%t-sn-%s' $path
    echo $1 >> dcm2niix.done
}
export -f d2n
cat $root/dcm2niix.list | parallel --wd $root -j 4 d2n {}

#find products
(cd $root && find . -type f \( -name "*.json" -o -name "*.nii.gz" \) > list)

time ./analyzer/run.sh $root

echo "done preprocessing"
