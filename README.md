# ezBIDS

The secure, cloud-based service for the semi-automated mapping of entire sessions of neuroimaging data to the Brain Imaging Data Structure ([BIDS](https://bids.neuroimaging.io/)) standard.  

<img width="1450" alt="Screenshot 2023-11-01 at 11 50 48 AM" src="https://github.com/brainlife/ezbids/assets/2119795/2c054297-1503-4ebb-8718-336012c80b48">

### About

This is the repository for a semi-supervised web-service for converting neuroimaging data files to [BIDS](https://bids.neuroimaging.io/). The web service is securely hosted at [brainlife.io/ezbids](https://brainlife.io/ezbids). For additional details on security feaures, please see [here](https://brainlife.io/docs/using_ezBIDS/#faq).

Unlike other BIDS converters, ezBIDS eliminates the need for coding and command line interfaces (CLI), doing the bulk of the work behind the scenes to save users time. Importantly, ezBIDS does not require an organizational structure for uploaded data.

A series of inferenial heuritics analyze the uploaded data to provide a *first guess* BIDS structure, which is presented to users through the web-browser user interface. Users verify the *first guess* and modify the information provided as needed so as to best match the final BIDS structure. 

Data from all major scanner vendors are accepted by ezBIDS. ezBIDS enables pseudo-anonymization by providing options for the defacing of anatomical sequences, and removes all identifying metadata information (e.g. `PatientName`) before final conversion to BIDS.

The BIDS output can then be downloaded back to the user's computer, or uploaded to open repositories such as
[brainlife.io](https://brainlife.io/) or [OpenNeuro.org](https://openneuro.org/).

Helpful links:
1. [ezBIDS website](https://brainlife.io/ezbids) (Chrome or Firefox browsers preferred)
2. [ezBIDS user documentation](https://brainlife.io/docs/using_ezBIDS/)
3. [ezBIDS tutorial](https://brainlife.io/docs/tutorial/ezBIDS/)
4. [ezBIDS tutorial video](https://www.youtube.com/embed/L8rWA8qgnpo)

### Usage

To access the ezBIDS web service, please visit https://brainlife.io/ezbids. If you do not have a brainlife.io account, you will be prompted to create one for authentication purposes.

Users do not need to organize their uploaded data in any specific manner, and users may choose to compress (e.g. zip, tar) their uploaded data.

Should users feel the need to anonymize data before uploading, we strongly recommend that subjects (and sessions, if applicable) be organized into subject (and session) folders, with explicit labeling of the preferred subjects (and sessions) IDs (e.g. `MRI_data/sub-01/ses-01/DICOMS`). Failure to do so for non-anonymized data may result in an inaccurate *first guess* and require additional edits in the web browser.

If users wish to install ezBIDS locally, to ensure that data do not leave their institution site, please see [here](https://brainlife.io/docs/using_ezBIDS/#installing-ezbids-locally).

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
* _Both authors contributed equally to this project_

### Funding Acknowledgement

brainlife.io is publicly funded, and for the sustainability of the project it is helpful to acknowledge the use of the platform. We kindly ask that you acknowledge the funding below in your code and publications. Copy and past the following lines into your repository when using this code.

[![NSF-BCS-1734853](https://img.shields.io/badge/NSF_BCS-1734853-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1734853)
[![NSF-BCS-1636893](https://img.shields.io/badge/NSF_BCS-1636893-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1636893)
[![NSF-ACI-1916518](https://img.shields.io/badge/NSF_ACI-1916518-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1916518)
[![NSF-IIS-1912270](https://img.shields.io/badge/NSF_IIS-1912270-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1912270)
[![NIH-NIBIB-R01EB029272](https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg)](https://grantome.com/grant/NIH/R01-EB029272-01)
[![NIH-NIMH-R01MH126699](https://img.shields.io/badge/NIH_NIMH-R01MH126699-green.svg)](https://grantome.com/grant/NIH/R01-EB029272)

### Citations

Please use the following citation when using ezBIDS:

Levitas, Daniel, et al. "ezBIDS: Guided standardization of neuroimaging data interoperable with major data archives and platforms." [Article](https://www.nature.com/articles/s41597-024-02959-0).


Copyright © 2022 brainlife.io at University of Texas at Austin
