**ezBIDS: Cloud-based graphical user interface for automated DICOM to BIDS data ingestion**

**About**
This is the developmental repo for an automated BIDS converter web service that allows users to upload a directory containing 
DICOM files, and analyze the directory structure and sidecars generated from dcm2niix in order to *guess* 
as much information about the data structure as possible. Users will then be asked to verify / modify
those assumption before generating the final BIDS structure.

Unlike other automated DICOM to BIDS converters, ezbids eliminates the need for the command line and setup.

The output can be downloaded back to the user's computer, or sent to other repositories such as
OpenNeuro, or brainlife.io

Due to the plethora of scanner acquisition types, not all are currently supported by ezbids. Priority has therefore been given to acquisition types that are the most common in the neuroimaging community. These include:
1). anat/T1w (including multiecho)
2). anat/T2w
3). anat/FLAIR
4). func/sbref
5). func/bold (including multiecho)
6). fmap/epi
7). fmap/magnitude1
8). fmap/magnitude2
9). fmap/phasediff
10). dwi/dwi

**Usage**
To access the web service, please visit https://brainlife.io/ezbids


### Authors
- [Soichi Hayashi](soichih@gmail.com)
- [Daniel Levitas](dlevitas@iu.edu)
- [Franco Pestilli](pestilli@utexas.edu)

### Funding Acknowledgement
brainlife.io is publicly funded and for the sustainability of the project it is helpful to Acknowledge the use of the platform. We kindly ask that you acknowledge the funding below in your code and publications. Copy and past the following lines into your repository when using this code.

[![NSF-BCS-1734853](https://img.shields.io/badge/NSF_BCS-1734853-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1734853)
[![NSF-BCS-1636893](https://img.shields.io/badge/NSF_BCS-1636893-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1636893)
[![NSF-ACI-1916518](https://img.shields.io/badge/NSF_ACI-1916518-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1916518)
[![NSF-IIS-1912270](https://img.shields.io/badge/NSF_IIS-1912270-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1912270)
[![NIH-NIBIB-R01EB029272](https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg)](https://grantome.com/grant/NIH/R01-EB029272-01)

### Citations
We ask that you the following articles when publishing papers that used data, code or other resources created by the brainlife.io community.

1. Avesani, P., McPherson, B., Hayashi, S. et al. The open diffusion data derivatives, brain data upcycling via integrated publishing of derivatives and reproducible open cloud services. Sci Data 6, 69 (2019). [https://doi.org/10.1038/s41597-019-0073-y](https://doi.org/10.1038/s41597-019-0073-y)

Copyright © 2020 brainlife.io at University of Texas at Austin and Indiana University

