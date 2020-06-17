#!/bin/bash

root=$1

#this script should run dan's dicom directory analyzer
here=$( dirname "${BASH_SOURCE[0]}" )
cp $here/ezbids_reference.json $root

