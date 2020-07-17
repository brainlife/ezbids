#!/bin/bash

set -x

#singularity exec -e docker://brainlife/ezbids:1.0 ./analyzer/ezBIDS_data_extraction.py $1
./analyzer/ezBIDS_data_extraction.py $1


