#!/bin/bash

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

echo "converting output to bids"
./convert.js $root

echo "output bids directory structure"
tree $root/bids
