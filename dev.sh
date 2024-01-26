#!/usr/bin/env bash

set -ex

BRAINLIFE_AUTHENTICATION=true
while getopts "d" flag; do
 case $flag in
   d)
     BRAINLIFE_AUTHENTICATION=false
   ;;
   \?)
   ;;
 esac
done

export BRAINLIFE_AUTHENTICATION

git submodule update --init --recursive

(cd api && npm install)
(cd ui && npm install)

mkdir -p /tmp/upload
mkdir -p /tmp/workdir

npm run prepare-husky

./generate_keys.sh

# # ok docker compose is now included in docker as an option for docker
# if [[ $(command -v docker-compose) ]]; then 
#     # if the older version is installed use the dash
#     docker-compose up
# else
#     # if the newer version is installed don't use the dash
#     docker compose up
# fi

export SINGULARITY_DISABLE_CACHE=true
export SINGULARITY_CACHEDIR=/tmp

# Approach #1: singularity (individual .sif files)

# Helpful commentary on mongodb container build with Singularity: https://stackoverflow.com/questions/70746228/singularity-mongodb-container-in-background-mode
if [ ! -d $PWD/data/db ]; then
    mkdir -p $PWD/data/db
    chmod -R 777 $PWD/data/db
fi

if [ ! -f $PWD/mongodb/mongodb.sif ]; then # Will eventually be redundant and can remove
    echo "building mongodb"
    # build image
    singularity build           \
      --arch "amd64"            \
      --fakeroot                \
      --disable-cache           \
      $PWD/mongodb/mongodb.sif  \
      $PWD/mongodb/Singularity
    
#     # start the container instance
#     singularity instance start  \
#       --fakeroot                \
#       --bind $PWD/data/db:/data/db \
#       --net \
#       --network-args "portmap=27417:27017/tcp"  \
#       $PWD/mongodb/mongodb.sif  \
#       brainlife_ezbids-mongodb
#     # singularity run instance://brainlife_ezbids-mongodb # This seems to run mongodb in the foreground, meaning can't move on to building other containers.
fi

# if [ ! -f $PWD/api/api.sif ]; then
#     echo "building api"
#     singularity build --arch "amd64" --fakeroot --disable-cache $PWD/api/api.sif Singularity
#     singularity instance start --bind /tmp:/tmp --bind ./api:/app/api --env BRAINLIFE_AUTHENTICATION=${BRAINLIFE_AUTHENTICATION} $PWD/api/api.sif brainlife_ezbids-api
#     # Does --env actually work?
# fi

# if [ ! -f $PWD/handler/handler.sif ]; then
#     echo "building handler"
#     singularity build --arch "amd64" --fakeroot --disable-cache $PWD/handler/handler.sif $PWD/handler/Singularity
#     singularity instance start --bind /tmp:/tmp --bind .:/app $PWD/handler/handler.sif brainlife_ezbids-handler
# fi

# if [ ! -f $PWD/ui/ui.sif ]; then
#     echo "building ui"
#     singularity build --arch "amd64" --fakeroot --disable-cache $PWD/ui/ui.sif $PWD/ui/Singularity
#     singularity instance start --bind ./ui/src:/ui/src --env VITE_BRAINLIFE_AUTHENTICATION=${BRAINLIFE_AUTHENTICATION} $PWD/ui/ui.sif brainlife_ezbids-ui
#     # Does --env actually work? Don't see VITE_BRAINLIFE_AUTHENTICATION env variable inside container
# fi



# # Approach #2: singularity-compose 

# if [ ! -d $PWD/data/db ]; then
#     mkdir -p $PWD/data/db
#     chmod -R 777 $PWD/data/db
# fi
# singularity-compose --debug up --no-resolv
