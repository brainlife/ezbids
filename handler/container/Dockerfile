FROM ubuntu:20.04

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && apt install -y parallel nodejs python3 python3-pip tree

#install the latest version of dcm2niix
RUN apt install -y curl unzip
RUN curl -fLO https://github.com/rordenlab/dcm2niix/releases/latest/download/dcm2niix_lnx.zip && unzip dcm2niix_lnx.zip && mv dcm2niix /usr/bin

RUN pip3 install pandas numpy nilearn matplotlib
