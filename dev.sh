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
    echo "building mongodb"
    ./mongodb/mongodb_setup.sh
fi

# if [ ! -f ${PWD}/api.sif ]; then
#     echo "building api"
#     singularity build --fakeroot $PWD/api.sif Singularity

#     singularity instance start --bind /tmp,./api:/app/api $PWD/api.sif brainlife_ezbids-api
# fi

singularity-compose --debug up --no-resolv
