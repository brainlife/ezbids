#!/bin/bash

set -x

echo "running with profiler"
python3 -m cProfile ./analyzer/ezBIDS_data_extraction.py $1


