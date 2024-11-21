#!/usr/bin/env bash

set -ex

BRAINLIFE_AUTHENTICATION=false
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

# ok docker compose is now included in docker as an option for docker
if [[ $(command -v docker-compose) ]]; then 
    # if the older version is installed use the dash
    docker-compose --profile development up
else
    # if the newer version is installed don't use the dash
    docker compose --profile development up
fi
