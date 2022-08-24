#!/bin/bash

tsc --watch &
pm2 start ezbids.js --attach --watch --ignore-watch="*.log test *.sh ui bin example .git **/*.ts"
