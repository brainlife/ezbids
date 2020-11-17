#!/bin/bash

#module load pigz

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

echo "running expand.sh"
timeout 3600 ./expand.sh $root

#remove stuff that we know we can't convert
echo "removing .nii.gz"
find $root -name "*.nii.gz" -exec rm -rf {} \;
echo "removing .json"
find $root -name "*.json" -exec rm -rf {} \;
echo "removing .nii"
find $root -name "*.nii" -exec rm -rf {} \;

echo processing $root

echo "finding dicom directories"
./find_dicomdir.py $root > $root/dcm2niix.list
cat $root/dcm2niix.list

echo "running dcm2niix"
true > $root/dcm2niix.done
function d2n {
    path=$1
    echo "----------------------- $path ------------------------"
    timeout 3600 dcm2niix -v 1 -ba n -z o -f 'time-%t-sn-%s' $path
    ret=$!
    if [ $ret == 2 ]; then
        #probably empty directory?
        echo "skipping"
        return
    fi
    if [ $ret != 0]; then
        echo "dcm2niix failed"
        exit $ret
    fi
    echo $1 >> dcm2niix.done
}
export -f d2n
cat $root/dcm2niix.list | parallel --wd $root -j 6 d2n {}

#find products
(cd $root && find . -type f \( -name "*.json" -o -name "*.nii.gz" -o -name "*.bval" -o -name "*.bvec" \) > list)
cat $root/list

if [ ! -s $root/list ]; then
    echo "couldn't find any dicom files. aborting"
    exit 1
fi

echo "running analyzer"
timeout 600 ./analyzer/run.sh $root

echo "done preprocessing"


