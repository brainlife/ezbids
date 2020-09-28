FROM ubuntu:20.04

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && apt install -y parallel nodejs python3 python3-pip tree curl unzip git

#install the latest version of dcm2niix
#RUN curl -fLO https://github.com/rordenlab/dcm2niix/releases/latest/download/dcm2niix_lnx.zip && unzip dcm2niix_lnx.zip && mv dcm2niix /usr/bin
#RUN git clone --branch development https://github.com/rordenlab/dcm2niix.git /dcm2niix && cd /dcm2niix && ./configure && make install

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y build-essential pkg-config cmake git pigz && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y

# Get dcm2niix from github and compile
RUN cd /tmp && \
    git clone https://github.com/rordenlab/dcm2niix.git -b development && \
    cd dcm2niix && mkdir build && cd build && \
    cmake -DBATCH_VERSION=ON -DUSE_OPENJPEG=ON .. && \
    make && make install

RUN pip3 install pandas numpy nilearn matplotlib
