#!/bin/bash

# start server components

#nohup tsc --watch > tsc.log &
pm2 delete easybids-api-tsc
pm2 start tsc.sh --name easybids-api-tsc

pm2 delete easybids-api
pm2 start easybids.js --name easybids-api --watch --ignore-watch="*.log test *.sh ui bin example .git"

pm2 delete easybids-preprocess
pm2 start bin/preprocess.js --name easybids-preprocess --watch --ignore-watch="*.log test *.sh ui bin example .git"

pm2 save
