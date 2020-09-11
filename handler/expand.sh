#!/bin/bash

#for 7z sudo apt-get install p7zip-full

set -e
set -x

root=$1
cd $root

echo "expanding zip/gz/tar in $root"

#expand various things that we can expand
function expand {

    #pigz can't handle xz.. so fall back to use native tar uncompressor
    for tar in $(find -name "*.tar.xz"); do
        echo $tar
        #tar is too verbose
        tar -xf $tar -C $(dirname $tar)
        rm $tar
    done

    for tar in $(find -name "*.tar*"); do
        echo $tar
        #tar is too verbose
        tar -I pigz -xf $tar -C $(dirname $tar)
        rm $tar
    done

    for tar in $(find -name "*.tgz"); do
        echo $tar
        #tar is too verbose
        tar -I pigz -xf $tar -C $(dirname $tar)
        rm $tar
    done

    for gz in $(find -name "*.gz"); do
        echo $tar
        gunzip $gz
    done

    for zip in $(find -name "*.7z"); do
        echo $tar
        7z x $zip
        rm $zip
    done

    for zip in $(find -name "*.bz2"); do
        echo $tar
        bunzip2 $zip
    done

    for zip in $(find -name "*.zip"); do
        echo $tar
        unzip -o $zip -d $(dirname $zip)
        rm $zip
    done

    for rar in $(find -name "*.rar"); do
        echo $rar
        unrar x $rar
        rm $rar
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
    else
        echo "keep going"
    fi
done

