Bootstrap: docker
From: node:16
Stage: spython-base

%files
    . /app

%post
    mkdir -p /app
    cd /app
    npm install -g pm2 typescript tsc-watch
    npm install

%runscript
    cd /app
    exec /bin/bash "$@"

%startscript
    cd /app
    exec /bin/bash "$@"