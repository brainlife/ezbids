#!/bin/bash

# save config for red so we can print out a red error
RED='\033[0;31m'

tsc-watch --onSuccess "pm2 start ezbids.js --attach --watch --ignore-watch=\"*.log test *.sh ui bin example .git **/*.ts\"" \
          --onFailure "echo -e ${RED}URGENT: TRANSPILE TO JAVASCRIPT FAILED!"