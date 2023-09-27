#!/usr/bin/env bash

set -ex

git submodule update --init --recursive

# export UID=$(id -u)
export UID
export GID=$(id -g)

# ok docker compose is now included in docker as an option for docker
if [[ $(command -v docker-compose) ]]; then 
    # if the older version is installed use the dash
    docker-compose up
else
    # if the newer version is installed don't use the dash
    docker compose up
fi
