#!/bin/bash

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

datasetName=`jq -r '.datasetDescription.Name' $root/finalized.json`


#TODO - validate $root?
# rm -rf $root/bids
rm -rf $root/datasetName

#echo "making deface list"
#./make_deface_list.py $root
#
#echo "running defacing"
#if [ ! -f $root/deface.out ]; then
#    touch $root/deface.out
#fi
#
#chmod -R 777 $root

#function deface {
#    deface_info=$1 
#    ./deface.py $deface_info
#}
#export -f deface
#cat $root/deface_list.txt | parallel -j 12 deface {}

echo "converting output to bids"
./convert.js $root


echo "output bids directory structure"
tree $root/$datasetName > $root/tree.log

echo "running bids validator"
bids-validator $root/$datasetName > $root/validator.log || true

