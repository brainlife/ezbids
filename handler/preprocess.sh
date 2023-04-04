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

# check to see if uploaded data is a BIDS-compliant dataset
echo "Running bids-validator to check BIDS compliance"

# Check the ezBIDS uploaded directory to see if it's a BIDS-compliant root directory or contains one
# Search a few levels down in case a sub-directory is actually the BIDS root (could happen based on how user stored their data)
substring="dataset_description.json"
maxdepth=1

test_root=($(find $root -maxdepth $maxdepth -type f \( -name $substring \)))

until [[ $maxdepth -gt 5 ]]
do
    if [[ "$test_root" == *"$substring"* ]]; then
        break
    else
        ((maxdepth++))
        test_root=($(find $root -maxdepth $maxdepth -type f \( -name $substring \)))
    fi
done

test_root=${test_root///$substring/}

touch $test_root/.bidsignore
echo "*finalized.json" > $test_root/.bidsignore
echo "*dcm2niix*" > $test_root/.bidsignore
echo "*preprocess*" >> $test_root/.bidsignore
echo "*list" >> $test_root/.bidsignore
echo "*nii_files" >> $test_root/.bidsignore
echo "*ezBIDS_core.json" >> $test_root/.bidsignore
echo "*bids_compliant.log" >> $test_root/.bidsignore
echo "*validator.log" >> $test_root/.bidsignore
echo "*.png" >> $test_root/.bidsignore

bids-validator $test_root > $test_root/validator.log || true

if grep -w "ERR" $test_root/validator.log; then
	echo "Uploaded data is not a BIDS-compliant dataset"
    bids_compliant="no"
else
    echo "Uploaded data is a BIDS-compliant dataset"
	bids_compliant="yes"
fi

echo $test_root > $root/bids_compliant.log
echo $bids_compliant >> $root/bids_compliant.log

cat $root/bids_compliant.log

if [ $bids_compliant == "yes" ]; then
    # Skip certain processing steps, since uploaded data is already BIDS-compliant

    touch $root/dcm2niix_output
    touch $root/dcm2niix_error
    
    #find products
    (cd $root && find . -mindepth 2 -type f \( -name "*.json" \) > list)
    # remove irrelevant json files (ezBIDS_core.json, dataset_description.json, participants.json) if found
    grep -F -v ezBIDS_core.json $root/list > $root/list_tmp && mv $root/list_tmp $root/list
    grep -F -v dataset_description.json $root/list > $root/list_tmp && mv $root/list_tmp $root/list
    grep -F -v participants.json $root/list > $root/list_tmp && mv $root/list_tmp $root/list

    echo "running ezBIDS_core (may take several minutes, depending on size of data)"
    python3 "./ezBIDS_core/ezBIDS_core.py" $root
else
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
    # remove irrelevant json files (ezBIDS_core.json, dataset_description.json, participants.json) if found
    grep -F -v ezBIDS_core.json $root/list > $root/list_tmp && mv $root/list_tmp $root/list
    grep -F -v dataset_description.json $root/list > $root/list_tmp && mv $root/list_tmp $root/list
    grep -F -v participants.json $root/list > $root/list_tmp && mv $root/list_tmp $root/list

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
fi

echo "done preprocessing"
