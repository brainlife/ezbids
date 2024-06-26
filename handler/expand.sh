#!/bin/bash

#for 7z sudo apt-get install p7zip-full

#set -e #this makes the whole expand to get stuck if it fails to untar
set -x

root=$1
cd $root

echo "expanding archives in $root"

#expand various things that we can expand
function expand {

    ##############################################################################################
    ##
    ## tar can handle most things
    ##
    expand_counter=1

    #use pigz for gz
    for tar in $(find $root -name "*.tar.gz"); do
        if [ ! -d $(dirname $tar)/$expand_counter ]; then
            mkdir -p $(dirname $tar)/$expand_counter
        fi
        tar -I pigz -xf $tar -C $(dirname $tar)/$expand_counter
        expand_counter=$((expand_counter+1))
        rm -rf $tar
    done

    for tar in $(find $root -name "*.tgz"); do
        #tar is too verbose
        if [ ! -d $(dirname $tar)/$expand_counter ]; then
            mkdir -p $(dirname $tar)/$expand_counter
        fi
        tar -I pigz -xf $tar -C $(dirname $tar)/$expand_counter
        expand_counter=$((expand_counter+1))
        rm -rf $tar
    done

    #let tar handle all other compression algorithms in default way
    for tar in $(find $root -name "*.tar*"); do
        echo "found $tar ----------"
        if [ ! -d $(dirname $tar)/$expand_counter ]; then
            mkdir -p $(dirname $tar)/$expand_counter
        fi
        tar -xf $tar -C $(dirname $tar)/$expand_counter
        expand_counter=$((expand_counter+1))
        rm -rf $tar
    done

    ##
    ##
    ##############################################################################################

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
        unzip -o $zip -d $(dirname $zip)/$expand_counter
        expand_counter=$((expand_counter+1))
        rm -rf $zip
    done

    for rar in $(find $root -name "*.rar"); do
        unrar x $rar
        rm -rf $rar
    done

    for zst in $(find $root -name "*.zst"); do
        zst -d $zip
        rm -rf $zip
    done
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


