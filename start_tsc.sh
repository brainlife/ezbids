#!/bin/bash

# start server components

#nohup tsc --watch > tsc.log &
pm2 delete ezbids-tsc
pm2 start tsc.sh --name ezbids-tsc

pm2 save
