#!/usr/bin/env bash

set -ex

git submodule update --init --recursive

(cd api && npm install)
(cd ui && npm install)

mkdir -p /tmp/upload
mkdir -p /tmp/workdir

npm run prepare-husky

# Use singularity-compose instead of docker-compose

# Helpful commentary on mongodb container build with Singularity: https://stackoverflow.com/questions/70746228/singularity-mongodb-container-in-background-mode
if [ ! -d $PWD/data/db ]; then
    mkdir -p $PWD/data/db
fi

if [ ! -f $PWD/mongodb/mongodb.sif ]; then # Will eventually be redundant and can remove
    ./mongodb/mongodb_setup.sh
fi

singularity-compose --debug up --no-resolv
