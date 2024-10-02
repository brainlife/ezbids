#! /usr/bin/env bash

# If we're in production we want to build the ui and allow nginx to serve the files, 
# otherwise we run npm install which will create a ui page and use vite to serve it
# in "development" mode
if [ $BRAINLIFE_PRODUCTION == true ]; then
  npm run build
else
  npm run dev
fi