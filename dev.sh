#!/usr/bin/env bash

set -ex

git submodule update --init --recursive

(cd api && npm install)
(cd ui && npm install)

mkdir -p /tmp/upload
mkdir -p /tmp/workdir

npm run prepare-husky

# # ok docker compose is now included in docker as an option for docker
# if [[ $(command -v docker-compose) ]]; then 
#     # if the older version is installed use the dash
#     docker-compose up
# else
#     # if the newer version is installed don't use the dash
#     docker compose up
# fi

# Use singularity-compose instead of docker-compose
singularity-compose --debug up --read_only --no-resolv
