#!/usr/bin/env bash

# check to see if a .env file exists
if [ -f .env ]; then
    echo ".env file exists, loading environment variables from .env file"
else
    echo ".env file does not exist, copying example.env to .env"
    cp example.env .env
fi

# load the environment variables from the .env file
source .env

echo "Setting Environment Variables from .env file:"
# display the environment variables read in from .env, could be a gotcha if 
# the user is unclear about if the .env variables are being used. The .env variables
# will override environment variables set in the shell as they're set once this script 
# is run.
while read line
do
  # if line does not start with # then echo the line
  if [[ $line != \#* ]]; then
    if [[ $line != "" ]]; then
      echo "    ${line}"
    fi
  fi
done < .env

if [ $BRAINLIFE_DEVELOPMENT == true ]; then
  # build local changes and mount them directly into the containers
  # api/ and ui/ are mounted as volumes  at /app within the docker-compose.yml
  (cd api && npm install)
  (cd ui && npm install)
  # enable or disable debugging output
  set -ex
else
  set -e
fi

# update the bids submodule
git submodule update --init --recursive

# The main differences between the production and development docker-compose files are that the production
# files uses https and the development file uses http. The production file also uses a different nginx.conf
if [[ $BRAINLIFE_PRODUCTION == true ]]; then
  DOCKER_COMPOSE_FILE=docker-compose-production.yml
else
  DOCKER_COMPOSE_FILE=docker-compose.yml
fi

mkdir -p /tmp/upload
mkdir -p /tmp/workdir

#npm run prepare-husky

./generate_keys.sh

# ok docker compose is now included in docker as an option for docker
if [[ $(command -v docker-compose) ]]; then 
    # if the older version is installed use the dash
    docker-compose --file ${DOCKER_COMPOSE_FILE} up
else
    # if the newer version is installed don't use the dash
    docker compose --file ${DOCKER_COMPOSE_FILE} up
fi
