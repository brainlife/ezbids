set -x
set -e

docker build -t brainlife/ezbids-handler container
docker tag brainlife/ezbids-handler brainlife/ezbids-handler:3.5
#docker push brainlife/ezbids-handler
