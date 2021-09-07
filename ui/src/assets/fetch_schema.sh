#!/bin/bash

git clone --depth 1 https://github.com/bids-standard/bids-specification -b v1.6.0 bids-specification

mkdir -p schema/datatypes

echo "converting entities.yaml"
yq eval -o=j bids-specification/src/schema/entities.yaml > schema/entities.json

for yaml in $(ls bids-specification/src/schema/datatypes); do
    echo "converting datatypes/$yaml"
    filename="${yaml%.*}"
    yq eval -o=j bids-specification/src/schema/datatypes/$yaml > schema/datatypes/$filename.json
done

rm -rf bids-specification
