set -x
set -e

docker build -t brainlife/ezbids-handler container
docker tag brainlife/ezbids-handler brainlife/ezbids-handler:3.6

#let's just build the container on each host.. too big
#docker push brainlife/ezbids-handler:3.6
