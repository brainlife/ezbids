#!/bin/bash

set -e
set -x

export SHELL=$(type -p bash)
# if [ $OSTYPE == "darwin" ]; then
#     export SHELL=$(type -p bash)
# fi
    
if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

echo "running expand.sh"
#timeout 3600 ./expand.sh $root
#disabling timeout until we migrate to js2
./expand.sh $root

echo "replace file path that contains space"
# find $root -depth -name "* *" -execdir rename 's/ /_/g' "{}" \;
find $root -depth -name "*[ ()]*" -execdir rename 's/[ )]/_/g; s/\(//g' "{}" \;

# If there are .nii files, compress them to .nii.gz
echo "Making sure all NIfTI files are in .nii.gz format"
touch $root/nii_files
find $root -name "*.nii" > $root/nii_files
[ -s $root/nii_files ] && gzip $(cat $root/nii_files)

echo "processing $root"

echo "finding dicom directories"
./find_dicomdir.py $root > $root/dcm2niix.list
cat $root/dcm2niix.list

# There can be overlap between the dicom directories and the pet directories
# we want to use dcm2niix4pet for the pet directories, and dcm2niix for the dicom directories
# but if and only if the conversion library PET2BIDS is installed
PET2BIDS_INSTALLED=`which dcm2niix4pet > /dev/null && echo $?`

if [ $PET2BIDS_INSTALLED -eq 0 ]; then

    function dcm2niix4pet {
        #note.. this function runs inside $root (by --wd $root)

        path=$1

        echo "----------------------- $path ------------------------"
        timeout 3600 dcm2niix4pet $path

        #all good
        echo $path >> pet2bids.done
    } 

    export -f dcm2niix4pet

    # now we do a little magic to run pet2bids if it's installed
    ./find_petdir.py $root > $root/pet2bids.list
    echo "Found PET directories:"
    cat $root/pet2bids.list

    # remove pet directories from dcm2niix list
    echo "Removing PET directories from dcm2niix list"
    grep -v -x -f <(sort pet2bids.list) <(sort dcm2niix.list) > dcm2niix.list
    
    # run pet2bids
    true > $root/pet2bids.done

    if [ $OSTYPE = "darwin" ]; then
        cat $root/pet2bids.list | dcm2niix4pet {} 2>> $root/pet2bids_output
    else
        cat $root/pet2bids.list | parallel --linebuffer --wd $root -j 6 dcm2niix4pet {} 2>> $root/pet2bids_output
    fi

fi

echo "running dcm2niix"
true > $root/dcm2niix.done
function d2n {
    #note.. this function runs inside $root (by --wd $root)

    #set -e #we can't set this here because dcm2niix could return code:2
    #which just means there are no DICOM files in that directory
    set -x

    path=$1

    echo "----------------------- $path ------------------------"
    timeout 3600 dcm2niix --progress y -v 1 -ba n -z o -d 9 -f 'time-%t-sn-%s' $path

    #all good
    echo $path >> dcm2niix.done
}

export -f d2n

if [ $OSTYPE = "darwin" ]; then
    cat $root/dcm2niix.list | d2n {} 2>> $root/dcm2niix_output
else
    cat $root/dcm2niix.list | parallel --linebuffer --wd $root -j 6 d2n {} 2>> $root/dcm2niix_output
fi

#find products
(cd $root && find . -type f \( -name "*.json" \) > list)
cat $root/list

if [ ! -s $root/list ]; then
    echo "couldn't find any dicom files. aborting"
    exit 1
fi

# pull dcm2niix error information to log file
{ grep -B 1 --group-separator=$'\n\n' Error $root/dcm2niix_output || true; } > $root/dcm2niix_error
# # remove error message(s) about not finding any DICOMs in folder
line_nums=$(grep -n 'Error: Unable to find any DICOM images' $root/dcm2niix_error | cut -d: -f1)

for line_num in ${line_nums[*]}
do
    sed -i "$((line_num-1)), $((line_num+1))d" $root/dcm2niix_error
done

echo "running ezBIDS_core (may take several minutes, depending on size of data)"
python3 "./ezBIDS_core/ezBIDS_core.py" $root

echo "generating thumbnails and movies for 3/4D acquisitions (may take several minutes, depending on size of data)"
cat $root/list | parallel --linebuffer -j 6 --progress python3 "./ezBIDS_core/createThumbnailsMovies.py" $root

echo "updating ezBIDS_core.json"
python3 "./ezBIDS_core/update_ezBIDS_core.py" $root

echo "done preprocessing"
