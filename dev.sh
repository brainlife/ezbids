#!/usr/bin/env bash

set -ex

git submodule update --init --recursive

(cd api && npm install)
(cd ui && npm install)

mkdir -p /tmp/upload
mkdir -p /tmp/workdir

npm run prepare-husky

# Use singularity-compose instead of docker-compose

export SINGULARITY_DISABLE_CACHE=true
export SINGULARITY_CACHEDIR=/tmp
# Helpful commentary on mongodb container build with Singularity: https://stackoverflow.com/questions/70746228/singularity-mongodb-container-in-background-mode
if [ ! -d $PWD/data/db ]; then
    mkdir -p $PWD/data/db
fi

if [ ! -f $PWD/mongodb/mongodb.sif ]; then # Will eventually be redundant and can remove
    echo "building mongodb"
    singularity build --arch "amd64" --fakeroot --disable-cache $PWD/mongodb/mongodb.sif $PWD/mongodb/Singularity
    singularity instance start --bind ./data/db:/data/db $PWD/mongodb/mongodb.sif brainlife_ezbids-mongodb
    # singularity run instance://brainlife_ezbids-mongodb # This seems to run mongodb in the foreground, meaning can't move on to building other containers
fi

if [ ! -f $PWD/api/api.sif ]; then
    echo "building api"
    singularity build --arch "amd64" --fakeroot --disable-cache $PWD/api/api.sif Singularity
    singularity instance start --bind /tmp:/tmp --bind ./api:/app/api $PWD/api/api.sif brainlife_ezbids-api
fi


if [ ! -f $PWD/handler/handler.sif ]; then
    echo "building handler"
    singularity build --arch "amd64" --fakeroot --disable-cache $PWD/handler/handler.sif $PWD/handler/Singularity
    singularity instance start --bind /tmp:/tmp --bind .:/app $PWD/handler/handler.sif brainlife_ezbids-handler
fi

if [ ! -f $PWD/ui/ui.sif ]; then
    echo "building ui"
    cd ui
    singularity build --arch "amd64" --fakeroot --disable-cache $PWD/ui.sif $PWD/Singularity
    singularity instance start --bind ./src:/ui/src $PWD/ui.sif brainlife_ezbids-ui
fi

# # Only need this line below if there's un-commented stuff in the yml file
# singularity-compose --debug up --no-resolv
