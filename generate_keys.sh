#!/bin/bash

set -ex

if [ ! -f api/ezbids.key ]; then
  openssl genrsa -out api/ezbids.key 2048
  chmod 600 api/ezbids.key
  openssl rsa -in api/ezbids.key -pubout > api/ezbids.pub
fi