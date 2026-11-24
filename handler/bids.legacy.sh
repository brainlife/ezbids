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
bids-validator --json "$rootDir" > $root/validator.json || true

echo "Copying finalized.json file to ezBIDS_template.json"
cp -r $root/finalized.json $root/ezBIDS_template.json

# Telemetry is off by default (and always off in the desktop app). Setting EZBIDS_TELEMETRY_URL turns it on: the files are then created and
# POSTed best effort (time-limited, two quick retries); a failure is only logged and never fails the step.
telemetry_url=${EZBIDS_TELEMETRY_URL:-}
if [ -n "$telemetry_url" ] && [ "$IS_ELECTRON" != "true" ]; then
    echo "Creating ezBIDS telemetry files"
    ./telemetry.py $root
    for f in validator.json ezBIDS_core_telemetry.json ezBIDS_finalized_telemetry.json; do
        if [ -f "$root/$f" ]; then
            curl -sS -m 10 --retry 2 --retry-connrefused --retry-max-time 20 -H 'Content-Type: application/json' \
                -d @"$root/$f" -X POST "$telemetry_url" || echo "telemetry not sent ($f): server unreachable"
        fi
    done
fi
