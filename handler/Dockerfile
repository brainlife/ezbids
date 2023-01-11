FROM neurodebian:nd20.04-non-free

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt-get update && apt-get upgrade -y

RUN apt install -y parallel python3 python3-pip tree curl unzip git jq python libgl-dev python-numpy
RUN pip3 install numpy==1.23.0 nibabel pandas==1.0.1 matplotlib pyyaml==5.4.1 natsort pydeface && \
    pip3 install quickshear

RUN apt-get install -y build-essential pkg-config cmake git pigz rename zstd libopenjp2-7 wget && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y

#this is the most tedious that's why it's one of the first layers installed
#install fsl, and get rid of src
# RUN wget https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py && \
#       python fslinstaller.py -d /usr/local/fsl -V 6.0.6 && rm -rf /usr/local/fsl/src

RUN mkdir -p /usr/local/fsl/bin && \
    mkdir -p /usr/local/fsl/lib && \
    git clone https://github.com/dlevitas/FSL_binaries /usr/local/fsl/bin && \
    rm -rf /usr/local/fsl/bin/README.md

ENV FSLDIR=/usr/local/fsl
ENV PATH=$PATH:$FSLDIR/bin
ENV LD_LIBRARY_PATH=$FSLDIR/lib
# RUN . $FSLDIR/etc/fslconf/fsl.sh

ENV FSLOUTPUTTYPE=NIFTI_GZ

# #make sure fslpython is properly installed
# RUN which imcp

# certs have expired for nodesource use the hack below to get around that for install
#### HACK Warning ####
# unfortuanetly this seems to work the most reliably
# see https://github.com/nodesource/distributions/issues/1266#issuecomment-938408547 and
RUN echo "insecure" > $HOME/.curlrc \
    && echo "Acquire::https::Verify-Peer false;" >> /etc/apt/apt.conf.d/80ssl-exceptions \ 
    && echo "Acquire::https::Verify-Host false;" >> /etc/apt/apt.conf.d/80ssl-exceptions \
    && curl -fsSL https://deb.nodesource.com/setup_14.x | bash - \
    && apt install -y nodejs \ 
    && rm -f $HOME/.curlrc \
    && rm -f /etc/apt/apt.conf.d/80ssl-exceptions \
    && npm --version

RUN wget https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20220720/dcm2niix_lnx.zip -O /tmp/dcm2niix_lnx.zip && \
    unzip /tmp/dcm2niix_lnx.zip && \
    mv dcm2niix /usr/local/bin

# Get bids-specification from github
RUN cd && git clone https://github.com/bids-standard/bids-specification

#install ROBEX
ADD https://www.nitrc.org/frs/download.php/5994/ROBEXv12.linux64.tar.gz//?i_agree=1&download_now=1 /
RUN tar -xzf /ROBEXv12.linux64.tar.gz
ENV PATH /ROBEX:$PATH

ENV NODE_PATH $NVM_DIR/v$NODE_VERSION/lib/node_modules
ENV PATH $NVM_DIR/v$NODE_VERSION/bin:$PATH

#install bids-validator
RUN npm install -g bids-validator@1.9.6

# install source code from local
WORKDIR /app/handler
RUN npm -g install pm2
