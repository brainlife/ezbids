Bootstrap: docker
From: node:16
Stage: spython-base

%environment
    MONGO_CONNECTION_STRING=mongodb://mongodb:27017/ezbids
    BRAINLIFE_AUTHENTICATION=false
    PORT=8082
    export MONGO_CONNECTION_STRING BRAINLIFE_AUTHENTICATION PORT


%post
    mkdir -p /app
    cd /app
    npm install -g pm2 typescript tsc-watch
    npm install
    

%files
    . /app


%runscript
    # cd /app
    cd /app/api
    exec /bin/bash "$@"


%startscript
    # cd /app
    cd /app/api
    exec /bin/bash "$@"
    ./dev.sh # Need this, right?