#FROM ubuntu:20.04
FROM neurodebian:nd20.04-non-free

ENV DEBIAN_FRONTEND noninteractive

RUN apt update && apt install -y parallel nodejs python3 python3-pip tree curl unzip git

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
RUN pip3 install --upgrade pip

RUN pip3 install pandas numpy nilearn matplotlib tensorflow keras deepdefacer[tf_cpu]

#install fsl
#RUN apt install -y fsl python-numpy
#ENV FSLDIR=/usr/share/fsl/5.0
#ENV PATH=$PATH:$FSLDIR/bin
#ENV LD_LIBRARY_PATH=/usr/lib/fsl/5.0:/usr/share/fsl/5.0/bin
#ENV FSLBROWSER=/etc/alternatives/x-www-browser
#ENV FSLCLUSTER_MAILOPTS=n
#ENV FSLLOCKDIR=
#ENV FSLMACHINELIST=
#ENV FSLMULTIFILEQUIT=TRUE
#ENV FSLOUTPUTTYPE=NIFTI_GZ
#ENV FSLREMOTECALL=
#ENV FSLTCLSH=/usr/bin/tclsh
#ENV FSLWISH=/usr/bin/wish
#ENV POSSUMDIR=/usr/share/fsl/5.0

