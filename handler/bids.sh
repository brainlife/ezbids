#!/bin/bash

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

datasetName=`jq -r '.datasetDescription.Name' $root/finalized.json`

rootDir="$root/bids/$datasetName"

#clean up from previous run
rm -rf $root/bids

# run MEG BIDS conversion if relevant data found
echo "converting MEG data (if present)"
./convert_meg.py $root/finalized.json $rootDir

echo "converting output to bids"
./convert.js $root

echo "output bids directory structure"
tree "$rootDir" > $root/tree.log

echo "running bids validator"
bids-validator "$rootDir" > $root/validator.log || true

echo "Copying finalized.json file to ezBIDS_template.json"
cp -r $root/finalized.json $root/ezBIDS_template.json

