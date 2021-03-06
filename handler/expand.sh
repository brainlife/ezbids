#!/bin/bash

#for 7z sudo apt-get install p7zip-full

#set -e #this makes the whole expand to get stuck if it fails to untar
set -x

root=$1
cd $root

echo "expanding zip/gz/tar in $root"

#expand various things that we can expand
function expand {

    #pigz can't handle xz.. so fall back to use native tar uncompressor
    for tar in $(find $root -name "*.tar.xz"); do
        #tar is too verbose
        tar -xf $tar -C $(dirname $tar)
        rm -rf $tar
    done

    for tar in $(find $root -name "*.tar*"); do
        #tar is too verbose
        tar -I pigz -xf $tar -C $(dirname $tar)
        rm -rf $tar
    done

    for tar in $(find $root -name "*.tgz"); do
        #tar is too verbose
        tar -I pigz -xf $tar -C $(dirname $tar)
        rm -rf $tar
    done

    for gz in $(find $root -name "*.gz"); do
        if [[ "$gz" != *".nii.gz" ]]; then
            gunzip $gz
            rm -rf $gz
        fi
    done

    for zip in $(find $root -name "*.7z"); do
        7z x $zip
        rm -rf $zip
    done

    for zip in $(find $root -name "*.bz2"); do
        bunzip2 $zip
        rm -rf $zip
    done

    for zip in $(find $root -name "*.zip"); do
        unzip -o $zip -d $(dirname $zip)
        rm -rf $zip
    done

    for rar in $(find $root -name "*.rar"); do
        unrar x $rar
        rm -rf $rar
    done

    #TODO .xz?
}

#keep expanding until there is nothing else to expand
while true; do
    expand | tee expand.log
    if [ ! -s expand.log ]; then
        echo "expand log empty ..done"
        rm expand.log
        break
    fi
done


