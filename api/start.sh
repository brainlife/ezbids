#!/bin/bash

# start server components

pm2 delete ezbids-api
pm2 start ezbids.js --name ezbids-api --watch --ignore-watch="*.log test *.sh ui bin example .git"

pm2 delete ezbids-tsc
pm2 start tsc.sh --name ezbids-tsc

pm2 save
