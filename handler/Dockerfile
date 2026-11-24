FROM neurodebian:nd20.04-non-free

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt-get update && apt-get upgrade -y

RUN apt install -y parallel python3 python3-pip tree curl unzip git jq libgl-dev bc

# python packages: handler/requirements.txt (the list the desktop python runtime uses) except pypet2bids,
# plus pydeface/quickshear (handler/deface.sh); pypet2bids from master's tested PET2BIDS commit pin
COPY requirements.txt /tmp/requirements.txt
RUN grep -v '^pypet2bids' /tmp/requirements.txt > /tmp/requirements-docker.txt && \
    pip3 install -r /tmp/requirements-docker.txt && pip3 install pydeface quickshear

# Install pypet2bids
# pinned: PET2BIDS moved to uv (no more installpoetry target); this is the last commit before 2024-08-28
RUN git clone https://github.com/openneuropet/PET2BIDS && \
    cd PET2BIDS && git checkout 1c22d17 && make installpoetry buildpackage installpackage

RUN apt-get install -y build-essential pkg-config cmake git pigz rename zstd libopenjp2-7 libgdcm-tools wget libopenblas-dev && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y


RUN touch /.pet2bidsconfig && chown 1001:1001 /.pet2bidsconfig
RUN echo "DEFAULT_METADATA_JSON=/usr/local/lib/python3.8/dist-packages/pypet2bids/template_json.json" > /.pet2bidsconfig

#this is the most tedious that's why it's one of the first layers installed
#install fsl, and get rid of src
# RUN wget https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py && \
#       python fslinstaller.py -d /usr/local/fsl -V 6.0.6 && rm -rf /usr/local/fsl/src

RUN mkdir -p /usr/local/fsl && \
    git clone https://github.com/dlevitas/FSL_binaries /usr/local/fsl && \
    rm -rf /usr/local/fsl/README.md && \
    mkdir -p /usr/local/fsl/data/standard && \
    mv /usr/local/fsl/bin/MNI152_T1_2mm_brain.nii.gz /usr/local/fsl/data/standard && \
    ln -sf /usr/bin/python3 /usr/local/fsl/bin/fslpython
# The fslpython in FSL_binaries is a bare conda-forge python 3.8 binary without its own stdlib, so it
# falls back to Debian's /usr/lib/python3.8, which has no math extension module (Debian builds it in).
# tmpnam (#!/usr/bin/env fslpython) then fails and fslreorient2std writes its temporary matrix to
# ./_nii.mat in the shared working directory, where parallel deface jobs can overwrite or delete each other's.
# tmpnam only needs the standard library, so fslpython is the system python3 (also 3.8).

ENV FSLDIR=/usr/local/fsl
ENV PATH=$PATH:$FSLDIR/bin
# ENV LD_LIBRARY_PATH=$FSLDIR/lib
# RUN . $FSLDIR/etc/fslconf/fsl.sh

ENV FSLOUTPUTTYPE=NIFTI_GZ

# #make sure fslpython is properly installed
# RUN which imcp

# # certs have expired for nodesource use the hack below to get around that for install
# #### HACK Warning ####
# # unfortuanetly this seems to work the most reliably
# # see https://github.com/nodesource/distributions/issues/1266#issuecomment-938408547 and
# RUN echo "insecure" > $HOME/.curlrc \
#     && echo "Acquire::https::Verify-Peer false;" >> /etc/apt/apt.conf.d/80ssl-exceptions \ 
#     && echo "Acquire::https::Verify-Host false;" >> /etc/apt/apt.conf.d/80ssl-exceptions \
#     && curl -fsSL https://deb.nodesource.com/setup_14.x | bash - \
#     && apt install -y nodejs \ 
#     && rm -f $HOME/.curlrc \
#     && rm -f /etc/apt/apt.conf.d/80ssl-exceptions \
#     && npm --version

RUN apt-get update \
    && apt-get install -y ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg

ARG NODE_MAJOR=20
RUN echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list

RUN apt-get update \
    && apt-get install nodejs -y

# dcm2niix pinned to an exact release (its BidsGuess and sidecars change between releases);
# to update, change both ARGs: the sha256 is the release asset digest shown on GitHub
ARG DCM2NIIX_VERSION=v1.0.20261029
ARG DCM2NIIX_ZIP_SHA256=decc03fe9c08e696700876bd0e28fbc1dda5be11979905dfa5a5e01063cdf758
RUN cd /tmp && curl -fL -o dcm2niix_lnx.zip https://github.com/rordenlab/dcm2niix/releases/download/${DCM2NIIX_VERSION}/dcm2niix_lnx.zip \
    && echo "${DCM2NIIX_ZIP_SHA256}  /tmp/dcm2niix_lnx.zip" | sha256sum -c - \
    && unzip /tmp/dcm2niix_lnx.zip \
    && mv dcm2niix /usr/local/bin && rm /tmp/dcm2niix_lnx.zip

# Don't need, unless there's a reason for having the development branch ahead of scheduled release
# RUN git clone --branch development https://github.com/rordenlab/dcm2niix.git \
#     && cd dcm2niix/console \
#     && make \
#     && mv dcm2niix /usr/local/bin

# Get bids-specification from github
RUN cd && git clone https://github.com/bids-standard/bids-specification

#install ROBEX
ADD https://www.nitrc.org/frs/download.php/5994/ROBEXv12.linux64.tar.gz//?i_agree=1&download_now=1 /
RUN tar -xzf /ROBEXv12.linux64.tar.gz
ENV PATH /ROBEX:$PATH

ENV NODE_PATH $NVM_DIR/v$NODE_VERSION/lib/node_modules
ENV PATH $NVM_DIR/v$NODE_VERSION/bin:$PATH

#install bids-validator
RUN npm install -g npm@9.5.1
RUN npm install -g bids-validator@1.14.8
RUN git clone https://github.com/bids-standard/bids-validator

# The TypeScript handler (handler/*.ts) looks for its tools in the desktop bundle layout:
# $EZBIDS_BIN_DIR/<tool>/<tool>-<platform>-<arch>. Without $EZBIDS_BIN_DIR/python-runtime it uses this image's python3.
ENV EZBIDS_BIN_DIR=/opt/ezbids-bin EZBIDS_PLATFORM=linux EZBIDS_ARCH=amd64
ENV EZBIDS_TEMPLATE_DIR=/app/handler/templates
ENV BIDS_VALIDATOR_PATH=/usr/lib/node_modules/bids-validator/bin/bids-validator
RUN mkdir -p $EZBIDS_BIN_DIR/dcm2niix $EZBIDS_BIN_DIR/7z $EZBIDS_BIN_DIR/allineate && \
    ln -s /usr/local/bin/dcm2niix $EZBIDS_BIN_DIR/dcm2niix/dcm2niix-linux-amd64

# 7-Zip (expand step): the same release asset the desktop app ships (brainlife/ezbids-binaries)
ARG EZBIDS_BINARIES_TAG=v0.0.5
ARG SEVENZ_SHA256=57b73a4bf122b8d7e69c4c04a478f258b03f1515feebe1e70f190432710b3a3b
RUN curl -fsSL -o $EZBIDS_BIN_DIR/7z/7z-linux-amd64 \
        https://github.com/brainlife/ezbids-binaries/releases/download/${EZBIDS_BINARIES_TAG}/7z-linux-amd64 && \
    echo "${SEVENZ_SHA256}  $EZBIDS_BIN_DIR/7z/7z-linux-amd64" | sha256sum -c - && \
    chmod +x $EZBIDS_BIN_DIR/7z/7z-linux-amd64

# allineate (deface step): the release binary needs glibc 2.34 (this image has 2.31), so it is compiled here
# from the commit brainlife/ezbids-binaries pins (scripts/build/allineate.sh, same flags)
ARG ALLINEATE_REF=dd250449d46752f84761657fbaf0fb26c8aaf20e
RUN apt-get update && apt-get install -y zlib1g-dev && \
    cd /tmp && curl -fsSL -o allineate.tgz https://github.com/neurolabusc/allineate/archive/${ALLINEATE_REF}.tar.gz && \
    tar -xzf allineate.tgz && cd allineate-${ALLINEATE_REF} && \
    gcc -O3 -ffast-math -DHAVE_ZLIB main.c allineate.c nifti_io.c powell_newuoa.c -lz -lm \
        -o $EZBIDS_BIN_DIR/allineate/allineate-linux-amd64 && \
    cd /tmp && rm -rf allineate.tgz allineate-${ALLINEATE_REF} && apt-get clean -y

# install source code from local
WORKDIR /app/handler
RUN npm -g install pm2
