#!/bin/bash


set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi

root=$1
method=$(jq -r .method $root/deface.json)

#so runDeface parallel function can access it
export root
export method
export appdir=$(pwd)

function runDeface() {
    #note.. this function runs inside $root (by --wd $root)
    set -e
    set -x

    config=$1
        
    idx=$(echo $config | jq -r .idx) 
    anat=$(echo $config | jq -r .path)
    defaced=$anat.defaced.nii.gz

    echo "--------------- defacing($method) [$idx] $anat to $defaced ----------------"
    #if [ -f $defaced ]; then
    #    echo "already defaced"
    #    echo $idx >> $root/deface.finished
    #else
        #TODO - add other methods?
        case $method in
            quickshear)
                time runROBEX.sh $anat $anat.mask.nii.gz
                timeout 60 quickshear $anat $anat.mask.nii.gz $defaced
            ;;
            pydeface)
                time pydeface --force $anat --outfile $defaced
            ;;
        esac

        if [ $? -ne 0 ]; then
            echo "defacing failed?"
            echo $idx >> $root/deface.failed
        else
            #create thumbnail
            timeout 100 $appdir/createThumbnail.py $defaced $defaced.png
            echo $idx >> $root/deface.finished
        fi
    #fi
}
export -f runDeface

#list of idx that finished defacing
true > $root/deface.finished 
true > $root/deface.failed

#now run defacing
jq -c '.list[]' $root/deface.json | parallel --linebuffer --wd $root -j 6 runDeface {}

echo "all done defacing"
