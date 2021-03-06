#FROM ubuntu:20.04
FROM neurodebian:nd20.04-non-free

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && apt install -y parallel nodejs python3 python3-pip tree curl unzip git jq

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y build-essential pkg-config cmake git pigz && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y

# Get dcm2niix from github and compile
RUN cd /tmp && \
    git clone https://github.com/rordenlab/dcm2niix.git -b v1.0.20201102 && \
    cd dcm2niix && mkdir build && cd build && \
    cmake -DBATCH_VERSION=ON -DUSE_OPENJPEG=ON .. && \
    make && make install

#tensorflow2 needs pip>19
#RUN pip3 install --upgrade pip

RUN pip3 install numpy nibabel pandas matplotlib #need it before I can install quickshear
RUN pip3 install quickshear

#install ROBEX
COPY ROBEXv12.linux64.tar.gz /
RUN tar -xzf /ROBEXv12.linux64.tar.gz
ENV PATH=$PATH:/ROBEX

#install fsl6
#https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation/Linux
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
RUN which imcp

ADD fsl5 /usr/local/fsl5
ENV PATH=/usr/local/fsl5:$PATH

#install pydeface
RUN pip3 install pydeface

RUN rm /bin/sh && ln -s /bin/bash /bin/sh

#install bids-validator
RUN apt-get install -y npm 
RUN npm install -g bids-validator

