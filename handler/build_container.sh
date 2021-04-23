set -x
set -e
#docker pull neurodebian:nd20.04-non-free

docker build -t brainlife/ezbids-handler container
docker tag brainlife/ezbids-handler brainlife/ezbids-handler:3.3
docker push brainlife/ezbids-handler
