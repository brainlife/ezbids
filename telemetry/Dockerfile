FROM neurodebian:nd20.04-non-free

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt-get update && apt-get upgrade -y
    
RUN apt install -y parallel python3 python3-pip tree curl unzip git jq python libgl-dev python-numpy
RUN pip3 install --upgrade pip
RUN pip3 install conversiontelemetry
COPY telemetry.env /root/.telemetry.env

ENTRYPOINT [ "start-telemetry" ]