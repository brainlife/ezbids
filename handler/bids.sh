#!/bin/bash

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

echo "converting output to bids"
mkdir -p $root/bids
./convert.js $root
#jq .datasetDescription $root/finalized.json > $root/bids/dataset_description.json
#jq -r .readme $root/finalized.json > $root/bids/README.md
#jq -r .participantsColumn $root/finalized.json > $root/bids/participants.json
#jq -r .participants $root/finalized.json > $root/bids/participants.json

