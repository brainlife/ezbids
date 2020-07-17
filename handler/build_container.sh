set -x
set -e

docker build -t brainlife/ezbids-handler container
docker tag brainlife/ezbids-handler brainlife/ezbids-handler:1.1
docker push brainlife/ezbids-handler
