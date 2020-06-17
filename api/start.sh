#!/bin/bash

# start server components

#nohup tsc --watch > tsc.log &
#pm2 delete ezbids-api-tsc
#pm2 start tsc.sh --name ezbids-api-tsc

pm2 delete ezbids-api
pm2 start ezbids.js --name ezbids-api --watch --ignore-watch="*.log test *.sh ui bin example .git"

pm2 save
