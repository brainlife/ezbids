#!/bin/bash

# start server components
pm2 delete ezbids-handler
pm2 start handler.js --name ezbids-handler --watch --ignore-watch="*.log test *.sh ui bin example .git .syncthing*"

pm2 save
