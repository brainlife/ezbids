FROM neurodebian:nd20.04-non-free

ENV DEBIAN_FRONTEND noninteractive
RUN apt update

RUN apt install -y parallel python3 python3-pip tree curl unzip git jq

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y build-essential pkg-config cmake git pigz && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y

#install fsl6
##https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation/Linux
RUN apt update && apt install -y wget python libgl-dev jq python-numpy

#install fsl, but get rid of src
RUN wget https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py && \
      python fslinstaller.py -d /usr/local/fsl -V 6.0.4 && rm -rf /usr/local/fsl/src

ENV FSLDIR=/usr/local/fsl
ENV PATH=$PATH:$FSLDIR/bin
ENV LD_LIBRARY_PATH=$FSLDIR/lib

RUN . $FSLDIR/etc/fslconf/fsl.sh

ENV FSLOUTPUTTYPE=NIFTI_GZ

#make sure fslpython is properly installed
#RUN which imcp

RUN apt install -y curl
RUN curl -fsSL https://deb.nodesource.com/setup_14.x | bash -
RUN apt install -y nodejs

# Get dcm2niix from github and compile
#RUN cd /tmp && \
#    git clone https://github.com/rordenlab/dcm2niix.git -b v1.0.20211006 && \
#    cd dcm2niix && mkdir build && cd build && \
#    cmake -DBATCH_VERSION=ON -DUSE_OPENJPEG=ON .. && \
#    make && make install

RUN wget https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20211006/dcm2niix_lnx.zip -O /tmp/dcm2niix_lnx.zip
#RUN wget https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20220720/dcm2niix_lnx.zip -O /tmp/dcm2niix_lnx.zip
RUN unzip /tmp/dcm2niix_lnx.zip
RUN mv dcm2niix /usr/local/bin

# Get bids-specification from github
RUN cd && git clone https://github.com/bids-standard/bids-specification

#tensorflow2 needs pip>19
#RUN pip3 install --upgrade pip

RUN pip3 install numpy nibabel pandas==1.0.1 matplotlib pyyaml==5.4.1 natsort #need it before I can install quickshear
RUN pip3 install quickshear

#install ROBEX
#COPY ROBEXv12.linux64.tar.gz /
ADD https://www.nitrc.org/frs/download.php/5994/ROBEXv12.linux64.tar.gz//?i_agree=1&download_now=1 /
RUN ls -la
RUN tar -xzf /ROBEXv12.linux64.tar.gz
ENV PATH=$PATH:/ROBEX

#install pydeface
RUN pip3 install pydeface

RUN rm /bin/sh && ln -s /bin/bash /bin/sh

#install bids-validator
RUN npm install -g bids-validator@1.9.6

RUN apt-get install -y rename zstd

WORKDIR /app/handler
RUN npm install -g pm2 #for dev


