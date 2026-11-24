FROM neurodebian:nd20.04-non-free

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt-get update && apt-get upgrade -y

RUN apt install -y parallel python3 python3-pip tree curl unzip git jq python libgl-dev python-numpy bc

RUN pip3 install numpy==1.23.0 nibabel==4.0.0 pandas matplotlib pyyaml==5.4.1 pydicom==2.3.1 natsort pydeface && \
    pip3 install quickshear mne mne-bids

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
    mv /usr/local/fsl/bin/MNI152_T1_2mm_brain.nii.gz /usr/local/fsl/data/standard

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

# install source code from local
WORKDIR /app/handler
RUN npm -g install pm2
