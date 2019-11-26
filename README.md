This is a developmental repo for a web service that allows users to upload a directory containing 
DICOM files, and analyze the directory structure, sidecar generated from dcm2niix and *guess* 
as much information about the data structure as possible, then ask the user to verify / modify
those assumption before generating the final BIDS structure.

The output can be downloaded back to the user's computer, or sent to other repositories such as
OpenNeuro, or brainlife.io
