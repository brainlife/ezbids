#!/bin/bash

set -e
set -x

export SHELL=$(type -p bash)

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi

root=$1
method=$(jq -r .method $root/deface.json)

# allineate defacing is implemented in handler/deface.ts (Node): canonicalize + allineate binary.
# This script is used for pydeface (parallel) and other bash-only paths.

#so runDeface parallel function can access it
export root
export method
export appdir=$(pwd)/ezBIDS_core

function runDeface() {
    #note.. this function runs inside $root (by --wd $root)
    set -e
    set -x

    config=$1

    idx=$(echo $config | jq -r .idx)
    anat=$(echo $config | jq -r .path)
    #apply fslreorient2std to anat image
    fslreorient2std $anat $anat
    defaced=$anat.defaced.nii.gz

    echo "--------------- defacing($method) [$idx] $anat to $defaced ----------------"
    case $method in
        pydeface)
            time pydeface --verbose --force $anat --outfile $defaced
        ;;
        *)
            echo "Unsupported method in deface.sh: $method (use Node deface for allineate)"
            exit 1
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
}
export -f runDeface

#list of idx that finished defacing
true > $root/deface.finished
true > $root/deface.failed

#now run defacing
jq -c '.list[]' $root/deface.json | parallel --linebuffer --wd $root -j 6 runDeface {}

echo "all done defacing"
