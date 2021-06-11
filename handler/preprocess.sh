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
timeout 1800 ./expand.sh $root

echo "replace file path that contains space"
find $root -depth -name "* *" -execdir rename 's/ /_/g' "{}" \;

# If there are .nii files, compress them to .nii.gz
touch $root/nii_files
find $root -name "*.nii" > $root/nii_files
[ -s $root/nii_files ] && gzip $(cat $root/nii_files) 

echo "processing $root"

echo "finding dicom directories"
./find_dicomdir.py $root > $root/dcm2niix.list
cat $root/dcm2niix.list

echo "running dcm2niix"
true > $root/dcm2niix.done
function d2n {
    #note.. this function runs inside $root (by --wd $root)

    #set -e #we can't set this here because dcm2niix could return code:2
    #which just means there are no .dcm files in that directory
    set -x

    path=$1

    echo "----------------------- $path ------------------------"
    timeout 3600 dcm2niix -v 1 -ba n -z o -f 'time-%t-sn-%s' $path
    ret=$? 
    echo "dcm2niix returned $ret"

    if [ $ret -eq 2 ]; then
        #probably empty directory?
        echo "skipping directory with no DICOM image"
        return
    fi
    if [ $ret -ne 0 ]; then
        echo "dcm2niix returned $ret"
        return $ret
    fi

    #all good
    echo $path >> dcm2niix.done
}

export -f d2n
cat $root/dcm2niix.list | parallel --linebuffer --wd $root -j 6 d2n {}

#find products
(cd $root && find . -type f \( -name "*.json" \) > list)
cat $root/list

if [ ! -s $root/list ]; then
    echo "couldn't find any dicom files. aborting"
    exit 1
fi

echo "running analyzer (should only take a minute)"
timeout 600 ./analyzer/run.sh $root

echo "done preprocessing"


