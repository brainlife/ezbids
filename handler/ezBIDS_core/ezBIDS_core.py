# !/usr/bin/env python3
"""
Created on Fri Jun 26 08:37:56 2020

This code represents ezBIDS's attempt to determine BIDS information (subject/session mapping,
datatype, suffix, entity labels [acq, run, dir, etc]) based on dcm2niix output.
This information is then displayed in the ezBIDS UI, where users can make
edits/modifications as they see fit, before finalizing their data into a
BIDS-compliant dataset.

@author: dlevitas
"""

from __future__ import division
import os
import re
import sys
import json
import yaml
import time
import shutil
import warnings
import matplotlib
import numpy as np
import pandas as pd
import nibabel as nib
import matplotlib.pyplot as plt
from PIL import Image
from math import floor
from datetime import date
from operator import itemgetter
from urllib.request import urlopen
from pathlib import Path

DATA_DIR = sys.argv[1]

PROJECT_DIR = Path(__file__).resolve().parents[2]
BIDS_SCHEMA_DIR = PROJECT_DIR / Path("bids-specification/src/schema")

datatypes_yaml = yaml.load(open(BIDS_SCHEMA_DIR / Path("objects/datatypes.yaml")), Loader=yaml.FullLoader)
entities_yaml = yaml.load(open(BIDS_SCHEMA_DIR / Path("objects/entities.yaml")), Loader=yaml.FullLoader)
suffixes_yaml = yaml.load(open(BIDS_SCHEMA_DIR / Path("objects/suffixes.yaml")), Loader=yaml.FullLoader)
dataset_description_yaml = yaml.load(open(BIDS_SCHEMA_DIR / Path("rules/dataset_metadata.yaml")), Loader=yaml.FullLoader)
datatype_suffix_rules = str(BIDS_SCHEMA_DIR / Path("rules/datatypes"))
entity_ordering_file = str(BIDS_SCHEMA_DIR / Path("rules/entities.yaml"))

cog_atlas_url = "http://cognitiveatlas.org/api/v-alpha/task"

bids_compliant = pd.read_csv("{}/bids_compliant.log".format(DATA_DIR), header=None).iloc[1][0]

start_time = time.time()
analyzer_dir = os.getcwd()

today_date = date.today().strftime("%Y-%m-%d")

os.chdir(DATA_DIR)

######## Functions ########
def set_IntendedFor_B0FieldIdentifier_B0FieldSource(dataset_list_unique_series, bids_compliant):
    if bids_compliant == "yes":
        for index, unique_dic in enumerate(dataset_list_unique_series):
            json_path = unique_dic["json_path"]

            json_data = open(json_path)
            json_data = json.load(json_data, strict=False)

            if "IntendedFor" in json_data:
                IntendedFor_indices = []
                IntendedFor = json_data["IntendedFor"]
                for i in IntendedFor:
                    IntendedFor_items = [[x["nifti_path"], x["series_idx"]] for x in dataset_list_unique_series]
                    IntendedFor_items = [x for x in IntendedFor_items if i in x[0]]
                    
                    for IntendedFor_item in IntendedFor_items:
                        IntendedFor_indices.append(IntendedFor_item[1])
                
                unique_dic["IntendedFor"] = IntendedFor_indices

            if "B0FieldIdentifier" in json_data:
                unique_dic["B0FieldIdentifier"] = json_data["B0FieldIdentifier"]
                if type(unique_dic["B0FieldIdentifier"]) == str:
                    unique_dic["B0FieldIdentifier"] = [unique_dic["B0FieldIdentifier"]]
            if "B0FieldSource" in json_data:
                unique_dic["B0FieldSource"] = json_data["B0FieldSource"]
                if type(unique_dic["B0FieldSource"]) == str:
                    unique_dic["B0FieldSource"] = [unique_dic["B0FieldSource"]]
                
    return dataset_list_unique_series

def generate_readme(DATA_DIR, bids_compliant):

    if bids_compliant == "yes":
        bids_root_dir = pd.read_csv("{}/bids_compliant.log".format(DATA_DIR), header=None).iloc[0][0]
        try:
            with open("{}/README".format(bids_root_dir)) as f:
                lines = f.readlines()
        except:
            lines = []
    else:
        lines = ["This data was converted using ezBIDS (https://brainlife.io/ezbids/). Additional information regarding this dataset can be entered in this file."]
    
    readme = "\n".join(lines)

    return readme

def generate_dataset_description(DATA_DIR, bids_compliant):
    dataset_description_dic = {}
    for field in dataset_description_yaml["dataset_description"]["fields"]:
        if "GeneratedBy" not in field:
            dataset_description_dic[field] = ""    

    if bids_compliant == "yes":
        bids_root_dir = pd.read_csv("{}/bids_compliant.log".format(DATA_DIR), header=None).iloc[0][0]
        dataset_description = open("{}/dataset_description.json".format(bids_root_dir))
        dataset_description = json.load(dataset_description, strict=False)

        for field in dataset_description:
            if field in dataset_description_dic.keys() and "GeneratedBy" not in field:
                dataset_description_dic[field] = dataset_description[field]
    
    dataset_description_dic["GeneratedBy"] =[
                                                {   "Name": "ezBIDS", 
                                                    "Version": "n/a", 
                                                    "Description": "ezBIDS is a web-based tool for converting MRI datasets to BIDS, requiring neither coding nor knowledge of the BIDS specification", 
                                                    "CodeURL": "https://brainlife.io/ezbids/",
                                                    "Container": {
                                                        "Type": "n/a",
                                                        "Tag": "n/a"
                                                    }
                                                }
                                            ]

    dataset_description_dic["SourceDatasets"] =[
                                                    {   "DOI": "n/a", 
                                                        "URL": "https://brainlife.io/ezbids/",
                                                        "Version": "n/a"
                                                    }
                                                ]  
    # Explicit checks
    if dataset_description_dic["Name"] == "":
        dataset_description_dic["Name"] = "Untitled"  
    
    if dataset_description_dic["BIDSVersion"] == "":
        dataset_description_dic["BIDSVersion"] = "1.8.0"    
    
    if dataset_description_dic["DatasetType"] == "":
        dataset_description_dic["DatasetType"] = "raw"
        
    return dataset_description_dic

def generate_participants_columns(DATA_DIR, bids_compliant):
    bids_root_dir = pd.read_csv("{}/bids_compliant.log".format(DATA_DIR), header=None).iloc[0][0]
    
    if bids_compliant == "yes" and os.path.isfile("{}/participants.json".format(bids_root_dir)):
        participants_column_info = open("{}/participants.json".format(bids_root_dir))
        participants_column_info = json.load(participants_column_info, strict=False)
    else:
        participants_column_info = {"sex": {"LongName": "gender",
                                    "Description": "generic gender field",
                                    "Levels": {
                                        "M": "male",
                                        "F": "female"
                                        }
                                    },
                            "age": {"LongName": "age",
                                    "Units": "years"
                                    }
                            }
    return participants_column_info

def find_cog_atlas_tasks(url):
    """
    Generates a list of all possible task names from the Cognitive Atlas API
    task url.

    Parameters
    ----------

    url : string
        web url of the Cognitive Atlas API task page.

    Returns
    -------
    tasks : list
        list of all possible task names. Each task name has spaces, "task", and
        "test" removed, to make it easier to search the SeriesDescription
        fields for a matching task name.
    """
    url_contents = urlopen(url)
    data = json.load(url_contents)
    tasks = [re.sub("[^A-Za-z0-9]+", "", re.split(" task| test", x["name"])[0]) for x in data] # Remove non-alphanumeric terms and "task", "test" substrings
    tasks = [x for x in tasks if len(x) > 2] # Remove empty task name terms and ones under 2 characters (b/c hard to detect in SeriesDescription)
    tasks = sorted(tasks, key=str.casefold) # sort alphabetically, but ignore case

    return tasks

def correct_pe(pe_direction, ornt):
    """
    Takes phase encoding direction and image orientation to correct
    pe_direction if need be. This correction occurs if pe_direction
    is in "xyz" format instead of "ijk".

    Function is based on https://github.com/nipreps/fmriprep/issues/2341 and
    code derived from Chris Markiewicz and Mathias Goncalves.

    Parameters
    ----------
    pe_direction : string
        Value from PhaseEncodingDirection in acquisition json file generated
        by dcm2niix
    ornt: string
        Value of "".join(nib.aff2axcodes(nii_img.affine)), where "nii_img" is
        is the acquisition NIFTI file generated by dcm2niix

    Returns
    -------
    proper_pe_direction: string
        pe_direction, in "ijk" format
    """
    axes = (("R", "L"), ("A", "P"), ("S", "I"))
    proper_ax_idcs = {"i": 0, "j": 1, "k": 2}

    # pe_direction is ijk (no correction necessary)
    if any(x in pe_direction for x in ["i", "i-", "j", "j-", "k", "k"]):
        proper_pe_direction = pe_direction

    # pe_direction xyz (correction required)
    else:
        improper_ax_idcs = {"x": 0, "y": 1, "z": 2}
        axcode = ornt[improper_ax_idcs[pe_direction[0]]]
        axcode_index = improper_ax_idcs[pe_direction[0]]
        inv = pe_direction[1:] == "-"

        if pe_direction[0] == "x":
            if "L" in axcode:
                inv = not inv
        elif pe_direction[0] == "y":
            if "P" in axcode:
                inv = not inv
        elif pe_direction[0] == "z":
            if "I" in axcode:
                inv = not inv
        else:
            ValueError("pe_direction does not contain letter i, j, k, x, y, or z")

        if inv:
            polarity = "-"
        else:
            polarity = ""

        proper_pe_direction = [key for key, value in proper_ax_idcs.items()
                               if value == axcode_index][0] + polarity

    return proper_pe_direction


def determine_direction(pe_direction, ornt):
    """
    Takes [corrected] pe_direction and image orientation to determine "_dir-" entity label,
    which is required or highly recommended for specific acquisitions.

    Based on https://github.com/nipreps/fmriprep/issues/2341 and code derived
    from Chris Markiewicz and Mathias Goncalves.

    Parameters
    ----------
    pe_direction : string
        Value from PhaseEncodingDirection in acquisition json file generated
        by dcm2niix
    ornt: string
        Value of "".join(nib.aff2axcodes(nii_img.affine)), where "nii_img" is
        is the acquisition NIFTI file generated by dcm2niix

    Returns
    -------
    direction: string
        direction for BIDS "_dir-" entity label
    """
    axes = (("R", "L"), ("A", "P"), ("S", "I"))
    ax_idcs = {"i": 0, "j": 1, "k": 2}
    axcode = ornt[ax_idcs[pe_direction[0]]]
    inv = pe_direction[1:] == "-"

    if pe_direction[0] == "i":
        if "L" in axcode:
            inv = not inv
    elif pe_direction[0] == "j":
        if "P" in axcode:
            inv = not inv
    elif pe_direction[0] == "k":
        if "I" in axcode:
            inv = not inv

    for ax in axes:
        for flip in (ax, ax[::-1]):
            if flip[not inv].startswith(axcode):
                direction = "".join(flip)

    return direction


def modify_uploaded_dataset_list(uploaded_json_list):
    """
    Filters the list of json files generated by preprocess.sh to ensure that
    the json files are derived from dcm2niix, and that they contain
    corresponding nifti (and bval/bvec) files. Additionally, Phillips PAR/REC
    files are removed, as they cannot be handled by ezBIDS. If these conditions
    are satisfied, all files are added to a modified dir_list.

    Parameters
    ----------
    uploaded_json_list : list
        list of json files generated from preprocess.sh

    Returns
    -------
    uploaded_files_list: list
        all files (i.e json, nifti, bval/bvec) from uploaded dataset
    """
    uploaded_files_list = []

    # Remove Philips proprietary files in uploaded_json_list if they exist
    uploaded_json_list = [json for json in uploaded_json_list
                          if "parrec" not in json.lower()
                          and "finalized.json" not in json]
    
    # Sort uploaded_json_list
    uploaded_json_list.sort()

    # Parse json files
    for json_file in uploaded_json_list:
        try:
            json_data = open(json_file)
            json_data = json.load(json_data, strict=False)
        except:
            print("{} has improper JSON syntax, possibly b/c uploaded data was converted by older dcm2niix version.".format(json_file))

        # Only want json files with corresponding nifti (and bval/bvec) and if
        # the files come from dcm2niix
        if "ConversionSoftware" in json_data and ("dcm2niix" in json_data["ConversionSoftware"] or "pypet2bids" in json_data["ConversionSoftware"]): 
            if len([os.path.dirname(json_file) + "/" + x for x in os.listdir(os.path.dirname(json_file)) if os.path.basename(json_file)[:-4] in x]) > 1:
                uploaded_files_list.append([os.path.dirname(json_file) + "/" + x for x in os.listdir(os.path.dirname(json_file)) if os.path.basename(json_file[:-4]) in x])

    # Flatten uploaded_dataset_list
    uploaded_files_list = [file for sublist in uploaded_files_list for file in sublist]

    return uploaded_files_list


def generate_dataset_list(uploaded_files_list):
    """
    Takes list of nifti, json, (and bval/bvec) files generated from dcm2niix
    to create a list of info directories for each uploaded acquisition, where
    each directory contains metadata and other dicom header information to
    help ezBIDS determine the identify of acquisitions, and to determine other
    BIDS-related information (e.g. entity labels).

    Parameters
    ----------
    uploaded_files_list : list
        List of nifti, json, and bval/bvec files generated from dcm2niix. The
        list of files is generated from preprocess.sh

    Returns
    -------
    dataset_list : list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files
    """
    # Create list for appending dictionaries to
    dataset_list = []

    # Get separate nifti and json (i.e. sidecar) lists
    json_list = [x for x in uploaded_files_list if ".json" in x]
    nifti_list = [x for x in uploaded_files_list
                  if ".nii.gz" in x
                  or ".bval" in x
                  or ".bvec" in x]

    print("Determining unique acquisitions in dataset")
    print("------------------------------------------")
    for index, json_file in enumerate(json_list):
        json_data = open(json_file)
        json_data = json.load(json_data, strict=False)
        print("JSON file: {}".format(json_file))

        corresponding_nifti = [x for x in nifti_list if json_file[:-4] in x
                               if ".nii" in x or ".nii.gz" in x][0]

        #Phase encoding direction info
        if "PhaseEncodingDirection" in json_data:
            pe_direction = json_data["PhaseEncodingDirection"]
        else:
            pe_direction = None

        try:
            ornt = nib.aff2axcodes(nib.load(corresponding_nifti).affine)
            ornt = "".join(ornt)
        except:
            ornt = None

        if pe_direction is not None and ornt is not None:
            proper_pe_direction = correct_pe(pe_direction, ornt)
            ped = determine_direction(proper_pe_direction, ornt)
        else:
            ped = ""
        
        # Nifti (and bval/bvec) file(s) associated with specific json file
        nifti_paths_for_json = [x for x in nifti_list if json_file[:-4] in x]
        nifti_paths_for_json = [x for x in nifti_paths_for_json if ".json" not in x]

        # Find nifti file size
        filesize = os.stat(nifti_paths_for_json[0]).st_size

        # Find StudyID from json
        if "StudyID" in json_data:
            study_id = json_data["StudyID"]
        else:
            study_id = ""

        """
        Find subject_id from json, since some files contain neither
        PatientName nor PatientID
        """
        if "PatientName" in json_data:
            patient_name = json_data["PatientName"]
        else:
            patient_name = "n/a"

        if "PatientID" in json_data:
            patient_id = json_data["PatientID"]
        else:
            patient_id = "n/a"

        # Find PatientBirthDate
        if "PatientBirthDate" in json_data:
            patient_birth_date = json_data["PatientBirthDate"].replace("-", "")
        else:
            patient_birth_date = "00000000"

        # Find PatientSex
        patient_sex = "n/a"
        if "PatientSex" in json_data:
            if json_data["PatientSex"] in ["M", "F"]:
                patient_sex = json_data["PatientSex"]

        # Find PatientAge
        if "PatientAge" in json_data:
            patient_age = json_data["PatientAge"]
        else:
            patient_age = "n/a"


        """metadata may contain PatientBirthDate and/or PatientAge. Check either
        to see if one truly provides accurate age information."""
        age = "n/a"
        if "PatientAge" in json_data:
            patient_age = json_data["PatientAge"]
            if not patient_age.isalnum(): # if true, is alphanumeric, so not age
                try:
                    if (type(patient_age) == int or type(patient_age) == float) and int(patient_age) < 100: # if age is over 100, probably made up
                        age = patient_age
                except:
                    pass

        if age == "n/a" and "PatientBirthDate" in json_data:
            patient_birth_date = json_data["PatientBirthDate"] # ISO 8601 "YYYY-MM-DD"
            try:
                age = int(today_date.split("-")[0]) - int(patient_birth_date.split("-")[0]) - \
                    ((int(today_date.split("-")[1]), int(today_date.split("-")[2])) < \
                     (int(patient_birth_date.split("-")[2]), int(patient_birth_date.split("-")[2])))
            except:
                pass

        """
        Select subject ID to display.
        Subject ID precedence order if explicit subject ID (i.e. ReproIn naming convention)
        is not found: PatientName > PatientID > PatientBirthDate
        """
        subject = "n/a"
        for value in [json_file, patient_name, patient_id]:
            for string in ["sub-", "subject-", "sub_", "subject_"]:
                if string in value.lower():
                    if not value.lower().split(string)[0][-1].isalnum():
                        subject = re.split("[^a-zA-Z0-9]+", re.compile(string, re.IGNORECASE).split(value)[-1])[0]
                        break
        # for value in [json_file, patient_name, patient_id]:
        #     if any(x in value.lower() for x in ["sub-", "subject-", "sub_", "subject_"]):
        #         subject = re.split("[^a-zA-Z0-9]+", re.compile(r"sub-|subject-|sub_|subject_", re.IGNORECASE).split(value)[-1])[0]
        #         break

        if subject == "n/a":
            if patient_name != "n/a":
                subject = patient_name
            elif patient_id != "n/a":
                subject = patient_id
            elif patient_birth_date != "00000000":
                subject = patient_birth_date
            elif json_file.count("/") - 1 == 1: # only one level, so assume that level is the subject ID
                subject = json_file.split("/")[1]
            else:
                pass
        
        # Select session ID to display, if applicable
        session = ""
        for value in [json_file, patient_name, patient_id]:
            for string in ["ses-", "session-", "ses_", "session_"]:
                if string in value.lower():
                    if not value.lower().split(string)[0][-1].isalnum():
                        session = re.split("[^a-zA-Z0-9]+", re.compile(string, re.IGNORECASE).split(value)[-1])[0]
                        break

        # Remove non-alphanumeric characters from subject (and session) ID(s)
        subject = re.sub("[^A-Za-z0-9]+", "", subject)
        session = re.sub("[^A-Za-z0-9]+", "", session)

        # Find Acquisition Date & Time
        if "AcquisitionDateTime" in json_data:
            acquisition_date_time = json_data["AcquisitionDateTime"]
            acquisition_date = json_data["AcquisitionDateTime"].split("T")[0]
            acquisition_time = json_data["AcquisitionDateTime"].split("T")[-1]
        else:
            acquisition_date_time = "0000-00-00T00:00:00.000000"
            acquisition_date = "0000-00-00"
            acquisition_time = None

        if "AcquisitionTime" in json_data:
            acquisition_time = json_data["AcquisitionTime"]

        if "TimeZero" in json_data and json_data.get("ScanStart", None) == 0:
            acquisition_time = json_data["TimeZero"]

        # Find RepetitionTime
        if "RepetitionTime" in json_data:
            repetition_time = json_data["RepetitionTime"]
        else:
            repetition_time = "n/a"

        # Find EchoNumber
        if "EchoNumber" in json_data:
            echo_number = json_data["EchoNumber"]
        else:
            echo_number = None

        # Find EchoTime
        if "EchoTime" in json_data:
            echo_time = json_data["EchoTime"]*1000
        else:
            echo_time = 0

        # get the nibabel nifti image info
        image = nib.load(json_file[:-4] + "nii.gz")

        # Find how many volumes are in corresponding nifti file
        try:
            volume_count = image.shape[3]
        except:
            volume_count = 1

        # Find SeriesNumber
        if "SeriesNumber" in json_data:
            series_number = json_data["SeriesNumber"]
        else:
            series_number = 0

        # Modified SeriesNumber, which zero pads integers < 10. Helpful later for sorting purposes
        if series_number < 10:
            mod_series_number = '0' + str(series_number)
        else:
            mod_series_number = str(series_number)

        # Find SeriesDescription
        if "SeriesDescription" in json_data:
            series_description = json_data["SeriesDescription"]
            descriptor = "SeriesDescription"
        else:
            series_description = "n/a"
            descriptor = "ProtocolName"

        # Find ProtocolName
        if "ProtocolName" in json_data:
            protocol_name = json_data["ProtocolName"]
        else:
            protocol_name = "n/a"

        # Find ImageType
        if "ImageType" in json_data:
            image_type = json_data["ImageType"]
        else:
            image_type = []

        # Relative paths of json and nifti files (per SeriesNumber)
        paths = sorted(nifti_paths_for_json + [json_file])

        # Organize all from individual SeriesNumber in dictionary
        acquisition_info_directory = {
            "StudyID": study_id,
            "PatientName": patient_name,
            "PatientID": patient_id,
            "PatientBirthDate": patient_birth_date,
            "PatientSex": patient_sex,
            "PatientAge": age,
            "subject": subject,
            "session": session,
            "SeriesNumber": series_number,
            "ModifiedSeriesNumber": mod_series_number,
            "AcquisitionDateTime": acquisition_date_time,
            "AcquisitionDate": acquisition_date,
            "AcquisitionTime": acquisition_time,
            "SeriesDescription": series_description,
            "ProtocolName": protocol_name,
            "descriptor": descriptor,
            "ImageType": image_type,
            "RepetitionTime": repetition_time,
            "EchoNumber": echo_number,
            "EchoTime": echo_time,
            "datatype": "",
            "suffix": "",
            "subject_idx": 0,
            "session_idx": 0,
            "series_idx": 0,
            "direction": ped,
            "exclude": False,
            "filesize": filesize,
            "NumVolumes": volume_count,
            "orientation": ornt,
            "forType": "",
            "error": None,
            "IntendedFor": None,
            "B0FieldIdentifier": None,
            "B0FieldSource": None,
            "section_id": 1,
            "message": None,
            "type": "",
            "nifti_path": [x for x in nifti_paths_for_json if ".nii.gz" in x][0],
            'nibabel_image': image,
            "json_path": json_file,
            "paths": paths,
            "headers": "",
            "sidecar":json_data
        }
        dataset_list.append(acquisition_info_directory)

    # Sort dataset_list of dictionaries
    dataset_list = sorted(dataset_list, key=itemgetter("AcquisitionDate",
                                                        "subject",
                                                        "session",
                                                        "ModifiedSeriesNumber",
                                                        "json_path"))
    return dataset_list

def determine_subj_ses_IDs(dataset_list, bids_compliant):
    """
    Determine subject ID(s), and session ID(s) (if applicable) of uploaded
    dataset.

    Parameters
    ----------
    dataset_list: list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files

    Returns
    -------
    dataset_list: list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files

    subject_ids_info: list
        List of dictionaries containing subject identification info, such as
        PatientID, PatientName, PatientBirthDate, and corresponding session
        information

    """
    date_counter = 1
    subject_idx_counter = 0
    subjects_information = []
    participants_info = {}
    # Determine unique subjects from uploaded dataset
    for sub in np.unique([x["subject"] for x in dataset_list]):
        sub_dics_list = [x for x in dataset_list if x["subject"] == sub]

        # Give each subject a unique subject_idx value
        for x in sub_dics_list:
            x["subject_idx"] = subject_idx_counter
        subject_idx_counter += 1

        # Organize phenotype (e.g., sex, age) information
        bids_root_dir = pd.read_csv("{}/bids_compliant.log".format(DATA_DIR), header=None).iloc[0][0]
        if bids_compliant == "yes" and os.path.isfile("{}/participants.tsv".format(bids_root_dir)):
            participants_info_data = pd.read_csv("{}/participants.tsv".format(bids_root_dir), sep="\t")

            participants_info = {}
            participants_info_columns = [x for x in participants_info_data.columns if x != "participant_id"] + ["PatientName", "PatientID"]
            for len_index in range(len(participants_info_data)):
                participants_info[str(len_index)] = dict.fromkeys(participants_info_columns)
                
                for col in participants_info_columns:
                    if col not in ["PatientName", "PatientID"]:
                        participants_info[str(len_index)][col] = str(participants_info_data[col].iloc[len_index])
                    else:
                        if "sub-" in participants_info_data["participant_id"].iloc[len_index]:
                            participant_id = participants_info_data["participant_id"].iloc[len_index].split("-")[-1]
                        else:
                            participant_id = participants_info_data["participant_id"].iloc[len_index]

                        participants_info[str(len_index)]["PatientName"] = str(participant_id)
                        participants_info[str(len_index)]["PatientID"] = str(participant_id)
        else:
            phenotype_info = list({"sex":x["PatientSex"],"age":x["PatientAge"],"PatientName":x["PatientName"], "PatientID":x["PatientID"]} for x in sub_dics_list)[0]
            participants_info.update({str(x["subject_idx"]):phenotype_info})

        # Determine all unique sessions (if applicable) per subject
        unique_ses_date_times = []
        session_idx_counter = 0
        ses_dates = list(set([(x["session"], x["AcquisitionDate"]) for x in sub_dics_list]))

        # Session information includes the following metadata: session, AcquisitionDate, and AcquisitionTime
        for ses_date in ses_dates:
            ses_date = list(ses_date)
            date_time = [x["AcquisitionTime"] for x in sub_dics_list if x["session"] == ses_date[0] and x["AcquisitionDate"] == ses_date[1]][0]
            ses_date.append(date_time)
            dic = {"session": ses_date[0], "AcquisitionDate": ses_date[1], "AcquisitionTime": ses_date[2], "exclude": False, "session_idx": 0}
            unique_ses_date_times.append(dic)

        # Sorting method is determined by whether or not the uploaded data is anonymized
        if unique_ses_date_times[0]["AcquisitionDate"] != "0000-00-00":
            unique_ses_date_times = sorted(unique_ses_date_times, key=itemgetter("AcquisitionDate",
                                                                                 "AcquisitionTime",
                                                                                 "session"))
        else:
            unique_ses_date_times = sorted(unique_ses_date_times, key=itemgetter("session"))


        # For each session per subject, give a unique session_idx value
        for dic in unique_ses_date_times:
            dic["session_idx"] = session_idx_counter
            session_idx_counter += 1

        # Pair patient information (PatientName, PatientID, PatientBirthDate) with corresponding session information
        patient_info = []
        for ses_info in unique_ses_date_times:
            patient_dic = {
                            "PatientName": [x["PatientName"] for x in sub_dics_list if x["session"] == ses_info["session"] and x["AcquisitionDate"] == ses_info["AcquisitionDate"]][0],
                            "PatientID": [x["PatientID"] for x in sub_dics_list if x["session"] == ses_info["session"] and x["AcquisitionDate"] == ses_info["AcquisitionDate"]][0],
                            "PatientBirthDate": [x["PatientBirthDate"] for x in sub_dics_list if x["session"] == ses_info["session"] and x["AcquisitionDate"] == ses_info["AcquisitionDate"]][0]
                            # "PatientBirthDate": [x["PatientName"] for x in sub_dics_list if x["session"] == ses_info["session"] and x["AcquisitionDate"] == ses_info["AcquisitionDate"]][0]
                           }
            patient_info.append(patient_dic)

        """
        See if multiple sessions occurred on same day, meaning same AcquisitionDate
        If so, modify the AcquisitionDate value(s) so that each are unique, since
        ezBIDS only cares about AcquisitionDate. Modification entails appending
        a '.<value>' to the end of the AcquisitionDate value (e.g. '2021-01-01.1')
        """
        unique_ses_dates = [[x["session"], x["AcquisitionDate"]] for x in unique_ses_date_times]
        for ses_date in unique_ses_dates:
            unique_dates_dics_list = [x for x in unique_ses_date_times if x["AcquisitionDate"] == ses_date[1]]
            if len(unique_dates_dics_list) > 1:
                for date_dic in unique_dates_dics_list:
                    date_dic["AcquisitionDate"] = ses_date[1] + "." + str(date_counter)
                    date_counter += 1

        # update dataset_list with updated AcquisitionDate and session_idx info
        for sub_ses_map_dic in unique_ses_date_times:
            for data_dic in dataset_list:
                if (data_dic["subject"] == sub
                and data_dic["session"] == sub_ses_map_dic["session"]
                and data_dic["AcquisitionDate"] == sub_ses_map_dic["AcquisitionDate"].split(".")[0]):
                    data_dic["AcquisitionDate"] = sub_ses_map_dic["AcquisitionDate"]
                    data_dic["session_idx"] = sub_ses_map_dic["session_idx"]

        """
        Using all the information gathered above, build the subject/session
        information in format that ezBIDS can understand.
        """
        subject_ids_info = {
                            "subject": sub,
                            "PatientInfo": patient_info,
                            "phenotype": list({"sex":x["PatientSex"],"age":x["PatientAge"]} for x in sub_dics_list)[0],
                            "exclude": False,
                            "sessions": [{k: v for k, v in d.items() if k != "session_idx" and k != "AcquisitionTime"} for d in unique_ses_date_times],
                            "validationErrors": []
                            }

        subjects_information.append(subject_ids_info)

    return dataset_list, subjects_information, participants_info


def determine_unique_series(dataset_list, bids_compliant):
    """
    From the dataset_list, lump the individual acquisitions into unique series.
    Unique data is determined from 4 dicom header values: SeriesDescription
    EchoTime, ImageType, and RepetitionTime. If EchoTime values differ
    slightly (+/- 1 ms) and other values are the same, a unique series ID is not
    given, since EchoTime is a continuous variable.

    Parameters
    ----------
    dataset_list: list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files.

    Returns
    -------
    dataset_list_unique_series: list
        A modified version of dataset_list, where the list contains only the
        dictionaries of acquisitions with a unique series ID.
    """
    dataset_list_unique_series = []
    series_checker = []
    series_idx = 0

    for index, acquisition_dic in enumerate(dataset_list):
        """
        If retro-reconstruction (RR) acquistions are found
        ("_RR" in SeriesDescription), they should be of same unique
        series as non retro-reconstruction ones. These are generally rare
        cases, but should be accounted for.
        """

        if acquisition_dic["SeriesDescription"] != "n/a":
            if "_RR" in acquisition_dic["SeriesDescription"]:
                modified_sd = acquisition_dic["SeriesDescription"].replace("_RR", "")
                heuristic_items = [acquisition_dic["EchoTime"],
                                   modified_sd,
                                   acquisition_dic["ImageType"],
                                   acquisition_dic["RepetitionTime"],
                                   1]
            else:
                heuristic_items = [acquisition_dic["EchoTime"],
                                   acquisition_dic["SeriesDescription"],
                                   acquisition_dic["ImageType"],
                                   acquisition_dic["RepetitionTime"],
                                   1]
        else: # No SeriesDescription; use ProtocolName instead
            heuristic_items = [acquisition_dic["EchoTime"],
                                   acquisition_dic["ProtocolName"],
                                   acquisition_dic["ImageType"],
                                   acquisition_dic["RepetitionTime"],
                                   1]

        if bids_compliant == "yes": # Each uploaded BIDS NIfTI/JSON pair is a unique series
            if index == 0:
                series_idx = 0
            else:
                series_idx += 1
            acquisition_dic["series_idx"] = series_idx
            dataset_list_unique_series.append(acquisition_dic)
        else:
            if index == 0:
                acquisition_dic["series_idx"] = 0
                dataset_list_unique_series.append(acquisition_dic)

            # unique acquisition, make unique series ID
            elif heuristic_items not in [x[:-1] for x in series_checker]:
                # But first, check if EchoTimes are essentially the same (i.e. +- 0.5)
                if heuristic_items[1:] in [x[1:-1] for x in series_checker]:
                    echo_time = heuristic_items[0]
                    common_series_index = [x[1:-1] for x in series_checker].index(heuristic_items[1:])

                    """ Add slight EchoTime measurement error tolerance.
                    See https://github.com/rordenlab/dcm2niix/issues/543 """
                    if series_checker[common_series_index][0] - 0.5 <= echo_time <= series_checker[common_series_index][0] + 0.5:
                        common_series_idx = series_checker[common_series_index][-1]
                        acquisition_dic["series_idx"] = common_series_idx
                    else:
                        series_idx += 1
                        acquisition_dic["series_idx"] = series_idx
                        dataset_list_unique_series.append(acquisition_dic)

                else:
                    series_idx += 1
                    acquisition_dic["series_idx"] = series_idx
                    dataset_list_unique_series.append(acquisition_dic)

            else:
                common_series_index = [x[:-1] for x in series_checker].index(heuristic_items)
                common_series_idx = series_checker[common_series_index][-1]
                acquisition_dic["series_idx"] = common_series_idx

            series_checker.append(heuristic_items + [acquisition_dic["series_idx"]])

    return dataset_list, dataset_list_unique_series


def datatype_suffix_identification(dataset_list_unique_series):
    """
    Uses metadata to try to determine the identity (i.e. datatype and suffix)
    of each unique acquisition in uploaded dataset.

    Parameters
    ----------
    dataset_list_unique_series : list
        List of dictionaries for each unique acquisition series in dataset.

    Returns
    -------
    dataset_list_unique_series : list
        updated input list of dictionaries
    """

    """ Schema datatype and suffix labels are helpful, but typically
    researchers label their imaging protocols in less standardized ways.
    ezBIDS will attempt to determine datatype and suffix labels based on
    common keys/labels."""
    localizer_keys = ["localizer", "scout"]
    angio_keys = ["angio"]
    se_mag_phase_fmap_keys = ["fmap", "fieldmap", "spinecho", "sefmri", "semri", "grefieldmap", "distortionmap"]
    flair_keys = ["t2spacedafl", "t2spc"]
    dwi_derived_keys = ["trace", "fa", "adc"]
    dwi_keys = ["dti", "dmri", "dwi"]
    func_keys = ["func", "fmri", "mri", "task", "rest"]
    t1w_keys = ["tfl3d", "mprage", "spgr", "tflmgh", "t1mpr", "anatt1", "3dt1"]
    t2w_keys = ["t2", "anatt2", "3dt2"]
    tb1tfl_keys = ["tflb1map"]
    tb1rfm_keys = ["rfmap"]
    chimap_keys = ["qsm"]
    asl_keys = ["pasl", "m0scan"]
    pet_keys = ["Radiopharmaceutical", "InjectionStart"]
    for index, unique_dic in enumerate(dataset_list_unique_series):

        json_path = unique_dic["json_path"]

        if unique_dic["SeriesDescription"] == "n/a":
            sd = unique_dic["ProtocolName"]
        else:
            sd = unique_dic["SeriesDescription"]

        """Make easier to find key characters/phrases in sd by removing
        non-alphanumeric characters and make everything lowercase."""
        sd_sparse = re.sub("[^A-Za-z0-9]+", "", sd).lower()
        sd = sd.lower().replace(" ", "")

        # Try checking based on BIDS schema keys/labels
        if unique_dic["SeriesDescription"] != "n/a":
            if unique_dic["nibabel_image"].get_data_dtype() == [('R', 'u1'), ('G', 'u1'), ('B', 'u1')]: # non-BIDS acquisition
                unique_dic["type"] = "exclude"
                unique_dic["error"] = "Acquisition does not appear to be an MRI acquisition for BIDS"
                unique_dic["message"] = " ".join("Acquisition is not believed \
                    to be an MRI acquisition and therefore will not be converted \
                    to BIDS. Please modify if incorrect.".split())
            else:
                for datatype in datatypes_yaml:
                    if datatype in sd or datatype in json_path:
                        unique_dic["datatype"] = datatype

                    rule = yaml.load(open(os.path.join(analyzer_dir, datatype_suffix_rules, datatype) + ".yaml"), Loader=yaml.FullLoader)
                    # rule = yaml.load(open(os.path.join(datatype_suffix_rules, datatype + ".yaml")), Loader=yaml.FullLoader)

                    suffixes = [x for y in [rule[x]["suffixes"] for x in rule] for x in y]

                    short_suffixes = [x for x in suffixes if len(x) < 3]

                    unhelpful_suffixes = ["fieldmap", "beh", "epi", "magnitude", "magnitude1", "magnitude2", "phasediff"]

                    bad_suffixes = short_suffixes + unhelpful_suffixes

                    """ Oftentimes, magnitude/phase[diff] acquisitions are called "gre-field-mapping",
                    so shouldn't receive the "fieldmap" suffix """
                    if "grefieldmap" in sd_sparse:
                        unique_dic["datatype"] = "fmap"
                        unique_dic["suffix"] = ""

                    # Remove deprecated suffixes
                    deprecated_suffixes = ["T2star", "FLASH", "PD", "phase"]
                    suffixes = [x for x in suffixes if x not in deprecated_suffixes and x not in bad_suffixes]

                    if any(x.lower() in sd for x in suffixes):
                        unique_dic["suffix"] = [x for x in suffixes if re.findall(x.lower(), sd)][-1]
                        if unique_dic["datatype"] == "func" and unique_dic["suffix"] == "phase":
                            unique_dic["suffix"] = "bold"
                        unique_dic["message"] = " ".join("Acquisition is believed to \
                            be {}/{} because '{}' is in the {}. Please \
                            modify if incorrect.".format(unique_dic["datatype"], unique_dic["suffix"], unique_dic["suffix"], unique_dic["descriptor"]).split())

                    if any(x in json_path for x in suffixes):
                        unique_dic["suffix"] = [x for x in suffixes if re.findall(x, json_path)][-1]
                        if unique_dic["datatype"] == "func" and unique_dic["suffix"] == "phase":
                            unique_dic["suffix"] = "bold"
                        unique_dic["message"] = " ".join("Acquisition is believed to \
                            be {}/{} because '{}' is in the file path. Please \
                            modify if incorrect.".format(unique_dic["datatype"], unique_dic["suffix"], unique_dic["suffix"]).split())

                    for bad_suffix in bad_suffixes:
                        if "_{}.json".format(bad_suffix) in json_path:
                            if bad_suffix == "fieldmap":
                                unique_dic["datatype"] = "fmap"
                            elif bad_suffix == "beh":
                                unique_dic["datatype"] = "beh"
                            elif bad_suffix == "epi":
                                unique_dic["datatype"] = "fmap"
                            elif bad_suffix == "magnitude":
                                unique_dic["datatype"] = "fmap"
                            elif bad_suffix == "magnitude1":
                                unique_dic["datatype"] = "fmap"
                            elif bad_suffix == "magnitude2":
                                unique_dic["datatype"] = "fmap"                                                                                           
                            elif bad_suffix == "phasediff":
                                unique_dic["datatype"] = "fmap"                                                                                        
                            elif bad_suffix == "PC":
                                unique_dic["datatype"] = "micr"                            
                            elif bad_suffix == "DF":
                                unique_dic["datatype"] = "micr"

                            unique_dic["suffix"] = bad_suffix
                            unique_dic["message"] = " ".join("Acquisition is believed to \
                            be {}/{} because '_{}.json' is in the file path. Please \
                            modify if incorrect.".format(unique_dic["datatype"], unique_dic["suffix"], bad_suffix).split())

                    # Instances where users specify both mp2rage and UNIT1 together, default to UNIT1
                    if "DERIVED" and "UNI" in unique_dic["ImageType"]:
                        unique_dic["datatype"] = "anat"
                        unique_dic["suffix"] = "UNIT1"
                        unique_dic["message"] = " ".join("Acquisition is believed to be anat/UNIT1 \
                            because 'DERIVED' and 'UNI' are in the ImageType. Please modify \
                            if incorrect".split())

        """ If no luck with BIDS schema keys/labels, try using common keys in
        SeriesDescription """
        if not unique_dic["datatype"] or not unique_dic["suffix"]:
            # Localizer(s)
            if any(x in sd for x in localizer_keys) or "_i0000" in unique_dic["paths"][0]:
                unique_dic["type"] = "exclude"
                unique_dic["error"] = "Acquisition appears to be a localizer"
                unique_dic["message"] = " ".join("Acquisition is believed to be a \
                    localizer and will therefore not be converted to BIDS. Please \
                    modify if incorrect.".split())

            # # Arterial Spin Labeling (ASL)
            # elif any(x in sd for x in asl_keys):
                # piece = sd
            #     unique_dic["datatype"] = "perf"
            #     unique_dic["suffix"] = "asl"
            #     unique_dic["message"] = " ".join("Acquisition is believed to be perf/asl \
            #         because '{}' is in the {}. Please modify if \
            #         incorrect.".format([x for x in asl_keys if re.findall(x, piece)][0]).split())

            # Angiography
            elif any(x in sd for x in angio_keys):
                piece = sd

                unique_dic["type"] = "exclude"
                unique_dic["datatype"] = "anat"
                unique_dic["suffix"] = "angio"
                unique_dic["error"] = " ".join("Acquisition appears to be an Angiography \
                    acquisition, which is currently not supported by ezBIDS at \
                    this time, but will be in the future".split())
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/angio \
                    because '{}' is in the {}. Please modify if \
                    incorrect. Currently, ezBIDS does not support Angiography \
                    conversion to BIDS".format([x for x in angio_keys if re.findall(x, piece)][0], unique_dic["descriptor"]).split())

            # TB1TFL field maps
            elif any(x in sd for x in tb1tfl_keys):
                unique_dic["datatype"] = "fmap"
                unique_dic["suffix"] = "TB1TFL"
                unique_dic["message"] = " ".join("Acquisition is believed to be a \
                    TB1TFL field map because 'tflb1map' is in the {}. \
                    Please modify if incorrect".format(unique_dic["descriptor"]).split())

            # TB1RFM field maps
            elif any(x in sd for x in tb1rfm_keys):
                unique_dic["datatype"] = "fmap"
                unique_dic["suffix"] = "TB1RFM"
                unique_dic["message"] = " ".join("Acquisition is believed to be a \
                    TB1RFM field map because 'rfmap' is in the {}. \
                    Please modify if incorrect".format(unique_dic["descriptor"]).split())

            # Magnitude/Phase[diff] and Spin Echo (SE) field maps
            elif any(x in sd for x in se_mag_phase_fmap_keys) or (len([x for x in se_mag_phase_fmap_keys if x in sd_sparse]) and len([x for x in se_mag_phase_fmap_keys if x in sd_sparse][-1]) > 3):
                if any(x in sd for x in se_mag_phase_fmap_keys):
                    piece = sd
                else:
                    piece = sd_sparse
                
                unique_dic["datatype"] = "fmap"
                unique_dic["forType"] = "func/bold"

                if "EchoNumber" in unique_dic["sidecar"]:
                    if unique_dic["EchoNumber"] == 1 and "_e1_ph" not in unique_dic["json_path"]:
                        unique_dic["suffix"] = "magnitude1"
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            fmap/magnitude1 because '{}' is in SeriesDescription, \
                            EchoNumber == 1 in metadata, and the phrase '_e1_ph' \
                            is not in the filename. Please modify if \
                            incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, piece)][0]).split())
                    elif unique_dic["EchoNumber"] == 1 and "_e1_ph" in unique_dic["json_path"]:
                        unique_dic["suffix"] = "phase1"
                        unique_dic["message"] = " ".join("Acquisition is believed to \
                            be fmap/phase1 because '{}' is in SeriesDescription, \
                            EchoNumber == 1 in metadata, and the phrase '_e1_ph' is in \
                            the filename. Please modify if incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, piece)][0]).split())
                    elif unique_dic["EchoNumber"] == 2 and "_e2_ph" not in unique_dic["json_path"]:
                        unique_dic["suffix"] = "magnitude2"
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            fmap/magnitude2 because '{}' is in SeriesDescription, \
                            EchoNumber == 2 in metadata, and the phrase '_e2_ph' is \
                            not in the filename. Please modify if incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, piece)][0]).split())
                    elif unique_dic["EchoNumber"] == 2 and "_e2_ph" in unique_dic["json_path"] and "_e1_ph" in dataset_list_unique_series[index-2]["json_path"]:
                        unique_dic["suffix"] = "phase2"
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            fmap/phase2 because '{}' is in SeriesDescription, \
                            EchoNumber == 2 in metadata, and the phrase '_e2_ph' \
                            is in the filename and '_e1_ph' the one two before. \
                            Please modify if incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, piece)][0]).split())
                    elif unique_dic["EchoNumber"] == 2 and "_e2_ph" in unique_dic["json_path"] and "_e1_ph" not in dataset_list_unique_series[index-2]["json_path"]:
                        unique_dic["suffix"] = "phasediff"
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            fmap/phasediff because 'fmap' or 'fieldmap' is in \
                            SeriesDescription, EchoNumber == 2 in metadata, and \
                            the subjectstring '_e2_ph' is in the filename but \
                            '_e1_ph' not found in the acquisition two before. \
                            Please modify if incorrect".split())
                    else:
                        unique_dic["error"] = " ".join("Acquisition appears to be some form \
                            of fieldmap with an EchoNumber, however, unable to \
                            determine if it is a magnitude, phase, or phasediff. \
                            Please modify if acquisition is desired for BIDS \
                            conversion, otherwise the acquisition will not be \
                            converted".split())
                        unique_dic["message"] = unique_dic["error"]
                        unique_dic["type"] = "exclude"

                # Spin echo field maps (for func)
                else:
                    unique_dic["suffix"] = "epi"
                    unique_dic["message"] = " ".join("Acquisition is believed to be fmap/epi \
                        because '{}' is in SeriesDescription, and does not contain \
                        metadata info associated with magnitude/phasediff acquisitions.\
                        Please modify if incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, piece)][0]).split())

            # spin echo field maps (for dwi)
            elif "DIFFUSION" in unique_dic["ImageType"] and ("b0" in sd or "bzero" in sd):
                unique_dic["datatype"] = "fmap"
                unique_dic["suffix"] = "epi"
                unique_dic["forType"] = "dwi/dwi"
                unique_dic["message"] = " ".join("Acquisition appears to be a fmap/epi meant \
                    for dwi/dwi, as 'DIFFUSION' is in ImageType, and 'b0' or 'bzero' is in \
                    the SeriesDescription. Please modify if incorrect".split())

            # DWI
            elif not any(".bvec" in x for x in unique_dic["paths"]) and "DIFFUSION" in unique_dic["ImageType"]:
                unique_dic["error"] = " ".join("Acquisitions has 'DIFFUSION' label in the \
                    ImageType; however, there are no corresponding bval/bvec \
                    files. This may or may not be dwi/dwi. Please modify if \
                    incorrect.".split())
                unique_dic["message"] = unique_dic["error"]
                unique_dic["type"] = "exclude"

            elif any(".bvec" in x for x in unique_dic["paths"]):
                if "DIFFUSION" not in unique_dic["ImageType"]:
                    if unique_dic["NumVolumes"] < 2:
                        if any(x in sd for x in flair_keys):
                            piece = sd

                            unique_dic["datatype"] = "anat"
                            unique_dic["suffix"] = "FLAIR"
                            unique_dic["message"] = " ".join("Acquisition is believed to be \
                                anat/FLAIR because '{}' is in the \
                                SeriesDescription. Please modify if incorrect".format([x for x in flair_keys if re.findall(x, piece)][0]).split())
                        elif "t2w" in sd:
                            unique_dic["datatype"] = "anat"
                            unique_dic["suffix"] = "T2w"
                            unique_dic["message"] = " ".join("Acquisition is believed to be \
                                anat/T2w because 't2w' is in the \
                                SeriesDescription. Please modify if incorrect".split())
                        else:
                            unique_dic["error"] = " ".join("Acquisition has bval and bvec \
                                files but does not appear to be dwi/dwi because \
                                'DIFUSSION' is not in ImageType and contains less \
                                than 2 volumes. Please modify if incorrect, \
                                otherwise will not convert to BIDS".split())
                            unique_dic["message"] = unique_dic["error"]
                            unique_dic["type"] = "exclude"
                    else:
                        unique_dic["datatype"] = "dwi"
                        unique_dic["suffix"] = "dwi"
                        unique_dic["message"] = " ".join("Acquisition appears to be dwi/dwi \
                            because although 'DIFUSSION' is not in ImageType, the \
                            acquisition has bval and bvec files and has {} \
                            volumes. Please modify if incorrect".format(unique_dic["NumVolumes"]).split())
                else:
                    """Low b-values will default to fmap/epi, intended to be used
                    on dwi/dwi data."""
                    bval = np.loadtxt([x for x in unique_dic["paths"] if "bval" in x][0])
                    if np.max(bval) <= 50:
                        unique_dic["datatype"] = "fmap"
                        unique_dic["suffix"] = "epi"
                        unique_dic["forType"] = "dwi/dwi"
                        unique_dic["message"] = " ".join("Acquisition appears to be \
                            fmap/epi meant for dwi/dwi, as there are bval & bvec \
                            files, but with low b-values. Please modify if \
                            incorrect".split())

                    # elif any(x in sd for x in dwi_derived_keys) and not any(x in sd for x in dwi_keys):
                    elif any(x in sd for x in dwi_derived_keys):
                        piece = sd
                        
                        unique_dic["error"] = " ".join("Acquisition appears to be a TRACE, \
                            FA, or ADC, which are unsupported by ezBIDS and will \
                            therefore not be converted".split())
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            TRACE, FA, or ADC because there are bval & bvec files \
                            with the same SeriesNumber, and '{}' is in the \
                            SeriesDescription. Please modify if \
                            incorrect".format([x for x in dwi_derived_keys if re.findall(x, piece)][0]).split())
                        unique_dic["type"] = "exclude"
                    else:
                        unique_dic["datatype"] = "dwi"
                        unique_dic["suffix"] = "dwi"
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            dwi/dwi because there are bval & bvec files with the \
                            same SeriesNumber, 'DIFFUSION' is in the ImageType, \
                            and it does not appear to be derived dwi data. Please \
                            modify if incorrect".split())

            # DWI derivatives or other non-BIDS diffusion offshoots
            elif any(x in sd for x in dwi_derived_keys) and any(x in sd for x in dwi_keys):
                unique_dic["error"] = " ".join("Acquisition appears to be a TRACE, FA, or \
                    ADC, which are unsupported by ezBIDS and will therefore not \
                    be converted".split())
                unique_dic["message"] = " ".join("Acquisition is believed to be dwi-derived \
                    (TRACE, FA, ADC), which are not supported by BIDS and will not \
                    be converted. Please modify if incorrect".split())
                unique_dic["type"] = "exclude"


            # Single band reference (sbref) for func or dwi
            elif "sbref" in sd:
                unique_dic["suffix"] = "sbref"

                if "DIFFUSION" in unique_dic["ImageType"]:
                    unique_dic["datatype"] = "dwi"
                    unique_dic["message"] = " ".join("Acquisition is believed to be \
                        dwi/sbref because 'DIFFUSION is in the ImageType and 'sbref' \
                        is in the SeriesDescription".split())
                else:
                    unique_dic["datatype"] = "func"
                    unique_dic["message"] = " ".join("Acquisition is believed to be \
                        func/sbref because 'sbref' is in the SeriesDescription".split())

            elif unique_dic["SeriesDescription"] == "n/a" and unique_dic["NumVolumes"] == 1 and unique_dic["nibabel_image"].ndim == 3 and any(x in sd for x in func_keys):
                unique_dic["datatype"] = "func"
                unique_dic["suffix"] = "sbref"
                unique_dic["message"] = " ".join("Acquisition is believed to be \
                        func/sbref the acquisition is 4D, has one volume, and \
                        information is provided by ProtocolName".split())

            # Functional BOLD
            elif any(x in sd for x in func_keys) or (len([x for x in func_keys if x in sd_sparse]) and len([x for x in func_keys if x in sd_sparse][-1]) > 3) and "sbref" not in sd:
                if any(x in sd for x in func_keys):
                    piece = sd
                else:
                    piece = sd_sparse
                    
                unique_dic["datatype"] = "func"
                unique_dic["suffix"] = "bold"
                unique_dic["message"] = " ".join("Acquisition is believed to be \
                    func/bold because '{}' is in the SeriesDescription \
                    (but not 'sbref'). Please modify if incorrect".format([x for x in func_keys if re.findall(x, piece)][0]).split())

            # T1w
            elif any(x in sd for x in t1w_keys) or (len([x for x in t1w_keys if x in sd_sparse]) and len([x for x in t1w_keys if x in sd_sparse][-1]) > 3):
                if any(x in sd for x in t1w_keys):
                    piece = sd
                else:
                    piece = sd_sparse
                
                unique_dic["datatype"] = "anat"
                unique_dic["suffix"] = "T1w"
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/T1w \
                    because '{}' is in the SeriesDescription. Please modify if \
                    incorrect".format([x for x in t1w_keys if re.findall(x, piece)][0]).split())

            # FLAIR
            elif any(x in sd for x in flair_keys) or (len([x for x in flair_keys if x in sd_sparse]) and len([x for x in flair_keys if x in sd_sparse][-1]) > 3):
                if any(x in sd for x in flair_keys):
                    piece = sd
                else:
                    piece = sd_sparse
                
                unique_dic["datatype"] = "anat"
                unique_dic["suffix"] = "FLAIR"
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/FLAIR \
                    because '{}' is in the SeriesDescription. Please modify if \
                    incorrect".format([x for x in flair_keys if re.findall(x, piece)][0]).split())

            # T2w (typically have EchoTime > 100ms)
            elif any(x in sd for x in t2w_keys) and unique_dic["EchoTime"] > 100:
                if any(x in sd for x in t2w_keys):
                    piece = sd
                else:
                    piece = sd_sparse

                unique_dic["datatype"] = "anat"
                unique_dic["suffix"] = "T2w"
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/T2w \
                    because '{}' is in the SeriesDescription and EchoTime > 100ms. \
                    Please modify if incorrect".format([x for x in t2w_keys if re.findall(x, piece)][0]).split())

            # Chimap, typically referred to as Quantitative susceptibility map (QSM), or MEGRE
            elif any(x in sd for x in chimap_keys):
                if any(x in sd for x in t2w_keys):
                    piece = sd
                else:
                    piece = sd_sparse
            
                unique_dic["datatype"] = "anat"
                if "EchoNumber" not in unique_dic:
                    unique_dic["suffix"] = "Chimap"
                    unique_dic["message"] = " ".join("Acquisition is believed to be anat/Chimap \
                    because '{}' is in the SeriesDescription. \
                    Please modify if incorrect".format([x for x in chimap_keys if re.findall(x, piece)][0]).split())
                else:
                    unique_dic["suffix"] = "MEGRE"
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/MEGRE \
                    because '{}' is in the SeriesDescription and the EchoNumber key is in the json sidecar. \
                    Please modify if incorrect".format([x for x in chimap_keys if re.findall(x, piece)][0]).split())
            # PET
            elif any(x in sd for x in pet_keys) or (len([x for x in pet_keys if x in sd_sparse]) or "pypet2bids" in unique_dic.get("sidecar", {}).get("ConversionSoftware", "")) \
                or unique_dic.get("sidecar", {}).get("Modality", "") == "PT":
                unique_dic["datatype"] = "pet"
                unique_dic["suffix"] = "pet"
                unique_dic["message"] = " ".join("Acquisition is believed to be PET")\

            else:
                """Can"t discern info from SeriesDescription, try using ndim and
                number of volumes to see if this is a func/bold."""
                test = unique_dic["nibabel_image"]
                if test.ndim == 4 and not any(x in unique_dic["ImageType"] for x in ["DERIVED", "PERFUSION", "DIFFUSION", "ASL"]):
                    unique_dic["datatype"] = "func"
                    unique_dic["suffix"] = "bold"
                    if test.shape[3] >= 50:
                        unique_dic["message"] = " ".join("SeriesDescription did not provide \
                            adequate information regarding the type of acquisition; however, it is \
                            believed to be a func/bold because it contains >= 50 \
                            volumes and is 4D. Please modify if incorrect".split())
                    else:
                        unique_dic["type"] = "exclude"
                        unique_dic["message"] = " ".join("SeriesDescription did not provide \
                            adequate information regarding the type of acquisition; however, it is \
                            believed to be a func/bold because it is 4D. However, \
                            it contains less than 50 volumes, potentially suggesting \
                            a failure/restart, or is some other type of data. This will be \
                            excluded from BIDS conversion. Please modify if incorrect".split())


                # Assume not BIDS-compliant acquisition, unless user specifies otherwise
                else:
                    unique_dic["error"] = " ".join("Acquisition cannot be resolved. Please \
                        determine whether or not this acquisition should be \
                        converted to BIDS".split())
                    unique_dic["message"] = " ".join("Acquisition is unknown because there \
                        is not enough adequate information, primarily in the \
                        SeriesDescription. Please modify if acquisition is desired \
                        for BIDS conversion, otherwise the acquisition will not be \
                        converted".split())
                    unique_dic["type"] = "exclude"

        """ Combine datatype and suffix to create type variable, which
        is needed for internal brainlife.io storage. """
        if "exclude" not in unique_dic["type"]:
            unique_dic["type"] = unique_dic["datatype"] + "/" + unique_dic["suffix"]

        """ For non-normalized anatomical acquisitions, provide message that
        they may have poor CNR and should consider excluding them from BIDS
        conversion if a corresponding normalized acquisition is present.
        """
        if "anat" in unique_dic["type"] and "NORM" not in unique_dic["ImageType"]:
            unique_dic["message"] = unique_dic["message"] + " ".join(" This acquisition \
            appears to be non-normalized, potentially having poor CNR. If there \
            is a corresponding normalized acquisition ('NORM' in ImageType \
            metadata field), consider excluding this current one from BIDS \
            conversion".split())

        # check that func/bold acquisitions have RepetitionTime, otherwise exclude
        if unique_dic["type"] == "func/bold":
            if unique_dic["RepetitionTime"] == "n/a":
                unique_dic["type"] = "exclude"
                unique_dic["message"] = " ".join("This acquisition is believed \
                            to be func/bold, yet does not contain RepetitionTime in  \
                            in the metadata. This acquisition will therefore be \
                            excluded from BIDS conversion. Please modify if \
                            incorrect".split())
                unique_dic["error"] = unique_dic["message"]

    return dataset_list_unique_series


def entity_labels_identification(dataset_list_unique_series):
    """
    Function to determine acquisition entity label information (e.g. dir-, echo-)
    based on acquisition metadata. Entities are then sorted in accordance with
    BIDS specification ordering.

    Parameters
    ----------
    dataset_list_unique_series : list
        List of dictionaries for each unique acquisition series in dataset.

    Returns
    -------
    dataset_list_unique_series : list
        updated input list
    """
    entity_ordering = yaml.load(open(os.path.join(analyzer_dir, entity_ordering_file)), Loader=yaml.FullLoader)

    tb1afi_tr = 1
    tb1srge_td = 1
    for index, unique_dic in enumerate(dataset_list_unique_series):

        series_entities = {}
        if unique_dic["SeriesDescription"] == "n/a":
            sd = unique_dic["ProtocolName"]
        else:
            sd = unique_dic["SeriesDescription"]

        json_path = unique_dic["json_path"]
        path = re.sub("[^A-Za-z0-9]+", "", unique_dic["nifti_path"]).lower()

        """ Check to see if entity labels can be determined from BIDS naming
        convention
        """
        for key in entities_yaml:
            if key not in ["subject", "session"]:
                entity = entities_yaml[key]["entity"]
                if len(entity) > 2: # an entity less than 3 characters could cause problems, though I don't think there are any entities currently this short
                    if entity == "res" and ("rest" in sd or "rest" in json_path): # short for "resolution", but might be confused with 'rest'
                        pass
                    elif entity in sd:
                        item = sd.split(entity)[-1][0] # what comes right after the entity
                        if item.isalpha() == False and item.isnumeric() == False: # non-alphanumeric character separates entity key from its value
                            entity = f"{entity}{item}"
                        series_entities[key] = re.split('[^a-zA-Z0-9]', sd.split(entity)[-1])[0]
                    elif entity in json_path:
                        item = json_path.split(entity)[-1][0]
                        if item.isalpha() == False and item.isnumeric() == False: # non-alphanumeric character separates entity key from its value
                            entity = f"{entity}{item}"
                        series_entities[key] = re.split('[^a-zA-Z0-9]', json_path.split(entity)[-1])[0]
                    else:
                        series_entities[key] = ""
                else:
                    series_entities[key] = ""  
            else:
                 series_entities[key] = ""     
                                
        """ If BIDS naming convention isn't detected, do a more thorough
        check for certain entities labels
        """
        # task
        func_rest_keys = ["rest", "rsfmri", "fcmri"]
        if any(x in re.sub("[^A-Za-z0-9]+", "", sd).lower() for x in func_rest_keys) and not series_entities["task"]:
            series_entities["task"] = "rest"
        else:
            match_index = [x for x,y in enumerate(re.search(x, sd, re.IGNORECASE) for x in cog_atlas_tasks) if y != None]
            if len(match_index):
                series_entities["task"] = cog_atlas_tasks[match_index[0]]

        # dir (required for fmap/epi an highly recommended for dwi/dwi)
        if any(x in unique_dic["type"] for x in ["fmap/epi", "dwi/dwi"]) and not series_entities["direction"]:
            series_entities["direction"] = unique_dic["direction"]

        # echo
        if unique_dic["EchoNumber"] and not any(x in unique_dic["type"] for x in ["fmap/epi", "fmap/magnitude1", "fmap/magnitude2", "fmap/phasediff", "fmap/phase1", "fmap/phase2", "fmap/fieldmap"]):
            series_entities["echo"] = str(unique_dic["EchoNumber"])
            # Warn user about non-RMS multi-echo anatomical acquisitions
            if "anat" in unique_dic["type"] and "EchoNumber" in unique_dic["sidecar"] and "MEAN" not in unique_dic["ImageType"]:
                # unique_dic["type"] = "exclude"
                unique_dic["message"] = unique_dic["message"] + ". " + " ".join("Acquisition also appears to be an \
                    anatomical multi-echo, but not the combined RMS file. If the RMS file \
                    exists it might be ideal to exclude this acquisition and only save \
                    the RMS file.".split())

        # flip
        if any(x in unique_dic["type"] for x in ["anat/VFA", "anat/MPM", "anat/MTS", "fmap/TB1EPI", "fmap/TB1DAM"]) and "FlipAngle" in unique_dic["sidecar"]:
            regex = re.compile('flip([1-9]*)')
            try:
                series_entities["flip"] = regex.findall(re.sub("[^A-Za-z0-9]+", "", sd).lower())[0]
            except:
                series_entities["flip"] = ""

        # acq
        if any(x in unique_dic["type"] for x in ["fmap/TB1TFL", "fmap/TB1RFM"]):
            if "FLIP ANGLE MAP" in unique_dic["ImageType"]:
                series_entities["acquisition"] = "fmap"
            else:
                series_entities["acquisition"] = "anat"

        if any(x in unique_dic["type"] for x in ["fmap/TB1AFI"]):
            series_entities["acquisition"] = "tr" + str(tb1afi_tr)
            tb1afi_tr += 1

        if any(x in unique_dic["type"] for x in ["fmap/TB1SRGE"]) and "DelayTime" in unique_dic["sidecar"]:
            series_entities["acquisition"] = "td" + str(tb1srge_td)
            tb1srge_td += 1

        if any(x in unique_dic["type"] for x in ["fmap/RB1COR"]) and "ReceiveCoilName" in unique_dic["sidecar"]:
            if "Head" in unique_dic["sidecar"]["ReceiveCoilName"]:
                series_entities["acquisition"] = "head"
            elif "Body" in unique_dic["sidecar"]["ReceiveCoilName"]:
                series_entities["acquisition"] = "body"

        # inversion
        if any(x in unique_dic["type"] for x in ["anat/MP2RAGE", "anat/IRT1"]) and "InversionTime" in unique_dic["sidecar"]:
            inversion_time = unique_dic["sidecar"]["InversionTime"]
            regex = re.compile('inv([1-9]*)')
            try:
                series_entities["inversion"] = regex.findall(re.sub("[^A-Za-z0-9]+", "", sd).lower())[0]
            except:
                series_entities["inversion"] = ""

        # reconstruction
        if "wave" in sd:
            series_entities["reconstruction"] = "wave"

        # part
        if "REAL" in unique_dic["ImageType"]:
            series_entities["part"] = "real"
        elif "IMAGINARY" in unique_dic["ImageType"]:
            series_entities["part"] = "imag"
        elif "fmap" not in unique_dic["type"] and "PHASE" in unique_dic['ImageType']:
            series_entities["part"] = "phase"
        else:
            pass

        """ Replace periods in series entities with "p", if found. If other
        non alphanumeric characters are found in the entity labels, remove them """
        for key, value in series_entities.items():
            if "." in value:
                series_entities[key] = value.replace(".", "p")
            elif not value.isalpha():
                series_entities[key] = re.sub("[^A-Za-z0-9]+", "", value)
            else:
                pass

        # Order the entities labels according to the BIDS specification
        series_entities = dict(sorted(series_entities.items(), key=lambda pair: entity_ordering.index(pair[0])))

        unique_dic["entities"] = series_entities

    return dataset_list_unique_series

def check_part_entity(dataset_list_unique_series):
    """ Certain data contain the part-phase entity key/value pair. 
        If this occurs, expose the part-mag key/value pair for the 
        corresponding data.
    """
    part_phase_data = [x for x in dataset_list_unique_series if x["entities"]["part"] == "phase"]

    for part in part_phase_data:
        mag_data = [x for x in dataset_list_unique_series
                    if x != part
                    and x["SeriesDescription"] == part["SeriesDescription"]
                    and x["type"] == part["type"]
                    and {key:val for key, val in x["entities"].items() if key != "part"} == {key:val for key, val in part["entities"].items() if key != "part"}
                    ]

        if len(mag_data) and len(mag_data) == 1:
            mag_data[0]["entities"]["part"] = "mag"
        
    return dataset_list_unique_series

def update_dataset_list(dataset_list, dataset_list_unique_series):
    """
    Update the dataset_list with information that we found from the unique
    series list. Since the unique_series_list does not contain all dataset
    acquisitions, use the unique series ID (series_idx) to port information
    over.
    """
    for unique_dic in dataset_list_unique_series:
        for data in dataset_list:
            if data["series_idx"] == unique_dic["series_idx"]:
                data["entities"] = unique_dic["entities"]
                data["type"] = unique_dic["type"]
                data["forType"] = unique_dic["forType"]
                data["error"] = unique_dic["error"]
                data["message"] = unique_dic["message"]
                data["IntendedFor"] = unique_dic["IntendedFor"]
                data["B0FieldIdentifier"] = unique_dic["B0FieldIdentifier"]
                data["B0FieldSource"] = unique_dic["B0FieldSource"]

    return dataset_list


def modify_objects_info(dataset_list):
    """
    Make any necessary changes to the objects level, which primarily entails
    adding a section ID value to each acquisition, creating image screenshots,
    and clean up (i.e. removing identifying metadata information).

    Parameters
    ----------
    dataset_list : list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files

    Returns
    -------
    objects_list : list
        List of dictionaries of all dataset acquisitions
    """
    objects_list = []

    entity_ordering = yaml.load(open(os.path.join(analyzer_dir, entity_ordering_file)), Loader=yaml.FullLoader)

    # Find unique subject/session idx pairs in dataset and sort them
    subj_ses_pairs = [[x["subject_idx"], x["session_idx"]] for x in dataset_list]
    unique_subj_ses_pairs = sorted([list(i) for i in set(tuple(i) for i in subj_ses_pairs)])

    for unique_subj_ses in unique_subj_ses_pairs:
        scan_protocol = [x for x in dataset_list
                         if x["subject_idx"] == unique_subj_ses[0]
                         and x["session_idx"] == unique_subj_ses[1]]

        objects_data = []

        """ Peruse scan protocol to check for potential issues and add some
        additional information. """

        for p, protocol in enumerate(scan_protocol):
            image = protocol["nibabel_image"]
            protocol["headers"] = str(image.header).splitlines()[1:]

            object_img_array = image.dataobj
            # PET images are scaled, type will be float <f4 
            if object_img_array.dtype not in ["<i2", "<u2"] and protocol.get("sidecar", {}).get("Modality", "") != "PT":
                # Weird edge case where data array is RGB instead of integer
                protocol["exclude"] = True
                protocol["error"] = " ".join("The data array for this \
                    acquisition is improper, likely suggesting some issue \
                    with the corresponding DICOMS".split())
                protocol["message"] = protocol["error"]
                protocol["type"] = "exclude"
            
            # Check for negative dimesions and exclude from BIDS conversion if they exist
            if len([x for x in image.shape if x < 0]):
                protocol["exclude"] = True
                protocol["type"] = "exclude"
                protocol["error"] = "Image contains negative dimension(s) and cannot be converted to BIDS format"
                protocol["message"] = "Image contains negative dimension(s) and cannot be converted to BIDS format"

            if protocol["error"]:
                protocol["error"] = [protocol["error"]]
            else:
                protocol["error"] = []

            objects_entities = dict(zip([x for x in entities_yaml], [""]*len([x for x in entities_yaml])))

            # Re-order entities to what BIDS expects
            objects_entities = dict(sorted(objects_entities.items(), key=lambda pair: entity_ordering.index(pair[0])))

            # Make items list (part of objects list)
            items = []
            for item in protocol["paths"]:
                if ".bval" in item:
                    items.append({"path":item,
                                  "name":"bval"})
                elif ".bvec" in item:
                    items.append({"path":item,
                                  "name":"bvec"})
                elif ".json" in item:
                    items.append({"path":item,
                                  "name":"json",
                                  "sidecar":protocol["sidecar"]})
                elif ".nii.gz" in item:
                    items.append({"path":item,
                                  "name":"nii.gz",
                                  "pngPaths": [],
                                  "moviePath": None,
                                  "headers":protocol["headers"]})


            # Objects-level info for ezBIDS_core.json
            objects_info = {"subject_idx": protocol["subject_idx"],
                            "session_idx": protocol["session_idx"],
                            "series_idx": protocol["series_idx"],
                            "AcquisitionDate": protocol["AcquisitionDate"],
                            "AcquisitionTime": protocol["AcquisitionTime"],
                            "SeriesNumber": protocol["SeriesNumber"],
                            "ModifiedSeriesNumber": protocol["ModifiedSeriesNumber"],
                            "IntendedFor": protocol["IntendedFor"],
                            "B0FieldIdentifier": protocol["B0FieldIdentifier"],
                            "B0FieldSource": protocol["B0FieldSource"],
                            "entities": objects_entities,
                            "items": items,
                            "PED": protocol["direction"],
                            "analysisResults": {
                                "NumVolumes": protocol["NumVolumes"],
                                "errors": protocol["error"],
                                "warnings": [],
                                "filesize": protocol["filesize"],
                                "orientation": protocol["orientation"],
                                "section_id": 1}
                            }
            objects_data.append(objects_info)

        objects_list.append(objects_data)

    # Flatten list of lists
    objects_list = [x for y in objects_list for x in y]

    return objects_list

def extract_series_info(dataset_list_unique_series):
    """
    Extract a subset of the acquistion information, which will be displayed on
    the Series-level page of the ezBIDS UI.

    Parameters
    ----------
    dataset_list_unique_series : list
        List of dictionaries for each unique acquisition series in dataset.

    Returns
    -------
    ui_series_info_list : list
        List of dictionaries containing subset of acquisition information to be
        displayed to user on ezBIDS Series-level UI
    """
    ui_series_info_list = []
    for unique_dic in dataset_list_unique_series:
        ui_series_info = {"SeriesDescription": unique_dic["SeriesDescription"],
                          "EchoTime": unique_dic["EchoTime"],
                          "ImageType": unique_dic["ImageType"],
                          "RepetitionTime": unique_dic["RepetitionTime"],
                          "NumVolumes": unique_dic["NumVolumes"],
                          "IntendedFor": unique_dic["IntendedFor"],
                          "B0FieldIdentifier": unique_dic["B0FieldIdentifier"],
                          "B0FieldSource": unique_dic["B0FieldSource"],
                          "nifti_path": unique_dic["nifti_path"],
                          "series_idx": unique_dic["series_idx"],
                          "AcquisitionDateTime": unique_dic["AcquisitionDateTime"],
                          "entities": unique_dic["entities"],
                          "type": unique_dic["type"],
                          "forType": unique_dic["forType"],
                          "error": unique_dic["error"],
                          "message": unique_dic["message"],
                          "object_indices": []
                          }

        ui_series_info_list.append(ui_series_info)

    return ui_series_info_list

def setVolumeThreshold(dataset_list_unique_series, objects_list):
    """
    Determine a volume threshold for all func/bold acquisitions in dataset,
    using the following heuristic:


    Parameters
    ----------
    dataset_list_unique_series : list
        List of dictionaries of unique series
    objects_list: list
        List of dictionaries of all dataset objects
    """

    func_series = [x for x in dataset_list_unique_series if "func" in x["type"]
                   and x["type"] != "func/sbref" and x["RepetitionTime"] != "n/a"]

    if len(func_series):
        for func in func_series:
            series_idx = func["series_idx"]
            tr = func["RepetitionTime"]
            corresponding_objects_volumes = [x["analysisResults"]["NumVolumes"]
                                             for x in objects_list
                                             if x["series_idx"] == series_idx]
            minNumVolumes = min(corresponding_objects_volumes)
            maxNumVolumes = max(corresponding_objects_volumes)
            numVolumes1min = floor(60/tr)

            if maxNumVolumes <= numVolumes1min: # set default as # volumes after 1 minute
                volumeThreshold = numVolumes1min
            else:
                if minNumVolumes == maxNumVolumes: # set threshold at max NumVolumes
                    volumeThreshold = maxNumVolumes
                else: # set threshold at 50% of max NumVolumes, or min NumVolumes if it's greater than half
                    half = floor(maxNumVolumes/2)
                    if minNumVolumes > half:
                        volumeThreshold = minNumVolumes
                    else:
                        volumeThreshold = half
            
            volumeThreshold = 30 # temporary, but setting threshold low for debugging purposes

            # With volume threshold, exclude objects that don't pass it
            corresponding_objects = [x for x in objects_list if x["series_idx"] == series_idx]
            for obj in corresponding_objects:
                if obj["analysisResults"]["NumVolumes"] < volumeThreshold:
                    obj["exclude"] = True
                    obj["analysisResults"]["errors"] = [" ".join("Acquisition is \
                        believed to be func/bold and contains {} volumes, which \
                        is less than the threshold value of {} volumes. Therefore, \
                        this acquisition will be excluded from BIDS conversion.\
                        Please modify if incorrect".format(obj["analysisResults"]["NumVolumes"], volumeThreshold).split())]

# def finalized_configuration(uploaded_json_list):
#     finalized = [json for json in uploaded_json_list if "finalized.json" in json]
#     if len(finalized):
#         finalized_config = finalized[0]
#         finalized_config = open(finalized_config)
#         finalized_config = json.load(finalized_config, strict=False)
#     else:
#         pass

##################### Begin #####################

print("########################################")
print("Beginning conversion process of uploaded dataset")
print("########################################")
print("")

# README
readme = generate_readme(DATA_DIR, bids_compliant)

# dataset description information
dataset_description_dic = generate_dataset_description(DATA_DIR, bids_compliant)

# participantsColumn portion of ezBIDS_core.json
participants_column_info = generate_participants_columns(DATA_DIR, bids_compliant)

# Generate list of all possible Cognitive Atlas task terms
cog_atlas_tasks = find_cog_atlas_tasks(cog_atlas_url)

# Load dataframe containing all uploaded files
uploaded_json_list = pd.read_csv("list", header=None, lineterminator='\n').to_numpy().flatten().tolist()

# finalized_configuration(uploaded_json_list)

# Filter for files that ezBIDS can't use
uploaded_files_list = modify_uploaded_dataset_list(uploaded_json_list)

# Create the dataset list of dictionaries
dataset_list = generate_dataset_list(uploaded_files_list)

# Determine subject (and session) information
dataset_list, subjects_information, participants_info = determine_subj_ses_IDs(dataset_list, bids_compliant)

# Make a new list containing the dictionaries of only unique dataset acquisitions
dataset_list, dataset_list_unique_series = determine_unique_series(dataset_list, bids_compliant)

# Identify datatype and suffix information
dataset_list_unique_series = datatype_suffix_identification(dataset_list_unique_series)

# Identify entity label information
dataset_list_unique_series = entity_labels_identification(dataset_list_unique_series)
for index, unique_dic in enumerate(dataset_list_unique_series):
    print(unique_dic["message"])

dataset_list_unique_series = check_part_entity(dataset_list_unique_series)

# If BIDS-compliant dataset uploaded, set and apply IntendedFor mapping
dataset_list_unique_series = set_IntendedFor_B0FieldIdentifier_B0FieldSource(dataset_list_unique_series, bids_compliant)

# Port series level information to all other acquistions (i.e. objects level) with same series info
dataset_list = update_dataset_list(dataset_list, dataset_list_unique_series)

# Apply a few other changes to the objects level
objects_list = modify_objects_info(dataset_list)

# Map unique series IDs to all other acquisitions in dataset that have those parameters
for index, unique_dic in enumerate(dataset_list_unique_series):

    print(" ".join("Unique data acquisition file {}, \
        Series Description {}, \
        was determined to be {}, \
        with entity labels {} \
        ".format(unique_dic["nifti_path"], unique_dic["SeriesDescription"], unique_dic["type"], [x for x in unique_dic["entities"].items() if x[-1] != ""]).split()))
    print("")
    print("")


# Set volume threshold for func/bold acquisitions
setVolumeThreshold(dataset_list_unique_series, objects_list)

# Extract important series information to display in ezBIDS UI
ui_series_info_list = extract_series_info(dataset_list_unique_series)

# Convert information to dictionary
EZBIDS = {  "readme": readme,
            "datasetDescription": dataset_description_dic,
            "subjects": subjects_information,
            "participantsColumn": participants_column_info,
            "participantsInfo": participants_info,
            "series": ui_series_info_list,
            "objects": objects_list
          }

# Write dictionary to ezBIDS_core.json
with open("ezBIDS_core.json", "w") as fp:
    json.dump(EZBIDS, fp, indent=3)

print("--- Analyzer completion time: {} seconds ---".format(time.time() - start_time))
