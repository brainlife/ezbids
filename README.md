# ezBIDS

The secure, cloud-based service for the semi-automated mapping of entire sessions of neuroimaging data to the Brain Imaging Data Structure ([BIDS](https://bids.neuroimaging.io/)) standard.  

<img width="1450" alt="Screenshot 2023-11-01 at 11 50 48 AM" src="https://github.com/brainlife/ezbids/assets/2119795/2c054297-1503-4ebb-8718-336012c80b48">

### About

This is the development repository for a semi-supervised neuroimaging data files to [BIDS](https://bids.neuroimaging.io/) conversion web service. The web service is hosted securely at [brainlife.io/ezbids](https://brainlife.io/ezbids).

Unlike other BIDS converters, ezBIDS eliminates the need for code, and command line interfaces and automatically generates heuristic and configuration files (called ezBIDS Templates).

An inferential process analyzes the directory structure and sidecars of the data uploaded to provide a *first guess* about the data types and content. A web-browser user interface presents the users with a *first guess* mapping of the uploaded data files into a BIDS structure. Finally, users provided with the opportunity to verify the *first guess* and modify the information provided as needed so as to best match the final BIDS structure. 

Data from all major scanner vendors can be directly uploaded to ezBIDS. ezBIDS provides options for the defacing of anatomical acquisitions.

The BIDS output can be downloaded back to the user's computer, or uploaded to open repositories such as
[brainlife.io](https://brainlife.io/), or in the future, [OpenNeuro.org](https://openneuro.org/).

Helpful links:
1. [ezBIDS website](https://brainlife.io/ezbids) (Chrome or Firefox browser preferred)
2. [ezBIDS tutorial](https://brainlife.io/docs/tutorial/ezBIDS/)
3. [ezBIDS tutorial video](https://www.youtube.com/embed/L8rWA8qgnpo)
4. [ezBIDS user documentation](https://brainlife.io/docs/using_ezBIDS/)

### Usage
To access the ezBIDS web service, please visit https://brainlife.io/ezbids

Users do not need to organize their uploaded data in any specific manner, so long as the data is non-anonymized. The uploaded data can contain any number of sub-folders, and users and may compress (e.g. zip, tar) their upload directory if users so choose. ezBIDS permits two types of data uploads:

1. **DICOM files** - Only DICOMs should be included in the upload. No specific organizational structure is required.
2. **dcm2niix generated output (i.e. NIfTI, json, bval, and bvec) files** - Only these files (no DICOMs) should be included in the upload. We strongly recommend that the dcm2niix output not be anonymized (i.e. include _-ba n_ in the dcm2niix command), in which case, no specific organizational structure is required.

Should users feel the need to anonymize their data before uploading, we strongly recommend that subjects (and sessions) be organized into subject (and session) folders, with explicit labeling of the subject (and session) IDs (e.g. _/MRI_data/sub-01/ses-01/DICOMS_). Failure to do so for non-anonymized data will result in additional work.

### Authors
-   [Daniel Levitas](djlevitas208@gmail.com)*
-   [Soichi Hayashi](soichih@gmail.com)*
-   [Sophia Vinci-Booher](sophia.vinci-booher@vanderbilt.edu)
-   [Anibal Heinsfeld](anibalsolon@utexas.edu)
-   [Dheeraj Bhatia](dheeraj.bhatia@utexas.edu)
-   [Nicholas Lee](niconal902@gmail.com)
-   [Anthony Galassi](niconal902@gmail.com)
-   [Guiomar Niso](guiomar.niso@ctb.upm.es)
-   [Franco Pestilli](pestilli@utexas.edu)
* Both authors contributed equally to this work

### Funding Acknowledgement

brainlife.io is publicly funded and for the sustainability of the project it is helpful to Acknowledge the use of the platform. We kindly ask that you acknowledge the funding below in your code and publications. Copy and past the following lines into your repository when using this code.

[![NSF-BCS-1734853](https://img.shields.io/badge/NSF_BCS-1734853-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1734853)
[![NSF-BCS-1636893](https://img.shields.io/badge/NSF_BCS-1636893-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1636893)
[![NSF-ACI-1916518](https://img.shields.io/badge/NSF_ACI-1916518-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1916518)
[![NSF-IIS-1912270](https://img.shields.io/badge/NSF_IIS-1912270-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1912270)
[![NIH-NIBIB-R01EB029272](https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg)](https://grantome.com/grant/NIH/R01-EB029272-01)
[![NIH-NIMH-R01MH126699]](https://img.shields.io/badge/NIH_NIMH-R01MH126699-green.svg)](https://grantome.com/grant/NIH/R01-EB029272)

### Citations

Please use the following citation when using ezBIDS:

Levitas, Daniel, et al. "ezBIDS: Guided standardization of neuroimaging data interoperable with major data archives and platforms." [Article](https://www.nature.com/articles/s41597-024-02959-0).


Copyright © 2022 brainlife.io at University of Texas at Austin
