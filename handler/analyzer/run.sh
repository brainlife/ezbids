#!/bin/bash

set -x

#echo "running with profiler"
# python3 -m cProfile ./analyzer/analyzer.py $1
python3 ./analyzer/analyzer.py $1


