FROM neurodebian:nd22.04-non-free

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt-get update && apt-get upgrade -y

# RUN apt install -y parallel python3 python3-pip tree curl unzip git jq libgl-dev python-numpy (orig)
RUN apt install -y parallel python3 python3-pip tree curl unzip git jq libgl-dev

RUN pip3 install numpy nibabel pandas matplotlib pyyaml pydicom natsort pydeface && \
    pip3 install quickshear mne mne-bids

# Install eye2bids for eyetracking
RUN git clone https://github.com/bids-standard/eye2bids.git && \
    cd eye2bids && \
    pip3 install .

# Install edf2asc function from EyeLink Developers Kit (needed by eye2bids for EyeLink data)
RUN git clone https://github.com/dlevitas/edf2asc /tmp/edf2asc && \
    cp -r /tmp/edf2asc/edf2asc /usr/local/bin && \
    chmod +x /usr/local/bin/edf2asc
# RUN add-apt-repository universe && \
#     apt update && \
#     apt install ca-certificates && \
#     apt-key adv --fetch-keys https://apt.sr-research.com/SRResearch_key && \
#     add-apt-repository 'deb [arch=amd64] https://apt.sr-research.com SRResearch main' && \
#     apt update && \
#     apt install eyelink-display-software

# Install pypet2bids
RUN git clone https://github.com/openneuropet/PET2BIDS && \
    cd PET2BIDS && make installpoetry buildpackage installpackage

RUN apt-get install -y build-essential pkg-config cmake git pigz rename zstd libopenjp2-7 libgdcm-tools wget libopenblas-dev && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y


RUN touch /.pet2bidsconfig && chown 1001:1001 /.pet2bidsconfig
RUN echo "DEFAULT_METADATA_JSON=/usr/local/lib/python3.10/dist-packages/pypet2bids/template_json.json" > /.pet2bidsconfig

# Install FSL
#this is the most tedious that's why it's one of the first layers installed
#install fsl, and get rid of src
# RUN wget https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py && \
#       python fslinstaller.py -d /usr/local/fsl -V 6.0.6 && rm -rf /usr/local/fsl/src

RUN mkdir -p /usr/local/fsl && \
    git clone https://github.com/dlevitas/FSL_binaries /usr/local/fsl && \
    rm -rf /usr/local/fsl/README.md

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

ARG NODE_MAJOR=16
RUN echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list

RUN apt-get update \
    && apt-get install nodejs -y

RUN cd /tmp && curl -fLO https://github.com/rordenlab/dcm2niix/releases/latest/download/dcm2niix_lnx.zip \
    && unzip /tmp/dcm2niix_lnx.zip \
    && mv dcm2niix /usr/local/bin

# Don't need, unless there's a reason for having the development branch ahead of scheduled release
# RUN git clone --branch development https://github.com/rordenlab/dcm2niix.git \
#     && cd dcm2niix/console \
#     && make \
#     && mv dcm2niix /usr/local/bin

# Install bids-specification from github
RUN cd && git clone https://github.com/bids-standard/bids-specification

# Install ROBEX
ADD https://www.nitrc.org/frs/download.php/5994/ROBEXv12.linux64.tar.gz//?i_agree=1&download_now=1 /
RUN tar -xzf /ROBEXv12.linux64.tar.gz
ENV PATH /ROBEX:$PATH

ENV NODE_PATH $NVM_DIR/v$NODE_VERSION/lib/node_modules
ENV PATH $NVM_DIR/v$NODE_VERSION/bin:$PATH

# Install bids-validator
RUN npm install -g bids-validator@1.11.0
RUN git clone https://github.com/bids-standard/bids-validator

# Install source code from local
WORKDIR /app/handler
RUN npm -g install pm2
