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

echo "converting output to bids"
npm run convert $root

echo "output bids directory structure"
tree "$rootDir" > $root/tree.log

echo "running bids validator"
bids-validator "$rootDir" > $root/validator.log || true

