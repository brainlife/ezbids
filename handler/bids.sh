#!/bin/bash

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

rm -rf $root/bids

echo "running defacing"
# parallel --wd $root -j 6 d2n {}
if [ ! -f $root/deface.out ]; then
    touch $root/deface.out
fi
function deface{
    ./deface.py $root >> deface.out
}
parallel -j 10 deface 
# ./deface.py $root

echo "converting output to bids"
./convert.js $root

echo "output bids directory structure"
tree $root/bids
