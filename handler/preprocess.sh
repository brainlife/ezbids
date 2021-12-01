#!/bin/bash

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
echo "Making sure all NIfTI files are in .nii.gz format"
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
    timeout 3600 dcm2niix --progress y -v 1 -ba n -z o -f 'time-%t-sn-%s' $path

    #all good
    echo $path >> dcm2niix.done
}

export -f d2n
cat $root/dcm2niix.list | parallel --linebuffer --wd $root -j 6 d2n {} 2>> $root/dcm2niix_output
grep -B 1 --group-separator=$'\n\n\n\n' 'Error' $root/dcm2niix_output > $root/dcm2niix_error_log.txt # Get the dcm2niix error, and line above the error. Line above should contain the path of the DICOM folder causing the issue
rm -rf $root/dcm2niix_output # Don't need this anymore


# Stop ezBIDS if dcm2niix produced any errors
if grep -q Error "$root/dcm2niix_error_log.txt"; then
    echo "FATAL: dcm2niix error(s) detected. This suggests something wrong with you data. ezBIDS will abort until this can be resolved."
    echo "Please post a new issue to the dcm2niix Issues page (https://github.com/rordenlab/dcm2niix/issues) for assistance in this matter, with the contents of the error log (dcm2niix_error_log.txt)."
    echo "Once resolved, please re-upload your data."
    exit 1
fi


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
