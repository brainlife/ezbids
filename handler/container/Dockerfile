FROM ubuntu:20.04

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && apt install -y parallel nodejs python3 dcm2niix python3-pip

RUN pip3 install pandas numpy nilearn
