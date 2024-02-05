Bootstrap: docker
From: node:16
Stage: spython-base

%environment
    MONGO_CONNECTION_STRING=mongodb://mongodb:27017/ezbids
    BRAINLIFE_AUTHENTICATION=false
    SINGULARITY_PWD=/app/api  # Not sure this is being properly set (or at least adhered to)
    PORT=8082
    export MONGO_CONNECTION_STRING BRAINLIFE_AUTHENTICATION PORT SINGULARITY_PWD


%post
    mkdir -p /app
    cd /app

    npm install -g pm2 typescript tsc-watch
    npm install

    cd /app/api
    echo "Current working directory: $PWD"
    ./dev.sh

%files
    . /app

%test
    # curl -f http://localhost:8082/health