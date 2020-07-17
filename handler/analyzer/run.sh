#!/bin/bash

set -e
set -x

root=$1

#this script should run dan's dicom directory analyzer
python3 ezBIDS_data_extraction.py $root
here=$( dirname "${BASH_SOURCE[0]}" )
cp $here/ezbids_reference.json $root/ezbids.json


