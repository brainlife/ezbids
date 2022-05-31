#!/bin/bash

#TODO get rid of this eventually and let UI load the .yml files directly

#git clone --depth 1 https://github.com/bids-standard/bids-specification -b v1.6.0 bids-specification

schemadir=../../../bids-specification/src/schema

mkdir -p schema/objects
mkdir -p schema/rules
mkdir -p schema/rules/datatypes

echo "converting entities.yaml"
yq eval -o=j $schemadir/objects/entities.yaml > schema/objects/entities.json
yq eval -o=j $schemadir/rules/entities.yaml > schema/rules/entities.json

ls $schemadir/rules/datatypes
for yaml in $(ls $schemadir/rules/datatypes/*.yaml); do
    filename=$(basename $yaml .yaml)
    echo "converting $yaml to $filename.json"
    yq eval -o=j $yaml > schema/rules/datatypes/$filename.json
done

#rm -rf bids-specification
