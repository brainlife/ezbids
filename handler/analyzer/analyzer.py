# !/usr/bin/env python3
"""
Created on Fri Jun 26 08:37:56 2020

This code represents ezBIDS's attempt to determine BIDS information (subject/session mapping,
datatype, suffix, entitiy labels [acq, run, dir, etc]) based on dcm2niix output.
This information is then displayed in the ezBIDS UI, where users can make
edits/modifications as they see fit, before finalizing their data into a
BIDS-compliant dataset.

@author: dlevitas
"""

from __future__ import division
import yaml
import time
import os
import sys
import re
import json
import warnings
from operator import itemgetter
from urllib.request import urlopen
from math import floor
import pandas as pd
import numpy as np
import nibabel as nib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
plt.style.use("dark_background")
warnings.filterwarnings("ignore")

DATA_DIR = sys.argv[1]

datatypes_yaml = yaml.load(open("../bids-specification/src/schema/objects/datatypes.yaml"))
entities_yaml = yaml.load(open("../bids-specification/src/schema/objects/entities.yaml"))
suffixes_yaml = yaml.load(open("../bids-specification/src/schema/objects/suffixes.yaml"))
datatype_suffix_rules = "../bids-specification/src/schema/rules/datatypes"
entity_ordering_file = "../bids-specification/src/schema/rules/entities.yaml"

cog_atlas_url = "http://cognitiveatlas.org/api/v-alpha/task"

start_time = time.time()
analyzer_dir = os.getcwd()

os.chdir(DATA_DIR)

######## Functions ########
def cog_atlas_tasks(url):
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
    tasks = [x for x in tasks if len(x) > 0] # Remove empty task name terms
    tasks = sorted(tasks, key=str.casefold) # sort alphabetically, but ignore case

    return tasks


def create_DWIshell_screenshots(nifti_path, nibabel_nifti_obj, bval_path):
    """
    Generates PNG screenshot of each unique DWI shell (e.g. unique b-value(s))

    Parameters
    ----------
    nifti_path: str
        location of nifti file

    nibabel_nifti_obj : nibabel.nifti1.Nifti1Image
        result of nib.load(nifti_file_path)

    bval_path: str
        location of corresponding bval file


    Returns
    -------
    pngPaths: list
        list of screenshots, each screenshot pertains to unique bval
    """
    pngPaths = []
    image = nibabel_nifti_obj
    bvals = [floor(float(x)) for x in pd.read_csv(bval_path, delim_whitespace=True).columns.tolist()]
    modified_bvals = [round(x, -2) for x in bvals]
    unique_bvals = np.unique(modified_bvals).tolist()

    for bval in unique_bvals:
        object_img_array = image.dataobj[..., modified_bvals.index(bval)]

        slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
        slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
        slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]

        fig, axes = plt.subplots(1, 3, figsize=(9, 3))
        for index, slices in enumerate([slice_x, slice_y, slice_z]):
            axes[index].imshow(slices.T, cmap="gray", origin="lower", aspect="auto")
            axes[index].axis("off")
        plt.tight_layout(pad=0, w_pad=0, h_pad=0)

        fig.canvas.draw()

        w,h = fig.canvas.get_width_height()
        buf = np.fromstring(fig.canvas.tostring_argb(), dtype=np.uint8)
        buf.shape = (w,h,4)

        buf = np.roll(buf,3,axis=2)

        w,h,d = buf.shape
        png = Image.frombytes("RGBA", (w,h), buf.tostring())
        png.save("{}_shell-{}.png".format(nifti_path[:-7], bval))

        pngPaths.append("{}_shell-{}.png".format(nifti_path[:-7], bval))

    return pngPaths


def create_screenshots(nifti_path, nibabel_nifti_obj, num_volumes):
    """
    Generates PNG screenshot of each acquisition

    Parameters
    ----------
    nifti_path: str
        location of nifti file

    nibabel_nifti_obj : nibabel.nifti1.Nifti1Image
        result of nib.load(nifti_file_path)

    num_volumes: int
        number of volumes in the nifti file


    Returns
    -------
    pngPaths: list
        list of 1, containing file path of screenshot
    """
    image = nibabel_nifti_obj
    object_img_array = image.dataobj

    if num_volumes > 1:
        object_img_array = image.dataobj[..., 1]
    else:
        object_img_array = image.dataobj[:]

    slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
    slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
    slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]

    fig, axes = plt.subplots(1, 3, figsize=(9, 3))
    for index, slices in enumerate([slice_x, slice_y, slice_z]):
        axes[index].imshow(slices.T, cmap="gray", origin="lower", aspect="auto")
        axes[index].axis("off")
    plt.tight_layout(pad=0, w_pad=0, h_pad=0)

    fig.canvas.draw()

    w,h = fig.canvas.get_width_height()
    buf = np.fromstring(fig.canvas.tostring_argb(), dtype=np.uint8)
    buf.shape = (w,h,4)

    buf = np.roll(buf,3,axis=2)

    w,h,d = buf.shape
    png = Image.frombytes("RGBA", (w,h), buf.tostring())
    png.save("{}.png".format(nifti_path[:-7]))

    return ["{}.png".format(nifti_path[:-7])]


def correct_pe(pe_direction, ornt):
    """
    Takes phase encoding direction (pe_direction) and image orientation (ornt)
    to correct pe_direction if need be. This correction occurs if pe_direction
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
    Takes [corrected] pe_direction (pe_direction) and image orientation (ornt)
    to determine "_dir-" entity label, which is required for specific
    acquisitions.

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
                          if "parrec" not in json.lower()]

    # Sort uploaded_json_list
    uploaded_json_list.sort()

    # Parse json files
    for json_file in uploaded_json_list:
        json_data = open(json_file)
        json_data = json.load(json_data, strict=False)

        # Only want json files with corresonding nifti (and bval/bvec) and if
        # the files come from dcm2niix
        if "ConversionSoftware" in json_data and json_data["ConversionSoftware"] == "dcm2niix":
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
    BIDS-related information (e.g. entitiy labels).

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

        corresponding_nifti = [x for x in nifti_list if json_file[:-4] in x
                               if "nii.gz" in x][0]

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
            patient_name = "NA"

        if "PatientID" in json_data:
            patient_id = json_data["PatientID"]
        else:
            patient_id = "NA"

        # Find PatientBirthDate
        if "PatientBirthDate" in json_data:
            patient_birth_date = json_data["PatientBirthDate"].replace("-", "")
        else:
            patient_birth_date = "00000000"

        # Find PatientSex
        patient_sex = "N/A"
        if "PatientSex" in json_data:
            if json_data["PatientSex"] in ["M", "F"]:
                patient_sex = json_data["PatientSex"]

        """
        Select subject ID to display.
        Subject ID precedence order if explicit subject ID (i.e. ReproIn) is not
        found is: PatientName > PatientID > PatientBirthDate
        """
        subject = "NA"
        for value in [json_file, patient_name, patient_id]:
            if any(x in value.lower() for x in ["sub-", "subject-", "sub_", "subject_"]):
                subject = re.split("[^a-zA-Z0-9]+", re.compile(r"sub-|subject-|sub_|subject_", re.IGNORECASE).split(value)[-1])[0]
                break

        if subject == "NA":
            if patient_name != "NA":
                subject = patient_name
            elif patient_id != "NA":
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
            if any(x in value.lower() for x in ["ses-", "session-", "ses_", "session_"]):
                session = re.split("[^a-zA-Z0-9]+", re.compile(r"ses-|session-|ses_|session_", re.IGNORECASE).split(value)[-1])[0]
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

        # Find RepetitionTime
        if "RepetitionTime" in json_data:
            repetition_time = json_data["RepetitionTime"]
        else:
            repetition_time = "N/A"

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
        else:
            series_description = "N/A"

        # Find ProtocolName
        if "ProtocolName" in json_data:
            protocol_name = json_data["ProtocolName"]
        else:
            protocol_name = "N/A"

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
            "PatientAge": "N/A",
            "subject": subject,
            "session": session,
            "SeriesNumber": series_number,
            "ModifiedSeriesNumber": mod_series_number,
            "AcquisitionDateTime": acquisition_date_time,
            "AcquisitionDate": acquisition_date,
            "AcquisitionTime": acquisition_time,
            "SeriesDescription": series_description,
            "ProtocolName": protocol_name,
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
            "TaskName": "",
            "exclude": False,
            "filesize": filesize,
            "NumVolumes": volume_count,
            "forType": "",
            "error": None,
            "section_idx": 1,
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

def determine_subj_ses_IDs(dataset_list):
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
    # Determine unique subjects from uploaded dataset
    for sub in np.unique([x["subject"] for x in dataset_list]):
        sub_dics_list = [x for x in dataset_list if x["subject"] == sub]

        # Organize phenotype (sex, age) information
        phenotype_info = list({"sex":x["PatientSex"],"age":x["PatientAge"]} for x in sub_dics_list)[0]

        # Give each subject a unique subject_idx value
        for x in sub_dics_list:
            x["subject_idx"] = subject_idx_counter
        subject_idx_counter += 1

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
                            "PatientBirthDate": [x["PatientName"] for x in sub_dics_list if x["session"] == ses_info["session"] and x["AcquisitionDate"] == ses_info["AcquisitionDate"]][0]
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
                            "phenotype": phenotype_info,
                            "exclude": False,
                            "sessions": [{k: v for k, v in d.items() if k != "session_idx" and k != "AcquisitionTime"} for d in unique_ses_date_times],
                            "validationErrors": []
                            }

        subjects_information.append(subject_ids_info)

    return dataset_list, subjects_information


def determine_unique_series(dataset_list):
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
    researhcers label their imaging protocols in less standardized ways.
    ezBIDS will attempt to determine datatype and suffix labels based on
    common keys/labels. """
    localizer_keys = ["localizer", "scout"]
    angio_keys = ["angio"]
    se_mag_phase_fmap_keys = ["fmap", "fieldmap", "spinecho", "sefmri", "semri"]
    flair_keys = ["t2spacedafl"]
    dwi_derived_keys = ["trace", "fa", "adc"]
    dwi_keys = ["dti", "dmri"]
    func_keys = ["func", "fmri", "mri", "task", "rest"]
    t1w_keys = ["tfl3d", "mprage", "spgr", "tflmgh", "t1mpr"]
    t2w_keys = ["t2"]
    tb1tfl_keys = ["tflb1map"]
    tb1rfm_keys = ["rfmap"]

    for index, unique_dic in enumerate(dataset_list_unique_series):

        sd = unique_dic["SeriesDescription"]

        """Make easier to find key characters/phrases in sd by removing
        non-alphanumeric characters and make everything lowercase."""
        sd = re.sub("[^A-Za-z0-9]+", "", sd).lower()

        # Try checking based on BIDS schema keys/labels
        for datatype in datatypes_yaml:
            if datatype in sd:
                unique_dic["datatype"] = datatype

            rule = yaml.load(open(os.path.join(analyzer_dir, datatype_suffix_rules, datatype) + ".yaml"))

            suffixes = [x for y in [x["suffixes"] for x in rule] for x in y]
            unhelpful_suffixes = ["fieldmap", "beh", "epi"]

            # Remove deprecated suffixes
            deprecated_suffixes = ["T2star", "FLASH", "PD"]
            suffixes = [x for x in suffixes if x not in deprecated_suffixes and x not in unhelpful_suffixes]

            if any(x.lower() in sd for x in suffixes):
                unique_dic["datatype"] = datatype
                unique_dic["suffix"] = [x for x in suffixes if re.findall(x.lower(), sd)][-1]
                unique_dic["message"] = " ".join("Acquisition is believed to \
                    be {}/{} because '{}' is in the SeriesDescription. Please \
                    modify if incorrect.".format(unique_dic["datatype"], unique_dic["suffix"], unique_dic["suffix"]).split())

            # Instances where users specify both mp2rage and UNI[T1] together, default to UNIT1
            if "DERIVED" and "UNI" in unique_dic["ImageType"]:
                unique_dic["datatype"] = "anat"
                unique_dic["suffix"] = "UNIT1"
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/UNIT1 \
                    because 'DERIVED' and 'UNI' are in the ImageType. Please modify \
                    if incorrect".split())

            """ Oftentimes, magnitude/phase[diff] acquisitions are called "gre-field-mapping",
            so shouldn't receive the fieldmap suffix """
            if "grefieldmap" in sd:
                unique_dic["datatype"] = ""
                unique_dic["suffix"] = ""

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

            # Angiography
            elif any(x in sd for x in angio_keys):
                unique_dic["type"] = "exclude"
                unique_dic["datatype"] = "anat"
                unique_dic["suffix"] = "angio"
                unique_dic["error"] = " ".join("Acqusition appears to be an Angiography \
                    acquisition, which is currently not supported by ezBIDS at \
                    this time, but will be in the future".split())
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/angio \
                    because '{}' is in the SeriesDescription. Please modify if \
                    incorrect. Currently, ezBIDS does not support Angiography \
                    conversion to BIDS".format([x for x in angio_keys if re.findall(x, sd)][0]).split())

            # TB1TFL field maps
            elif any(x in sd for x in tb1tfl_keys):
                unique_dic["datatype"] = "fmap"
                unique_dic["suffix"] = "TB1TFL"
                unique_dic["message"] = " ".join("Acquisition is believed to be a \
                    TB1TFL field map because 'tflb1map' is in the SeriesDescription. \
                    Please modify if incorrect".split())

            # TB1RFM field maps
            elif any(x in sd for x in tb1rfm_keys):
                unique_dic["datatype"] = "fmap"
                unique_dic["suffix"] = "TB1RFM"
                unique_dic["message"] = " ".join("Acquisition is believed to be a \
                    TB1RFM field map because 'rfmap' is in the SeriesDescription. \
                    Please modify if incorrect".split())

            # Magnitude/Phase[diff] and Spin Echo (SE) field maps
            elif any(x in sd for x in se_mag_phase_fmap_keys):
                unique_dic["datatype"] = "fmap"
                unique_dic["forType"] = "func/bold"

                if "EchoNumber" in unique_dic["sidecar"]:
                    if unique_dic["EchoNumber"] == 1 and "_e1_ph" not in unique_dic["json_path"]:
                        unique_dic["suffix"] = "magnitude1"
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            fmap/magnitude1 because '{}' is in SeriesDescription, \
                            EchoNumber == 1 in metadata, and the phrase '_e1_ph' \
                            is not in the filename. Please modify if \
                            incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, sd)][0]).split())
                    elif unique_dic["EchoNumber"] == 1 and "_e1_ph" in unique_dic["json_path"]:
                        unique_dic["suffix"] = "phase1"
                        unique_dic["message"] = " ".join("Acquisition is believed to \
                            be fmap/phase1 because '{}' is in SeriesDescription, \
                            EchoNumber == 1 in metadata, and the phrase '_e1_ph' is in \
                            the filename. Please modify if incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, sd)][0]).split())
                    elif unique_dic["EchoNumber"] == 2 and "_e2_ph" not in unique_dic["json_path"]:
                        unique_dic["suffix"] = "magnitude2"
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            fmap/magnitude2 because '{}' is in SeriesDescription, \
                            EchoNumber == 2 in metadata, and the phrase '_e2_ph' is \
                            not in the filename. Please modify if incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, sd)][0]).split())
                    elif unique_dic["EchoNumber"] == 2 and "_e2_ph" in unique_dic["json_path"] and "_e1_ph" in dataset_list_unique_series[index-2]["json_path"]:
                        unique_dic["suffix"] = "phase2"
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            fmap/phase2 because '{}' is in SeriesDescription, \
                            EchoNumber == 2 in metadata, and the phrase '_e2_ph' \
                            is in the filename and '_e1_ph' the one two before. \
                            Please modify if incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, sd)][0]).split())
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
                            conversion, otherwise the acqusition will not be \
                            converted".split())
                        unique_dic["message"] = unique_dcontains >= 50 \
                            volumes and is 4Dic["error"]
                        unique_dic["type"] = "exclude"

                # Spin echo field maps (for func)
                else:
                    unique_dic["suffix"] = "epi"
                    unique_dic["message"] = " ".join("Acquisition is believed to be fmap/epi \
                        because '{}' is in SeriesDescription, and does not contain \
                        metadata info associated with magnitude/phasediff acquisitions.\
                        Please modify if incorrect".format([x for x in se_mag_phase_fmap_keys if re.findall(x, sd)][0]).split())

            # spin echo field maps (for dwi)
            elif "DIFFUSION" in unique_dic["ImageType"] and "b0" in sd:
                unique_dic["datatype"] = "fmap"
                unique_dic["suffix"] = "epi"
                unique_dic["forType"] = "dwi/dwi"
                unique_dic["message"] = " ".join("Acquisition appears to be a fmap/epi meant \
                    for dwi/dwi, as 'DIFFUSION' is in ImageType, and 'b0' is in \
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
                            unique_dic["datatype"] = "anat"
                            unique_dic["suffix"] = "FLAIR"
                            unique_dic["message"] = " ".join("Acquisition is believed to be \
                                anat/FLAIR because '{}' is in the \
                                SeriesDescription. Please modify if incorrect".format([x for x in flair_keys if re.findall(x, sd)][0]).split())
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
                        unique_dic["error"] = " ".join("Acquisition appears to be a TRACE, \
                            FA, or ADC, which are unsupported by ezBIDS and will \
                            therefore not be converted".split())
                        unique_dic["message"] = " ".join("Acquisition is believed to be \
                            TRACE, FA, or ADC because there are bval & bvec files \
                            with the same SeriesNumber, and '{}' are in the \
                            SeriesDescription. Please modify if \
                            incorrect".format([x for x in dwi_derived_keys if re.findall(x, sd)][0]).split())
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

            elif any(x in sd for x in func_keys) and "sbref" not in sd:
                unique_dic["datatype"] = "func"
                unique_dic["suffix"] = "bold"
                unique_dic["message"] = " ".join("Acquisition is believed to be \
                    func/bold because '{}' is in the SeriesDescription \
                    (but not 'sbref'). Please modify if incorrect".format([x for x in func_keys if re.findall(x, sd)][0]).split())

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

            # T1w
            elif any(x in sd for x in t1w_keys):
                unique_dic["datatype"] = "anat"
                unique_dic["suffix"] = "T1w"
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/T1w \
                    because '{}' is in the SeriesDescription. Please modify if \
                    incorrect".format([x for x in t1w_keys if re.findall(x, sd)][0]).split())

            # FLAIR
            elif any(x in sd for x in flair_keys):
                unique_dic["datatype"] = "anat"
                unique_dic["suffix"] = "FLAIR"
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/FLAIR \
                    because '{}' is in the SeriesDescription. Please modify if \
                    incorrect".format([x for x in flair_keys if re.findall(x, sd)][0]).split())

            # T2w (typically have EchoTime > 100ms)
            elif any(x in sd for x in t2w_keys) and unique_dic["EchoTime"] > 100:
                unique_dic["datatype"] = "anat"
                unique_dic["suffix"] = "T2w"
                unique_dic["message"] = " ".join("Acquisition is believed to be anat/T2w \
                    because '{}' is in the SeriesDescription and EchoTime > 100ms. \
                    Please modify if incorrect".format([x for x in t2w_keys if re.findall(x, sd)][0]).split())

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
                        for BIDS conversion, otherwise the acqusition will not be \
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
            appers to be non-normalized, potentially having poor CNR. If there \
            is a corresponding normalized acquisition ('NORM' in ImageType \
            metadata field), consider excluding this current one from BIDS \
            conversion".split())

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
    entity_ordering = yaml.load(open(os.path.join(analyzer_dir, entity_ordering_file)))

    tb1afi_tr = 1
    for index, unique_dic in enumerate(dataset_list_unique_series):

        series_entities = {}
        sd = unique_dic["SeriesDescription"]

        """ Check to see if entity labels can be determined from ReproIn naming
        convention
        """
        for key in entities_yaml:
            entity = "_" + entities_yaml[key]["entity"] + "-"
            if entity in sd:
                series_entities[key] = sd.split(entity)[-1].split("_")[0]
            else:
                series_entities[key] = ""

        """ If ReproIn naming convention isn't detected, do a more thorough
        check for certain entities labels
        """
        # task
        func_rest_keys = ["rest", "rsfmri", "fcmri"]
        if any(x in re.sub("[^A-Za-z0-9]+", "", sd).lower() for x in func_rest_keys) and not series_entities["task"]:
            series_entities["task"] = "rest"
        else:
            match_index = [x for x,y in enumerate(re.search(x, sd, re.IGNORECASE) for x in cog_atlas_tasks) if y != None]
            if len(match_index) == 1:
                series_entities["task"] = cog_atlas_tasks[match_index[0]]

        # dir (required for fmap/epi an highly recommended for dwi/dwi)
        if any(x in unique_dic["type"] for x in ["fmap/epi", "dwi/dwi"]) and not series_entities["direction"]:
            series_entities["direction"] = unique_dic["direction"]

        # echo
        if unique_dic["EchoNumber"] and not any(x in unique_dic["type"] for x in ["fmap/epi", "fmap/magnitude1", "fmap/magnitude2", "fmap/phasediff", "fmap/phase1", "fmap/phase2", "fmap/fieldmap"]):
            series_entities["echo"] = str(unique_dic["EchoNumber"])
            # Exclude non-RMS multi-echo anatomical acquisitions
            if "anat" in unique_dic["type"] and "EchoNumber" in unique_dic["sidecar"] and "MEAN" not in unique_dic["ImageType"]:
                unique_dic["type"] = "exclude"
                unique_dic["message"] = " ".join("Acquisition appears to be an \
                    anatomical multi-echo, but not the combined RMS file. Since this is \
                    not the combined RMS file, this acquisition will not be set to \
                    exclude. Please modify if incorrect".split())

        # flip
        if any(x in unique_dic["type"] for x in ["anat/VFA", "anat/MPM", "anat/MTS", "fmap/TB1EPI"]) and "FlipAngle" in unique_dic["sidecar"]:
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

        # run (strip leading zeros, if any, as this isn't proper by BIDS standards)
        if series_entities["run"]:
            series_entities["run"] = series_entities["run"].lstrip("0")


        """ Replace periods in series entities with "p", if found. If other
        non alpha-numeric characters are found in the entity labels, remove them """
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

    entity_ordering = yaml.load(open(os.path.join(analyzer_dir, entity_ordering_file)))

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
            pngPaths = []
            image = protocol["nibabel_image"]
            protocol["headers"] = str(image.header).splitlines()[1:]

            object_img_array = image.dataobj
            if object_img_array.dtype not in ["<i2", "<u2"]:
                # Weird edge case where data array is RGB instead of intger
                protocol["exclude"] = True
                protocol["error"] = " ".join("The data array is for this \
                    acquisition is improper, likely suggesting some issue \
                    with the corresponding DICOMS".split())
                protocol["message"] = protocol["error"]
                protocol["type"] = "exclude"
            else:
                # Generate screenshot of every acquisition in dataset
                pngPaths.append(create_screenshots(protocol["nifti_path"], image, protocol["NumVolumes"]))

                # Generate screenshot(s) of every unique dwi/dwi shell (e.g. b-value(s))
                if protocol["type"] == "dwi/dwi":
                    try:
                        bval_path = [x for x in protocol["paths"] if ".bval" in x][0]
                        pngPaths.append(create_DWIshell_screenshots(protocol["nifti_path"], image, bval_path))
                    except:
                        print("Could not generate unique DWI shell screenshots for {}".format(protocol["nifti_path"]))

            pngPaths = [item for sublist in pngPaths for item in sublist] # flatten list of lists

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
                                  "pngPaths": pngPaths,
                                  "headers":protocol["headers"]})


            # Objects-level info for ezBIDS.json
            objects_info = {"subject_idx": protocol["subject_idx"],
                            "session_idx": protocol["session_idx"],
                            "series_idx": protocol["series_idx"],
                            "AcquisitionDate": protocol["AcquisitionDate"],
                            "AcquisitionTime": protocol["AcquisitionTime"],
                            "SeriesNumber": protocol["SeriesNumber"],
                            "ModifiedSeriesNumber": protocol["ModifiedSeriesNumber"],
                            "entities": objects_entities,
                            "items": items,
                            "analysisResults": {
                                "NumVolumes": protocol["NumVolumes"],
                                "errors": protocol["error"],
                                "filesize": protocol["filesize"],
                                "section_idx": 1},
                            "paths": protocol["paths"]}
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

##################### Begin #####################

print("########################################")
print("Beginning conversion process of uploaded dataset")
print("########################################")
print("")

# participantsColumn portion of ezBIDS.json
PARTICIPANTS_COLUMN = {"sex": {"LongName": "gender",
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

# Generate list of all possible Cognitive Atlas task terms
cog_atlas_tasks = cog_atlas_tasks(cog_atlas_url)

# Load dataframe containing all uploaded files
uploaded_json_list = pd.read_csv("list", header=None, sep="\n").to_numpy().flatten().tolist()

# Filter for files that ezBIDS can't use
uploaded_files_list = modify_uploaded_dataset_list(uploaded_json_list)

# Create the dataset list of dictionaries
dataset_list = generate_dataset_list(uploaded_files_list)

# Determine subject (and session) information
dataset_list, subjects_information = determine_subj_ses_IDs(dataset_list)

# Make a new list containing the dictionaries of only unique dataset acquisitions
dataset_list, dataset_list_unique_series = determine_unique_series(dataset_list)

# Identify datatype and suffix information
dataset_list_unique_series = datatype_suffix_identification(dataset_list_unique_series)

# Identify entity label information
dataset_list_unique_series = entity_labels_identification(dataset_list_unique_series)

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

# Extract important series information to display in ezBIDS UI
ui_series_info_list = extract_series_info(dataset_list_unique_series)

# Convert information to dictionary
EZBIDS = {"subjects": subjects_information,
          "participantsColumn": PARTICIPANTS_COLUMN,
          "series": ui_series_info_list,
          "objects": objects_list
          }

# Write dictionary to ezBIDS.json
with open("ezBIDS.json", "w") as fp:
    json.dump(EZBIDS, fp, indent=3)

print("--- Analyzer completion time: {} seconds ---".format(time.time() - start_time))
