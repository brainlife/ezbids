#!/usr/bin/env bash

BRAINLIFE_PRODUCTION=false
BRAINLIFE_AUTHENTICATION=false
BRAINLIFE_DEVELOPMENT=false
HOST_LOCAL_TELEMETRY=false
while getopts "padth" flag; do
 case $flag in
  p)
    BRAINLIFE_PRODUCTION=true
  ;;
  a)
    BRAINLIFE_AUTHENTICATION=true
  ;;
  d)
    BRAINLIFE_DEVELOPMENT=true
  ;;
  t)
    HOST_LOCAL_TELEMETRY=true
  ;;
  h)
    echo "Usage: dev.sh [-p] [-a] [-d] [-h]"
    echo "  -p: Set the BRAINLIFE_PRODUCTION environment variable to true and use https"
    echo "      (this will launch the server on port 443) and run with nginx/production_nginx.conf"
    echo "      the following files are required for https to work:" 
    echo "        nginx/ssl/sslcert.cert"
    echo "        nginx/ssl/sslcert.key"
    echo "        nginx/ssl/sslpassword"
    echo "      for https to work"
    echo "      defaults to running nginx/development_nginx.conf on port 80"
    echo "  -a: Set the BRAINLIFE_AUTHENTICATION environment variable to true, if you're not running"
    echo "      this with brainlife don't use."
    echo "  -d: Set the BRAINLIFE_DEVELOPMENT enables additional debugging output, default is false"
    echo "  -t: Collect telemetry data and store it locally using the telemetry container"
    echo "  -h: Display this help message"
    exit 0
  ;;
  \?)
  ;;
 esac
done

if [ $BRAINLIFE_DEVELOPMENT == true ]; then
  set -ex
else
  set -e
fi

# check to see if a .env file exists
if [ -f .env ]; then
    echo ".env file exists, loading environment variables from .env file"
else
    echo ".env file does not exist, copying example.env to .env"
    cp .env.example .env
fi

echo "Setting Environment:"
echo "    BRAINLIFE_PRODUCTION=${BRAINLIFE_PRODUCTION}"
echo "    BRAINLIFE_AUTHENTICATION=${BRAINLIFE_AUTHENTICATION}"

export BRAINLIFE_PRODUCTION
export BRAINLIFE_AUTHENTICATION

# display the environment variables read in from .env
while read line
do
  # if line does not start with # then echo the line
  if [[ $line != \#* ]]; then
    if [[ $line != "" ]]; then
      echo "    ${line}"
    fi
  fi
done < .env

git submodule update --init --recursive


if [[ $BRAINLIFE_PRODUCTION == true ]]; then
  continue
else
  (cd api && npm install)
  (cd ui && npm install)
fi

mkdir -p /tmp/upload
mkdir -p /tmp/workdir

#npm run prepare-husky

./generate_keys.sh

# ok docker compose is now included in docker as an option for docker
if [[ $(command -v docker-compose) ]]; then 
    # if the older version is installed use the dash
    docker-compose up
else
    # if the newer version is installed don't use the dash
    docker compose up
fi
