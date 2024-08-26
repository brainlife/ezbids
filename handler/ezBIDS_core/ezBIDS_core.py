#!/usr/bin/env python3

"""
This code represents ezBIDS's attempt to determine BIDS information (subject/session mapping,
datatype, suffix, entity labels [acq, run, dir, etc]) based on dcm2niix output.
This information is then displayed in the ezBIDS UI, where users can make
edits/modifications as they see fit, before finalizing their data into a BIDS-compliant dataset.

@author: dlevitas
"""

from __future__ import division
import os
import re
import sys
import mne
import json
import yaml
import time
import numpy as np
import pandas as pd
import nibabel as nib
from pathlib import Path
from datetime import date
from natsort import natsorted
from operator import itemgetter
from urllib.request import urlopen

DATA_DIR = sys.argv[1]

PROJECT_DIR = Path(__file__).resolve().parents[2]
BIDS_SCHEMA_DIR = PROJECT_DIR / Path("bids-specification/src/schema")

datatypes_yaml = yaml.load(open(BIDS_SCHEMA_DIR / Path("objects/datatypes.yaml")), Loader=yaml.FullLoader)
entities_yaml = yaml.load(open(BIDS_SCHEMA_DIR / Path("objects/entities.yaml")), Loader=yaml.FullLoader)
suffixes_yaml = yaml.load(open(BIDS_SCHEMA_DIR / Path("objects/suffixes.yaml")), Loader=yaml.FullLoader)
dataset_description_yaml = yaml.load(open(BIDS_SCHEMA_DIR / Path("rules/dataset_metadata.yaml")),
                                     Loader=yaml.FullLoader)
datatype_suffix_rules = str(BIDS_SCHEMA_DIR / Path("rules/datatypes"))
entity_ordering_file = str(BIDS_SCHEMA_DIR / Path("rules/entities.yaml"))

cog_atlas_url = "http://cognitiveatlas.org/api/v-alpha/task"

accepted_datatypes = ["anat", "dwi", "fmap", "func", "meg", "perf", "pet", "beh"]  # Will add others later

MEG_extensions = [".ds", ".fif", ".sqd", ".con", ".raw", ".ave", ".mrk", ".kdf", ".mhd", ".trg", ".chn", ".dat"]

bids_compliant = pd.read_csv(f"{DATA_DIR}/bids_compliant.log", header=None).iloc[1][0]
if bids_compliant == "true":
    bids_compliant = True
else:
    bid_compliant = False

start_time = time.perf_counter()
analyzer_dir = os.getcwd()

today_date = date.today().strftime("%Y-%m-%d")

os.chdir(DATA_DIR)

# Functions


def _sidecar_json(raw, task, manufacturer, fname, datatype, emptyroom_fname=None, overwrite=True):
    """Create a sidecar json file depending on the suffix and save it.

    The sidecar json file provides meta data about the data
    of a certain datatype.

    MNE-BIDS function: https://github.com/mne-tools/mne-bids/blob/main/mne_bids/write.py#L777

    Parameters
    ----------
    raw : mne.io.Raw
        The data as MNE-Python Raw object.
    task : str
        Name of the task the data is based on.
    manufacturer : str
        Manufacturer of the acquisition system. For MEG also used to define the
        coordinate system for the MEG sensors.
    fname : str | mne_bids.BIDSPath
        Filename to save the sidecar json to.
    datatype : str
        Type of the data as in ALLOWED_ELECTROPHYSIO_DATATYPE.
    emptyroom_fname : str | mne_bids.BIDSPath
        For MEG recordings, the path to an empty-room data file to be
        associated with ``raw``. Only supported for MEG.
    overwrite : bool
        Whether to overwrite the existing file.
        Defaults to False.

    """
    from mne import Epochs
    from mne.io import BaseRaw
    from mne.utils import logger
    from mne.io.constants import FIFF
    from mne.chpi import get_chpi_info
    from collections import OrderedDict
    from mne.channels.channels import _get_meg_system
    from mne_bids.config import IGNORED_CHANNELS
    from mne_bids.utils import (_write_json, _infer_eeg_placement_scheme)

    sfreq = raw.info["sfreq"]
    try:
        powerlinefrequency = raw.info["line_freq"]
        powerlinefrequency = "n/a" if powerlinefrequency is None else powerlinefrequency
    except KeyError:
        raise ValueError(
            "PowerLineFrequency parameter is required in the sidecar files. "
            "Please specify it in info['line_freq'] before saving to BIDS, "
            "e.g. by running: "
            "    raw.info['line_freq'] = 60"
            "in your script, or by passing: "
            "    --line_freq 60 "
            "in the command line for a 60 Hz line frequency. If the frequency "
            "is unknown, set it to None"
        )

    if isinstance(raw, BaseRaw):
        rec_type = "continuous"
    elif isinstance(raw, Epochs):
        rec_type = "epoched"
    else:
        rec_type = "n/a"

    # determine whether any channels have to be ignored:
    n_ignored = len(
        [
            ch_name
            for ch_name in IGNORED_CHANNELS.get(manufacturer, list())
            if ch_name in raw.ch_names
        ]
    )
    # all ignored channels are trigger channels at the moment...

    n_megchan = len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_MEG_CH])
    n_megrefchan = len(
        [ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_REF_MEG_CH]
    )
    n_eegchan = len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_EEG_CH])
    n_ecogchan = len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_ECOG_CH])
    n_seegchan = len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_SEEG_CH])
    n_eogchan = len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_EOG_CH])
    n_ecgchan = len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_ECG_CH])
    n_emgchan = len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_EMG_CH])
    n_miscchan = len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_MISC_CH])
    n_stimchan = (
        len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_STIM_CH])
        - n_ignored
    )
    n_dbschan = len([ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_DBS_CH])
    nirs_channels = [ch for ch in raw.info["chs"] if ch["kind"] == FIFF.FIFFV_FNIRS_CH]
    n_nirscwchan = len(nirs_channels)
    n_nirscwsrc = len(
        np.unique([ch["ch_name"].split(" ")[0].split("_")[0] for ch in nirs_channels])
    )
    n_nirscwdet = len(
        np.unique([ch["ch_name"].split(" ")[0].split("_")[1] for ch in nirs_channels])
    )

    # Set DigitizedLandmarks to True if any of LPA, RPA, NAS are found
    # Set DigitizedHeadPoints to True if any "Extra" points are found
    # (DigitizedHeadPoints done for Neuromag MEG files only)
    digitized_head_points = False
    digitized_landmark = False
    if datatype == "meg" and raw.info["dig"] is not None:
        for dig_point in raw.info["dig"]:
            if dig_point["kind"] in [
                FIFF.FIFFV_POINT_NASION,
                FIFF.FIFFV_POINT_RPA,
                FIFF.FIFFV_POINT_LPA,
            ]:
                digitized_landmark = True
            elif dig_point["kind"] == FIFF.FIFFV_POINT_EXTRA and str(
                raw.filenames[0]
            ).endswith(".fif"):
                digitized_head_points = True
    software_filters = {
        "SpatialCompensation": {"GradientOrder": raw.compensation_grade}
    }

    # Compile cHPI information, if any.
    system, _ = _get_meg_system(raw.info)
    chpi = None
    hpi_freqs = []
    if datatype == "meg":
        # We need to handle different data formats differently
        if system == "CTF_275":
            try:
                mne.chpi.extract_chpi_locs_ctf(raw)
                chpi = True
            except RuntimeError:
                chpi = False
                logger.info("Could not find cHPI information in raw data.")
        elif system == "KIT":
            try:
                mne.chpi.extract_chpi_locs_kit(raw)
                chpi = True
            except (RuntimeError, ValueError):
                chpi = False
                logger.info("Could not find cHPI information in raw data.")
        elif system in ["122m", "306m"]:
            n_active_hpi = mne.chpi.get_active_chpi(raw, on_missing="ignore")
            chpi = bool(n_active_hpi.sum() > 0)
            if chpi:
                hpi_freqs, _, _ = get_chpi_info(info=raw.info, on_missing="ignore")
                hpi_freqs = list(hpi_freqs)

    # Define datatype-specific JSON dictionaries
    ch_info_json_common = [
        ("TaskName", task),
        ("Manufacturer", manufacturer),
        ("PowerLineFrequency", powerlinefrequency),
        ("SamplingFrequency", sfreq),
        ("SoftwareFilters", "n/a"),
        ("RecordingDuration", raw.times[-1]),
        ("RecordingType", rec_type),
    ]

    ch_info_json_meg = [
        ("DewarPosition", "n/a"),
        ("DigitizedLandmarks", digitized_landmark),
        ("DigitizedHeadPoints", digitized_head_points),
        ("MEGChannelCount", n_megchan),
        ("MEGREFChannelCount", n_megrefchan),
        ("SoftwareFilters", software_filters),
    ]

    if chpi is not None:
        ch_info_json_meg.append(("ContinuousHeadLocalization", chpi))
        ch_info_json_meg.append(("HeadCoilFrequency", hpi_freqs))

    if emptyroom_fname is not None:
        ch_info_json_meg.append(("AssociatedEmptyRoom", str(emptyroom_fname)))

    ch_info_json_eeg = [
        ("EEGReference", "n/a"),
        ("EEGGround", "n/a"),
        ("EEGPlacementScheme", _infer_eeg_placement_scheme(raw)),
        ("Manufacturer", manufacturer),
    ]

    ch_info_json_ieeg = [
        ("iEEGReference", "n/a"),
        ("ECOGChannelCount", n_ecogchan),
        ("SEEGChannelCount", n_seegchan + n_dbschan),
    ]

    ch_info_json_nirs = [("Manufacturer", manufacturer)]

    ch_info_ch_counts = [
        ("EEGChannelCount", n_eegchan),
        ("EOGChannelCount", n_eogchan),
        ("ECGChannelCount", n_ecgchan),
        ("EMGChannelCount", n_emgchan),
        ("MiscChannelCount", n_miscchan),
        ("TriggerChannelCount", n_stimchan),
    ]

    ch_info_ch_counts_nirs = [
        ("NIRSChannelCount", n_nirscwchan),
        ("NIRSSourceOptodeCount", n_nirscwsrc),
        ("NIRSDetectorOptodeCount", n_nirscwdet),
    ]

    # Stitch together the complete JSON dictionary
    ch_info_json = ch_info_json_common
    if datatype == "meg":
        append_datatype_json = ch_info_json_meg
    elif datatype == "eeg":
        append_datatype_json = ch_info_json_eeg
    elif datatype == "ieeg":
        append_datatype_json = ch_info_json_ieeg
    elif datatype == "nirs":
        append_datatype_json = ch_info_json_nirs
        ch_info_ch_counts.extend(ch_info_ch_counts_nirs)

    ch_info_json += append_datatype_json
    ch_info_json += ch_info_ch_counts
    ch_info_json = OrderedDict(ch_info_json)

    _write_json(fname, ch_info_json, overwrite)


def fix_multiple_dots(uploaded_img_list):
    '''
    Occasionally, data files with have multiple periods ('.') in their file names.
    This can cause problems when determining the file extension, so this function remove
    all extra periods except for the one at the end (assumined to be the extension).

    Parameters
    ----------
    uploaded_img_list : list
        List of data files derived from preprocess.sh

    Returns
    -------
    uploaded_img_list : list
        Same list, but with the possibility for corrected file names if they had extra
        periods that weren't the extension.
    '''

    for img_path in uploaded_img_list:
        img_file = img_path.split('/')[-1]
        typo_files = []
        fix = False
        if img_file.endswith('.nii.gz') and img_file.count('.') > 2:  # for MRI and PET
            fix = True
            ext = '.nii.gz'
        elif img_file.endswith('.v.gz') and img_file.count('.') > 2:  # ECAT-formatted PET
            fix = True
            ext = '.v.gz'
        elif img_file.endswith('.tsv.gz') and img_file.count('.') > 2:  # Eyetracking
            fix = True
            ext = '.tsv.gz'
        elif img_file.endswith('.json') and img_file.count('.') > 1:  # for PET blood
            fix = True
            ext = '.json'
        elif img_file.endswith(tuple(MEG_extensions)) and img_file.count('.') > 1:  # for MEG
            if not img_file.endswith('.ds'):
                fix = True
                ext = '.' + img_file.split('.')[-1]
        else:
            pass

        if fix is True:
            img_dir = os.path.dirname(img_path)

            corresponding_files = [
                img_dir + '/' + x for x in os.listdir(img_dir)
                if os.path.basename(img_path).split(ext)[0] in x
            ]

            if len(corresponding_files):
                for f in corresponding_files:
                    typo_files.append(f)

        if len(typo_files):
            for typo in typo_files:

                if typo.endswith('.nii.gz'):
                    ext = '.nii.gz'
                elif typo.endswith('.v.gz'):
                    ext = '.v.gz'
                elif typo.endswith('.tsv.gz'):
                    ext = '.tsv.gz'
                else:
                    ext = '.' + typo.split('.')[-1]

                typo_split_list = typo.split(ext)[0].split('.')

                new_file_name = f".{'_'.join(typo_split_list[1:])}{ext}"

                os.system(f'mv {typo} {new_file_name}')

                if typo in uploaded_img_list:
                    idx = uploaded_img_list.index(typo)
                    uploaded_img_list.pop(idx)
                    uploaded_img_list = natsorted(uploaded_img_list + [new_file_name])

            # Save to list file
            with open("list", "w") as f:
                for line in uploaded_img_list:
                    f.write(f"{line}\n")

    return uploaded_img_list


def generate_MEG_json_sidecars(uploaded_img_list):
    """
    Get the MEG data organized
    """
    img_files = [x.split("./")[-1] for x in uploaded_img_list]
    MEG_img_files = []
    for img in img_files:
        include = True
        if any(x in img for x in MEG_extensions):
            if ".ds" in str(Path(img).parent):
                # don't want subfolders or files to get caught, the ".ds" folder is essentially the data
                include = False

            if include is True:
                MEG_img_files.append(img)

    if len(MEG_img_files):
        """
        Generate the JSON metadata
        """
        from mne_bids.path import _parse_ext
        from mne_bids.sidecar_updates import _update_sidecar
        from mne_bids.config import MANUFACTURERS

        for meg in MEG_img_files:
            if meg.endswith('.ds'):
                ext = '.ds'
            else:
                ext = Path(meg).suffix

            fname = f"{DATA_DIR}/{meg}"
            json_output_name = fname.split(ext)[0] + ".json"
            raw = mne.io.read_raw(fname, verbose=0)
            acquisition_date_time = raw.info["meas_date"].strftime("%Y-%m-%dT%H:%M:%S.%f")
            acquisition_date = acquisition_date_time.split("T")[0]
            acquisition_time = acquisition_date_time.split("T")[-1]
            datatype = "meg"  # assume meg datatype for now
            task = "unknown"  # set placeholder label for task entity

            # get the manufacturer from the file in the Raw object
            _, ext = _parse_ext(raw.filenames[0])
            manufacturer = MANUFACTURERS.get(ext, "")

            # check a few parameters
            try:
                data_id = raw.info["subject_info"]["his_id"]
            except:
                data_id = "na"

            if (
                ("noise" in fname.lower() or "emptyroom" in fname.lower())
                or ("noise" in data_id.lower() or "emptyroom" in data_id.lower())
            ):
                sub = "sub-emptyroom"
                ses = "ses-" + str(raw.info["meas_date"].strftime("%Y%m%d"))
                task = "noise"
            else:
                sub = data_id
                ses = None

            # Create the JSON sidecar
            _sidecar_json(raw, task, manufacturer, json_output_name, datatype, emptyroom_fname=None, overwrite=True)

            # Add some fields to the sidecar
            if ses is not None:
                _update_sidecar(json_output_name, "PatientID", f"{sub}_{ses}")
            else:
                _update_sidecar(json_output_name, "PatientID", sub)
            _update_sidecar(json_output_name, "AcquisitionDateTime", acquisition_date_time)
            _update_sidecar(json_output_name, "AcquisitionDate", acquisition_date)
            _update_sidecar(json_output_name, "AcquisitionTime", acquisition_time)
            _update_sidecar(json_output_name, "Modality", "MEG")
            _update_sidecar(json_output_name, "ConversionSoftware", "MNE-BIDS")
            _update_sidecar(json_output_name, "SeriesDescription", fname)


def modify_uploaded_dataset_list(uploaded_img_list):
    """
    Filters the list of json files generated by preprocess.sh to ensure that
    the json files are derived from dcm2niix, and that they contain
    corresponding NIfTI (and bval/bvec) file(s). Additionally, Philips PAR/REC
    files are excluded, as they cannot easily be handled by ezBIDS. Furthermore,
    checks whether an ezBIDS configuration template file is provided.

    Parameters
    ----------
    uploaded_img_list : list
        list of NIfTI files collected from preprocess.sh

    Returns
    -------
    uploaded_files_list : list
        List of NIfTI, JSON, and bval/bvec files generated from dcm2niix

    exclude_data : boolean
        True if uploaded data doesn't come as a NIfTI/JSON pair, which is flagged for exclusion
        from BIDS conversion.

    config : boolean
        True if an ezBIDS configuration file (*ezBIDS_template.json) was detected in the upload.

    config_file : string
        Path to the ezBIDS configuration file, if config == True. Otherwise, set as empty string.
    """
    uploaded_files_list = []

    uploaded_img_list = natsorted([img for img in uploaded_img_list])

    config = False
    config_file = ""
    exclude_data = False

    config_file_list = natsorted([x for x in os.listdir(DATA_DIR) if x.endswith('ezBIDS_template.json')])
    if len(config_file_list):
        # Ideally only one config file uploaded, but if multiple configurations found, select last one (most recent?)
        config = True
        config_file = config_file_list[-1]

    # Parse img files
    for img_file in uploaded_img_list:
        if img_file.endswith('.nii.gz'):
            ext = '.nii.gz'
        elif img_file.endswith('.v.gz'):
            ext = '.v.gz'
        elif img_file.endswith('.ds'):
            ext = '.ds'
        elif img_file.endswith('.tsv.gz'):
            ext = '.tsv.gz'
        else:
            ext = Path(img_file).suffix

        if (not img_file.endswith(tuple(MEG_extensions)) and not img_file.endswith('blood.json')
                and not img_file.endswith('.tsv.gz')):
            try:
                nib.load(img_file)
            except:
                exclude_data = True
                print(f'{img_file} is not a properly formatted imaging file. Will not be converted by ezBIDS.')
                break

        img_dir = os.path.dirname(img_file)
        grouped_files = [
            img_dir + '/' + x for x in os.listdir(img_dir)
            if os.path.basename(img_file).split(ext)[0] + "." in x
        ]

        # deal with PET issue where ECAT-formatted or blood data could be accidentally grouped with imaging data
        if "blood" not in img_file and any("blood" in x for x in grouped_files):
            grouped_files = [x for x in grouped_files if "blood" not in x]
        elif any(x.endswith(tuple(['.v', '.v.gz'])) for x in grouped_files):
            grouped_files = [x for x in grouped_files if not x.endswith(tuple(['.v', '.v.gz']))]

        # Don't want this section if we're allowing only NIfTI files to be uploaded (group length will only be 1).
        # # If imaging file comes with additional data (JSON, bval/bvec) add them to list for processing
        # if len(grouped_files) > 1:
        #     uploaded_files_list.append(grouped_files)
        uploaded_files_list.append(grouped_files)

    # Flatten uploaded_files_list
    uploaded_files_list = natsorted([file for sublist in uploaded_files_list for file in sublist])

    return uploaded_files_list, exclude_data, config, config_file


def set_IntendedFor_B0FieldIdentifier_B0FieldSource(dataset_list_unique_series, bids_compliant):
    """
    If BIDS-compliant dataset uploaded, check for IntendedFor, B0FieldIdentifier, and/or B0FieldSource
    mappings, and apply if found.

    Parameters
    ----------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.

    bids_compliant : boolean
        True if uploaded data is already BIDS-compliant. If so, check for
        IntendedFor, B0FieldIdentifier, and/or B0FieldSource mappings, and
        apply if found.

    Returns
    -------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.
    """
    if bids_compliant is True:
        for unique_dic in dataset_list_unique_series:
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
                if isinstance(unique_dic["B0FieldIdentifier"], str):
                    unique_dic["B0FieldIdentifier"] = [unique_dic["B0FieldIdentifier"]]
            if "B0FieldSource" in json_data:
                unique_dic["B0FieldSource"] = json_data["B0FieldSource"]
                if isinstance(unique_dic["B0FieldSource"], str):
                    unique_dic["B0FieldSource"] = [unique_dic["B0FieldSource"]]

    return dataset_list_unique_series


def generate_readme(DATA_DIR, bids_compliant):
    """
    Determines the contents of the README file, depending on whether the uploaded data
    is BIDS-compliant or not. If True, extracts the information contained in the uploaded README.
    If False, generates a template README.

    Parameters
    ----------
    DATA_DIR : string
        Root-level directory where uploaded data is stored and assessed.

    bids_compliant : boolean
        True if uploaded data is already BIDS-compliant. If so, extract the information contained
        in the uploaded README file.

    Returns
    -------
    readme : string
        General information regarding the dataset.
    """

    if bids_compliant is True:
        bids_root_dir = pd.read_csv(f"{DATA_DIR}/bids_compliant.log", header=None).iloc[0][0]
        try:
            with open(f"{bids_root_dir}/README") as f:
                lines = f.readlines()
        except:
            lines = []
    else:
        lines = [
            "This data was converted using ezBIDS (https://brainlife.io/ezbids). "
            "Additional information regarding this dataset can be entered in this file."
        ]

    readme = "\n".join(lines)

    return readme


def generate_dataset_description(DATA_DIR, bids_compliant):
    """
    If uploaded data is BIDS-compliant, copies information in uploaded dataset_description.json
    file. Otherwise, creates a template dataset_description.json file with relevant information
    study-level information.

    Parameters
    ----------
    DATA_DIR : string
        Root-level directory where uploaded data is stored and assessed.

    bids_compliant : boolean
        True if uploaded data is already BIDS-compliant. If so, extract the information contained
        in the uploaded dataset_description.json file. Otherwise, create a template
        dataset_description.json file.

    Returns
    -------
    dataset_description_dic : dictionary
        Dataset description information.
    """
    dataset_description_dic = {}
    if bids_compliant is True:
        bids_root_dir = pd.read_csv(f"{DATA_DIR}/bids_compliant.log", header=None).iloc[0][0]
        dataset_description = open(f"{bids_root_dir}/dataset_description.json")
        dataset_description = json.load(dataset_description, strict=False)

        for field in dataset_description:
            if field in dataset_description_dic.keys() and "GeneratedBy" not in field:
                dataset_description_dic[field] = dataset_description[field]

    else:
        for field in dataset_description_yaml["dataset_description"]["fields"]:
            if "GeneratedBy" not in field:
                dataset_description_dic[field] = ""
        dataset_description_dic["SourceDatasets"] = []

    dataset_description_dic["GeneratedBy"] = [
        {
            "Name": "ezBIDS",
            "Version": "1.0.0",
            "Description": "ezBIDS is a web-based tool for converting neuroimaging datasets to BIDS, requiring"
                           " neither coding nor knowledge of the BIDS specification",
            "CodeURL": "https://brainlife.io/ezbids/",
            "Container": {
                "Type": "docker",
                "Tag": "brainlife/ezbids-handler"
            }
        }
    ]

    # Explicit checks for required information
    if dataset_description_dic["Name"] == "":
        dataset_description_dic["Name"] = "Untitled"

    if dataset_description_dic["BIDSVersion"] == "":
        dataset_description_dic["BIDSVersion"] = "1.9.0"

    if dataset_description_dic["DatasetType"] == "":
        dataset_description_dic["DatasetType"] = "raw"

    return dataset_description_dic


def generate_participants_columns(DATA_DIR, bids_compliant):
    """
    If uploaded data is BIDS-compliant, copies information contained in the uploaded
    participants.json file. Otherwise, creates standard column information for this
    file.

    Parameters
    ----------
    DATA_DIR : string
        Root-level directory where uploaded data is stored and assessed.

    bids_compliant : boolean
        True if uploaded data is already BIDS-compliant. If so, extract the information contained
        in the uploaded participants.json file

    Returns
    -------
    participants_column_info : dictionary
        Column information for the participants.json file.
    """
    bids_root_dir = pd.read_csv(f"{DATA_DIR}/bids_compliant.log", header=None).iloc[0][0]

    if bids_compliant is True and os.path.isfile(f"{bids_root_dir}/participants.json"):
        participants_column_info = open(f"{bids_root_dir}/participants.json")
        participants_column_info = json.load(participants_column_info, strict=False)
    else:
        participants_column_info = {
            # "species": {
            #     "Description": "species of the participant(s)",
            # },
            "sex": {
                "Description": "Sex of the participant(s)",
                "Levels": {
                    "M": "male",
                    "F": "female",
                    "O": "other"
                }
            },
            "age": {
                "Description": "Age of the participant(s)",
                "Units": "year",
            }
            # "handedness": {
            #     "Description": "Dominant hand of the participant(s)",
            #     "Levels": {
            #         "Left": "Left",
            #         "Right": "Right",
            #         "Ambidextrous": "Ambidextrous"
            #     }
            # }
        }
    return participants_column_info


def find_cog_atlas_tasks(url):
    """
    Generates a list of all possible task names from the Cognitive Atlas API
    task webpage.

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
    # Remove non-alphanumeric terms and "task", "test" substrings
    tasks = [re.sub("[^A-Za-z0-9]+", "", re.split(" task| test", x["name"])[0]).lower() for x in data]
    # Remove empty task name terms and ones under 2 characters (b/c hard to detect in SeriesDescription)
    tasks = [x for x in tasks if len(x) > 2]
    tasks = sorted(tasks, key=str.casefold)  # sort alphabetically, but ignore case

    return tasks


def correct_pe(pe_direction, ornt, correction):
    """
    Equivalent to fMRIPrep’s get_world_pedir (Esteban et al., 2019) function.
    Takes phase encoding direction and image orientation to correct
    pe_direction if needed. This correction occurs if pe_direction
    is in "xyz" format instead of "ijk".

    Function is based on https://github.com/nipreps/fmriprep/issues/2341 and
    code is derived from Chris Markiewicz and Mathias Goncalves.

    Parameters
    ----------
    pe_direction : string
        Value from PhaseEncodingDirection in acquisition json file generated
        by dcm2niix.

    ornt : string
        Value of "".join(nib.aff2axcodes(nii_img.affine)), where "nii_img" is
        is the acquisition NIFTI file generated by dcm2niix.

    correction: boolean
        Whether or not a correction needs to be made to the PhaseEncodingDirection json metadata. Occurs in 
        certain cases where the metadata has the polarity (-) come before the axis letter (e.g. -j instead of j-).

    Returns
    -------
    proper_pe_direction : string
        pe_direction, in "ijk" format.

    correction: boolean
    """
    # axes = (("R", "L"), ("A", "P"), ("S", "I"))
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

    # Weird issue where the polarity sign (-) comes before the axis letter (e.g. -j instead of j-).
    # Only witnessed in Philips data.
    if len(proper_pe_direction) == 2 and proper_pe_direction[0] == '-':
        proper_pe_direction = proper_pe_direction[1] + proper_pe_direction[0]
        correction = True
    else:
        correction = False

    return proper_pe_direction, correction


def determine_direction(proper_pe_direction, ornt):
    """
    Takes [corrected] pe_direction and image orientation (from correct_pe function)
    to determine "_dir-" entity label, which is required or highly
    recommended for specific acquisitions.

    Based on https://github.com/nipreps/fmriprep/issues/2341, with code
    derived from Chris Markiewicz and Mathias Goncalves.

    Parameters
    ----------
    proper_pe_direction : string
        phase encoding direction in “ijk” format

    ornt : string
        Value of "".join(nib.aff2axcodes(nii_img.affine)), where "nii_img" is
        is the acquisition NIFTI file generated by dcm2niix.

    Returns
    -------
    direction : string
        direction for BIDS "_dir-" entity label.
    """
    axes = (("R", "L"), ("A", "P"), ("S", "I"))
    ax_idcs = {"i": 0, "j": 1, "k": 2}
    axcode = ornt[ax_idcs[proper_pe_direction[0]]]
    inv = proper_pe_direction[1:] == "-"

    if proper_pe_direction[0] == "i":
        if "L" in axcode:
            inv = not inv
    elif proper_pe_direction[0] == "j":
        if "P" in axcode:
            inv = not inv
    elif proper_pe_direction[0] == "k":
        if "I" in axcode:
            inv = not inv

    for ax in axes:
        for flip in (ax, ax[::-1]):
            if flip[not inv].startswith(axcode):
                direction = "".join(flip)

    return direction


def generate_dataset_list(uploaded_files_list, exclude_data):
    """
    Takes list of NIfTI, JSON, (and bval/bvec) files generated from dcm2niix
    to create a list of info directories for each uploaded acquisition, where
    each directory contains metadata and other dicom header information to
    help ezBIDS determine the identify of acquisitions, and to determine other
    BIDS-related information (e.g., entity labels).

    Parameters
    ----------
    uploaded_files_list : list
        List of NIfTI, JSON, and bval/bvec files generated from dcm2niix,
        generated from preprocess.sh

    exclude_data : boolean
        True if uploaded data doesn't come as a NIfTI/JSON pair, which is flagged for exclusion
        from BIDS conversion.

    Returns
    -------
    dataset_list : list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files.
    """
    # Create list for appending dictionaries to
    dataset_list = []

    # Get separate data (e.g. nifti) and json (i.e. sidecar) lists
    img_list = natsorted(
        [
            x for x in uploaded_files_list
            if x.endswith('nii.gz')
            or x.endswith('blood.json')
            or x.endswith('.tsv.gz')
            or x.endswith(tuple(MEG_extensions))
        ]
    )

    corresponding_files_list = natsorted([
        x for x in uploaded_files_list if x.endswith('.json')
        or x.endswith('.bval')
        or x.endswith('.bvec')
        or x.endswith(tuple(MEG_extensions))
        or x.endswith('blood.tsv')  # do we need this last one?
    ])

    print('')
    print("Determining unique acquisitions in dataset")
    print("------------------------------------------")
    sub_info_list_id = "01"
    sub_info_list = []

    for img_file in img_list:
        # Find file extension
        if img_file.endswith('.nii.gz'):
            ext = '.nii.gz'
        elif img_file.endswith('.v.gz'):
            ext = '.v.gz'
        elif img_file.endswith('.ds'):
            ext = '.ds'
        elif img_file.endswith('.tsv.gz'):
            ext = '.tsv.gz'
        else:
            ext = Path(img_file).suffix

        if img_file.endswith('.blood.json'):
            corresponding_json = img_file
        else:
            corresponding_json = [
                x for x in corresponding_files_list if x.endswith('.json') and img_file.split(ext)[0] in x
            ]  # should be length of 1, but may be empty (i.e. no metadata json file)

        if len(corresponding_json):
            json_path = corresponding_json[0]
            json_data = open(corresponding_json[0])
            json_data = json.load(json_data, strict=False)
            if ext == '.tsv.gz':
                from mne_bids.sidecar_updates import _update_sidecar
                _update_sidecar(json_path, "ConversionSoftware", "n/a")
        else:
            json_path = img_file.split(ext)[0] + '.json'
            json_data = {
                'ConversionSoftware': 'ezBIDS',
                'ConversionSoftwareVersion': '1.0.0'
            }

        # Find ImageModality
        if "Modality" in json_data:
            modality = json_data["Modality"]
        else:
            # assume MR (Is this a proper assumption to make? Probably most likely scenario)
            modality = "MR"

        # Phase encoding direction info
        if "PhaseEncodingDirection" in json_data:
            pe_direction = json_data["PhaseEncodingDirection"]
        else:
            pe_direction = None

        try:
            ornt = nib.aff2axcodes(nib.load(img_file).affine)
            ornt = "".join(ornt)
        except:
            ornt = None

        if pe_direction is not None and ornt is not None and json_data["Modality"] != "MEG":
            correction = False
            proper_pe_direction, correction = correct_pe(pe_direction, ornt, correction)
            if correction is True:
                json_data['PhaseEncodingDirection'] = proper_pe_direction
                with open(json_path, "w") as fp:
                    json.dump(json_data, fp, indent=3)
            ped = determine_direction(proper_pe_direction, ornt)
        else:
            ped = ""

        # Find image file size
        filesize = os.stat(img_file).st_size

        # Find StudyID from json
        if "StudyID" in json_data:
            study_id = json_data["StudyID"]
        else:
            study_id = img_file.split('/')[1]  # uppermost folder in file path

        # Find subject_id from json, since some files contain neither PatientID nor PatientName
        if "PatientID" in json_data:
            patient_id = json_data["PatientID"]
        else:
            patient_id = "n/a"

        if "PatientName" in json_data:
            patient_name = json_data["PatientName"]
        else:
            patient_name = "n/a"

        # Find PatientBirthDate
        if "PatientBirthDate" in json_data:
            patient_birth_date = json_data["PatientBirthDate"].replace("-", "")
        else:
            patient_birth_date = "00000000"

        # Assume patient_species is homo sapiens
        patient_species = "homo sapiens"

        # Find PatientSex
        patient_sex = "n/a"
        if "PatientSex" in json_data:
            patient_sex = json_data["PatientSex"]

        # Find PatientAge
        if "PatientAge" in json_data:
            patient_age = json_data["PatientAge"]
        else:
            patient_age = "n/a"

        # Patient handedness
        patient_handedness = "n/a"

        """
        Metadata may contain PatientBirthDate and/or PatientAge. Check either
        to see if one truly provides accurate age information.
        """
        age = "n/a"
        if "PatientAge" in json_data:
            patient_age = json_data["PatientAge"]
            if (isinstance(patient_age, int) or isinstance(patient_age, float)):
                age = patient_age

        if age == "n/a" and "PatientBirthDate" in json_data:
            patient_birth_date = json_data["PatientBirthDate"]  # ISO 8601 "YYYY-MM-DD"
            try:
                age = int(today_date.split("-")[0]) - int(patient_birth_date.split("-")[0])
                - ((int(today_date.split("-")[1]), int(today_date.split("-")[2]))
                    < (int(patient_birth_date.split("-")[2]), int(patient_birth_date.split("-")[2])))
            except:
                pass

        # Find AcquisitionDateTime
        if "AcquisitionDateTime" in json_data:
            acquisition_date_time = json_data["AcquisitionDateTime"]
        else:
            acquisition_date_time = "0000-00-00T00:00:00.000000"

        # Find AcquisitionDate
        if "AcquisitionDate" in json_data:
            acquisition_date = json_data["AcquisitionDate"]
        else:
            acquisition_date = "0000-00-00"

        # Find AcquisitionTime
        if "AcquisitionTime" in json_data:
            acquisition_time = json_data["AcquisitionTime"]
        else:
            acquisition_time = acquisition_time = "00:00:00.000000"

        # Find TimeZero
        if "TimeZero" in json_data and json_data.get("ScanStart", None) == 0:
            acquisition_time = json_data["TimeZero"]

        # Find Manufacturer metadata or make placehodler
        if "Manufacturer" not in json_data:
            manufacturer = "n/a"
            json_data["Manufacturer"] = manufacturer
        else:
            manufacturer = json_data["Manufacturer"]

        # Find RepetitionTime
        if "RepetitionTime" in json_data:
            repetition_time = json_data["RepetitionTime"]
        else:
            repetition_time = 0

        # Find EchoNumber
        if "EchoNumber" in json_data:
            echo_number = json_data["EchoNumber"]
        else:
            echo_number = None

        # Find EchoTime
        if "EchoTime" in json_data:
            echo_time = json_data["EchoTime"] * 1000
        else:
            echo_time = 0

        # Get the nibabel nifti image info
        if img_file.endswith('.nii.gz'):
            image = nib.load(img_file)
            ndim = image.ndim

            # If RepetitionTime (TR) not in JSON metadata, add to file
            if repetition_time == 0:
                if len(image.header.get_zooms()) == 4:
                    repetition_time = image.header.get_zooms()[-1]
                    if not isinstance(repetition_time, int):
                        repetition_time = round(float(repetition_time), 2)
                    json_data['RepetitionTime'] = repetition_time

            # Find how many volumes are in nifti file
            try:
                volume_count = image.shape[3]
            except:
                volume_count = 1
        elif img_file.endswith(tuple(MEG_extensions)):
            image = "n/a"
            volume_count = 1
            ndim = 4
        elif img_file.endswith("blood.json"):
            image = "n/a"
            volume_count = 1
            ndim = 2
        else:  # add as we support new imaging modalities
            image = 'n/a'
            volume_count = 1
            ndim = 2

        # Find SeriesNumber
        if "SeriesNumber" in json_data:
            series_number = json_data["SeriesNumber"]
        else:
            series_number = 0

        # Modified SeriesNumber, which zero pads integers < 10. Helpful for sorting purposes
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

        # If SeriesDescription and ProtocolName are both n/a, give SD something
        if series_description == "n/a" and protocol_name == "n/a":
            series_description = img_file
            descriptor = "SeriesDescription"

        # Find ImageType
        if "ImageType" in json_data:
            image_type = json_data["ImageType"]
        else:
            image_type = []

        # Exclude data or not
        if exclude_data is True:
            data_type = "exclude"
        else:
            data_type = ""

        """
        Select subject (and session, if applicable) IDs to display.
        """
        if patient_id == "n/a" and patient_name == "n/a" and patient_birth_date == "00000000":
            # Completely anonymized data, assume folder is the subject ID
            folder = [x for x in img_file.split("/") if not x.endswith(ext)][-1]
        else:
            folder = "n/a"

        sub_info = {
            "PatientID": patient_id,
            "PatientName": patient_name,
            "PatientBirthDate": patient_birth_date,
            "Folder": folder,
            "Subject": sub_info_list_id,
        }
        sub_info_list.append(sub_info)

        if len(sub_info_list) == 1:
            pass
        else:
            if sub_info != sub_info_list[len(sub_info_list) - 2]:
                sub_info_list_id = int(sub_info_list_id) + 1
                if sub_info_list_id > 9:
                    sub_info_list_id = str(sub_info_list_id)
                else:
                    sub_info_list_id = "0" + str(sub_info_list_id)
                sub_info_list[-1]["Subject"] = sub_info_list_id

        subject = sub_info["Subject"]

        # Check if subject (and session) ID(s) explicitly specified
        sub_search_term = "sub-"
        ses_search_term = "ses-"

        for value in [img_file, patient_id, patient_name]:
            if sub_search_term in value.lower():
                subject = re.split('[^a-zA-Z0-9]', value.lower().split(f"{sub_search_term}")[-1])[0]
                break

        session = ""
        for value in [img_file, patient_id, patient_name]:
            if ses_search_term in value.lower():
                session = re.split('[^a-zA-Z0-9]', value.lower().split(f"{ses_search_term}")[-1])[0]
                break

        # Remove non-alphanumeric characters from subject (and session) ID(s)
        subject = re.sub("[^A-Za-z0-9]+", "", subject)
        session = re.sub("[^A-Za-z0-9]+", "", session)

        # If uploaded data didn't contain JSON metadata, add here
        if not os.path.exists(json_path):
            with open(json_path, "w") as fp:
                json.dump(json_data, fp, indent=3)
            json_data = open(json_path)
            json_data = json.load(json_data, strict=False)
            corresponding_files_list = corresponding_files_list + [json_path]

        # Files (JSON, bval/bvec, tsv) associated with imaging file
        corresponding_file_paths = [
            x for x in corresponding_files_list if f"{img_file.split(ext)[0]}." in x and not x.endswith(ext)
        ]

        # Relative paths of NIfTI and JSON files (per SeriesNumber)
        paths = natsorted(corresponding_file_paths + [img_file])

        """
        Organize all from individual SeriesNumber in dictionary
        """
        sequence_info_directory = {
            "StudyID": study_id,
            "PatientID": patient_id,
            "PatientName": patient_name,
            "PatientBirthDate": patient_birth_date,
            "PatientSpecies": patient_species,
            "PatientSex": patient_sex,
            "PatientAge": age,
            "PatientHandedness": patient_handedness,
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
            "Modality": modality,
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
            "error": None,
            "IntendedFor": None,
            "B0FieldIdentifier": None,
            "B0FieldSource": None,
            "section_id": 1,
            "message": None,
            "type": data_type,
            "nifti_path": img_file,
            "nibabel_image": image,
            "ndim": ndim,
            "json_path": json_path,
            "file_directory": "/".join([x for x in img_file.split("/") if not x.endswith(ext)]),
            'uploaded_config_file': config,
            "paths": paths,
            "headers": "",
            "finalized_match": False,
            "sidecar": json_data
        }
        dataset_list.append(sequence_info_directory)

    # Sort dataset_list of dictionaries
    dataset_list = sorted(dataset_list, key=itemgetter("AcquisitionDate",
                                                       "subject",
                                                       "session",
                                                       "AcquisitionTime",
                                                       "ModifiedSeriesNumber",
                                                       "json_path"))

    return dataset_list


def organize_dataset(dataset_list):
    """
    Organize data files into pseudo subject (and session, if applicable) groups.
    This is particularly necessary when anaonymized data is provided, since crucial
    metadata including AcquisitionDateTime, PatientID, PatientName, etc are removed.
    Typically, these fields assist ezBIDS in determining subject (and session) mapping,
    so will try to use other metadata (AcquisitionTime, SeriesNumber, etc) to perform
    this important mapping. This is very brittle, so users should be informed before
    uploading to either explicitly state subject and session mappings (e.g., sub-001)
    in the file name or path, or not upload anonymized data.

    Parameters
    ----------
    dataset_list : list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files.

    Returns
    -------
    dataset_list : list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files.
    """
    dataset_list = sorted(dataset_list, key=itemgetter(
        "subject",
        "AcquisitionTime",
        "ModifiedSeriesNumber")
    )

    pseudo_sub = 1
    for index, unique_dic in enumerate(dataset_list):
        if unique_dic["subject"] == "n/a":
            if (unique_dic["AcquisitionDateTime"] == "0000-00-00T00:00:00.000000"
                    and unique_dic["PatientID"] == "n/a"
                    and unique_dic["PatientName"] == "n/a"):
                # Likely working with anonymized data, so not obvious what subject/session mapping should be
                if index == 0:
                    subj = pseudo_sub
                else:
                    previous_data = dataset_list[index - 1]
                    if unique_dic["SeriesNumber"] >= previous_data["SeriesNumber"]:
                        if not unique_dic["SeriesNumber"] - previous_data["SeriesNumber"] < 2:
                            # Probably a misalignment, adjust pseudo subject ID
                            subj = pseudo_sub - 1
                        else:
                            subj = pseudo_sub
                    else:
                        if int(unique_dic["SeriesNumber"]) == 1:
                            # Likely moving onto data from new subject or session, but going to assuming subject
                            pseudo_sub += 1
                        subj = pseudo_sub

                unique_dic["subject"] = (unique_dic["subject"] + ("0" * (4 - len(str(subj)))) + str(subj))
                unique_dic["AcquisitionDateTime"] = unique_dic["subject"][:-4]

        dataset_list = sorted(dataset_list, key=itemgetter(
            "subject",
            "AcquisitionTime",
            "ModifiedSeriesNumber")
        )

    return dataset_list


def determine_sub_ses_IDs(dataset_list, bids_compliant):
    """
    Determine subject ID(s), and session ID(s) (if applicable) of uploaded data.

    Parameters
    ----------
    dataset_list : list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files.

    bids_compliant : boolean
        True if uploaded data is already BIDS-compliant. If so, parses the participants.tsv
        file for subject ID information.

    Returns
    -------
    dataset_list : list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files.

    subjects_information : list
        List of dictionaries containing subject identification info, such as
        PatientID, PatientName, PatientBirthDate, and corresponding session
        information.

    participants_info : dictionary
        Information pertaining to phenotype and metadata of subjects.
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

        # Organize phenotype (e.g., species, sex, age, handedness) information
        bids_root_dir = pd.read_csv(f"{DATA_DIR}/bids_compliant.log", header=None).iloc[0][0]
        if bids_compliant is True and os.path.isfile(f"{bids_root_dir}/participants.tsv"):
            participants_info_data = pd.read_csv(f"{bids_root_dir}/participants.tsv", sep="\t")

            participants_info = {}
            participants_info_columns = ([x for x in participants_info_data.columns if x != "participant_id"]
                                         + ["PatientID", "PatientName"])

            for len_index in range(len(participants_info_data)):
                participants_info[str(len_index)] = dict.fromkeys(participants_info_columns)

                for col in participants_info_columns:
                    if col not in ["PatientID", "PatientName"]:
                        participants_info[str(len_index)][col] = str(participants_info_data[col].iloc[len_index])
                    else:
                        if "sub-" in participants_info_data["participant_id"].iloc[len_index]:
                            participant_id = participants_info_data["participant_id"].iloc[len_index].split("-")[-1]
                        else:
                            participant_id = participants_info_data["participant_id"].iloc[len_index]

                        participants_info[str(len_index)]["PatientID"] = str(participant_id)
                        participants_info[str(len_index)]["PatientName"] = str(participant_id)
        else:
            phenotype_info = list(
                {
                    "species": x["PatientSpecies"],
                    "sex": x["PatientSex"],
                    "age": x["PatientAge"],
                    "handedness": x["PatientHandedness"],
                    "PatientName": x["PatientID"],
                    "PatientID": x["PatientName"],
                    "FileDirectory": x["file_directory"]
                } for x in sub_dics_list)[0]

            participants_info.update({str(x["subject_idx"]): phenotype_info})

        # Determine all unique sessions (if applicable) per subject
        unique_ses_date_times = []
        session_idx_counter = 0
        ses_dates = list(set([(x["session"], x["AcquisitionDate"]) for x in sub_dics_list]))

        # Session information includes the following metadata: session, AcquisitionDate, and AcquisitionTime
        for ses_date in ses_dates:
            ses_date = list(ses_date)
            date_time = [
                x["AcquisitionTime"] for x in sub_dics_list if x["session"] == ses_date[0]
                and x["AcquisitionDate"] == ses_date[1]][0]
            ses_date.append(date_time)
            dic = {
                "session": ses_date[0],
                "AcquisitionDate": ses_date[1],
                "AcquisitionTime": ses_date[2],
                "exclude": False,
                "session_idx": 0
            }
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

        # Pair patient information (PatientID, PatientName, PatientBirthDate) with corresponding session information
        patient_info = []
        for ses_info in unique_ses_date_times:
            patient_dic = {
                "PatientID": [
                    x["PatientID"] for x in sub_dics_list if x["session"] == ses_info["session"]
                    and x["AcquisitionDate"] == ses_info["AcquisitionDate"]][0],
                "PatientName": [
                    x["PatientName"] for x in sub_dics_list if x["session"] == ses_info["session"]
                    and x["AcquisitionDate"] == ses_info["AcquisitionDate"]][0],
                "PatientBirthDate": [
                    x["PatientBirthDate"] for x in sub_dics_list if x["session"] == ses_info["session"]
                    and x["AcquisitionDate"] == ses_info["AcquisitionDate"]][0],
                "file_directory": [
                    x["file_directory"] for x in sub_dics_list if x["session"] == ses_info["session"]
                    and x["AcquisitionDate"] == ses_info["AcquisitionDate"]][0]
            }
            patient_info.append(patient_dic)

        """
        See if multiple sessions occurred on same day, meaning same AcquisitionDate
        If so, modify the AcquisitionDate value(s) so that each are unique, since
        ezBIDS only cares about AcquisitionDate. Modification entails appending
        a '.<value>' to the end of the AcquisitionDate value (e.g. '2021-01-01.1').
        AcquisitionDate cannot be used with anonymized data because that metadata
        is removed.
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
            "phenotype": list(
                {
                    "species": x["PatientSpecies"],
                    "sex": x["PatientSex"],
                    "age": x["PatientAge"],
                    "handedness": x["PatientHandedness"]
                } for x in sub_dics_list)[0],
            "exclude": False,
            "sessions": [
                {k: v for k, v in d.items()
                    if k != "session_idx"
                    and k != "AcquisitionTime"} for d in unique_ses_date_times],
            "validationErrors": []
        }

        subjects_information.append(subject_ids_info)

    return dataset_list, subjects_information, participants_info


def determine_unique_series(dataset_list, bids_compliant):
    """
    From the dataset_list, group the individual acquisitions into unique series.
    Unique data is determined from 4 DICOM header values: SeriesDescription
    EchoTime, ImageType, and RepetitionTime. If EchoTime values differ
    slightly (+/- 1 ms) and other values are the same, a unique series ID is not
    given, since EchoTime is a continuous variable.

    Parameters
    ----------
    dataset_list : list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files.

    Returns
    -------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.
    """
    dataset_list_unique_series = []
    series_checker = []
    series_idx = 0

    for index, acquisition_dic in enumerate(dataset_list):
        """
        Assign series index value (series_idx) to each unique sequence based on
        EchoTime, SeriesDescription/ProtocolName, ImageType, and RepetitionTime metadata.
        Since EchoTime and RepetitionTime are float values, add slight measurement error
        tolerance for these metadata. See https://github.com/rordenlab/dcm2niix/issues/543

        If retro-reconstruction (RR) acquisitions are found
        ("_RR" in SeriesDescription), they should be of same unique
        series as non retro-reconstruction ones. These are generally rare
        cases, but should be accounted for.
        """
        descriptor = acquisition_dic["descriptor"]
        if "_RR" in acquisition_dic["SeriesDescription"]:
            heuristic_items = [
                round(acquisition_dic["EchoTime"], 1),
                acquisition_dic[descriptor].replace("_RR", ""),
                acquisition_dic["ImageType"],
                round(acquisition_dic["RepetitionTime"], 1)
            ]
        else:
            heuristic_items = [
                round(acquisition_dic["EchoTime"], 1),
                acquisition_dic[descriptor],
                acquisition_dic["ImageType"],
                round(acquisition_dic["RepetitionTime"], 1)
            ]

        if bids_compliant is True:  # Each uploaded BIDS NIfTI/JSON pair is a unique series
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
            else:
                if heuristic_items[1:3] not in [x[1:3] for x in series_checker]:
                    series_idx += 1
                    acquisition_dic["series_idx"] = series_idx
                    dataset_list_unique_series.append(acquisition_dic)
                else:
                    if heuristic_items not in [x[:-1] for x in series_checker]:
                        series_idx += 1
                        acquisition_dic["series_idx"] = series_idx
                        dataset_list_unique_series.append(acquisition_dic)
                    else:
                        common_series_index = [x[:-1] for x in series_checker].index(heuristic_items)
                        common_series_idx = series_checker[common_series_index][-1]
                        acquisition_dic["series_idx"] = common_series_idx

            series_checker.append(heuristic_items + [acquisition_dic["series_idx"]])

    return dataset_list, dataset_list_unique_series


def template_configuration(dataset_list_unique_series, subjects_information, config_file):
    """
    Parameters
    ----------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.

    subjects_information : list
        List of dictionaries containing subject identification info, such as
        PatientID, PatientName, PatientBirthDate, and corresponding session
        information.

    config_file : string
        Path to the ezBIDS configuration file, if config is True. Otherwise, set as empty string.

    Returns
    -------
    readme : string
        General information regarding the dataset.

    dataset_description_dic : dictionary
        Dataset description information.

    participants_column_info : dictionary
        Column information for the participants.json file.

    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.

    subjects_information : list
        List of dictionaries containing subject identification info, such as
        PatientID, PatientName, PatientBirthDate, and corresponding session
        information.

    events : dictionary
        Information pertaining to the events timing files for func/bold data.
    """

    config_data = open(config_file)
    config_data = json.load(config_data, strict=False)

    readme = config_data["readme"]
    dataset_description_dic = config_data["datasetDescription"]
    participants_column_info = config_data["participantsColumn"]
    subjects_sessions_info = config_data["subjects"]
    config_dataset_list_unique_series = config_data["series"]
    config_dataset_list_objects = config_data["objects"]

    # Try to determine subject (and session) mapping from what's in the configuration
    match_start_index = None
    match_end_index = None
    subject_counter = 1

    ref_subject_info = subjects_sessions_info[-1]  # Get most recent information
    ref_session_info = ref_subject_info["sessions"]
    ref_subject_id = ref_subject_info["subject"]
    ref_patient_info = ref_subject_info["PatientInfo"][-1]  # Get most recent information

    anonymized_sidecar_fields = [
        "SeriesInstanceUID",
        "StudyInstanceUID",
        "ReferringPhysicianName",
        "StudyID",
        "PatientID",
        "PatientName",
        "AccessionNumber",
        "PatientBirthDate",
        "PatientSex",
        "PatientWeight",
        "AcquisitionDateTime"
    ]

    for sub_info in subjects_information:
        sub = sub_info["subject"]
        for key in ref_patient_info.keys():
            if ref_subject_id in ref_patient_info[key]:
                match_start_index, match_end_index = [
                    (x.start(), x.end()) for x in re.finditer(ref_subject_id, ref_patient_info[key])
                ][0]
                sub = ref_patient_info[key][match_start_index:match_end_index]
                sub_info["subject"] = sub
                break
        if ref_subject_id.isnumeric():
            nonzero_num = ref_subject_id.lstrip("0")
            num_leading_zeros = len(ref_subject_id) - len(nonzero_num)
            if ref_subject_id.endswith("9"):
                sub = "0" * (num_leading_zeros - 1) + str(int(nonzero_num) + subject_counter)
            else:
                sub = "0" * num_leading_zeros + str(int(nonzero_num) + subject_counter)
            sub_info["subject"] = sub
            subject_counter += 1
        else:
            # Maybe subject ID contains mix of letters and numbers
            letters = "".join([x for x in ref_subject_id if x.isalpha()])  # Assuming letters at start of sub ID string
            numeric_ID = "".join([x for x in ref_subject_id if x.isnumeric()])
            nonzero_num = numeric_ID.lstrip("0")
            num_leading_zeros = len(numeric_ID) - len(nonzero_num)
            if numeric_ID.endswith("9"):
                sub = letters + "0" * (num_leading_zeros - 1) + str(int(nonzero_num) + subject_counter)
            else:
                sub = letters + "0" * num_leading_zeros + str(int(nonzero_num) + subject_counter)
            sub_info["subject"] = sub
            subject_counter += 1

        for idx, ref_session in enumerate(ref_session_info):
            sub_info["sessions"][idx]["session"] = ref_session["session"]

    """
    Find datatype, suffix, and entity labels in uploaded data based on correspondence with data referenced
    in configuration.
    """
    for unique_dic in dataset_list_unique_series:
        sd = unique_dic["SeriesDescription"]
        et = unique_dic["EchoTime"]
        rt = unique_dic["RepetitionTime"]
        it = unique_dic["ImageType"]
        sidecar = unique_dic["sidecar"]

        """
        Don't use series_idx as identifier because the uploaded data might not contain the same data as
        what is referenced in the configuration (e.g., new data is uploaded that wasn't present in configuration)
        """
        config_series_ref_list = [
            x for x in config_dataset_list_unique_series if x["SeriesDescription"] == sd
            and x["ImageType"] == it
            and round(x["EchoTime"], 1) == round(et, 1)
            and round(x["RepetitionTime"], 1) == round(rt, 1)
        ]

        if len(config_series_ref_list):  # Should only be length of 1, but being extra cautious
            config_series_ref = config_series_ref_list[0]
            ref_type = config_series_ref["type"]
            ref_entities = config_series_ref["entities"]
            ref_IntendedFor = config_series_ref["IntendedFor"]
            ref_B0FieldIdentifier = config_series_ref["B0FieldIdentifier"]
            ref_B0FieldSource = config_series_ref["B0FieldSource"]
            ref_message = config_series_ref["message"]
            ref_series_idx = config_series_ref["series_idx"]

            unique_dic["type"] = ref_type
            unique_dic["entities"] = ref_entities
            unique_dic["IntendedFor"] = ref_IntendedFor
            unique_dic["B0FieldIdentifier"] = ref_B0FieldIdentifier
            unique_dic["B0FieldSource"] = ref_B0FieldSource
            unique_dic["finalized_match"] = True
            if "localizer" in ref_message:
                unique_dic["message"] = "Datatype, suffix, and entity information was determined based on match "\
                    "with corresponding data in ezBIDS configuration (ezBIDS_template.json) file. This data is "\
                    "believe to be a localizer. Please modify if incorrect"
            else:
                unique_dic["message"] = "Datatype, suffix, and entity information was determined based on match "\
                    "with corresponding data in ezBIDS configuration file. Please modify if incorrect"

            """
            If metadata information was added in, find it and add to the json file.
            """
            ref_object = [
                x for x in config_dataset_list_objects
                if "series_idx" in x.keys()
                and x["series_idx"] == ref_series_idx
            ]
            if len(ref_object):  # If len > 1, just take the 1st instance
                ref_sidecar = [x["sidecar"] for x in ref_object[0]["items"] if x["name"] == "json"][0]
                for field in ref_sidecar:
                    value = ref_sidecar[field]
                    if field not in sidecar and field not in anonymized_sidecar_fields:
                        sidecar[field] = value

                unique_dic["sidecar"] = sidecar

    """
    If events.tsv files (for func/bold) are referenced in the configuration, grab this information and display
    it on the Events page if user uploads event timing data again.
    """
    events = config_data["events"]
    events["loaded"] = False
    events["sampleValues"] = {}

    return (readme, dataset_description_dic, participants_column_info,
            dataset_list_unique_series, subjects_information, events)


def create_lookup_info():
    """
    Creates a lookup dictionary of conditionals for identifying different
    datatypes and suffixes, as well as some entity label information.

    Parameters
    ----------
    None

    Returns
    -------
    lookup_dic : dictionary
        A lookup dictionary of conditionals for identifying different
        datatypes and suffixes, as well as some entity label information.
    """
    lookup_dic = {}

    # Add localizers to lookup_dic
    lookup_dic["localizer"] = {
        "exclude": {
            "search_terms": ["localizer", "scout"],
            "accepted_entities": [],
            "required_entities": [],
            "conditions": ['"_i0000" in unique_dic["paths"][0]']
        }
    }

    for datatype in datatypes_yaml.keys():
        if datatype in accepted_datatypes:
            lookup_dic[datatype] = {}
            rule = yaml.load(open(os.path.join(analyzer_dir, datatype_suffix_rules, datatype) + ".yaml"),
                             Loader=yaml.FullLoader)

            for key in rule.keys():
                suffixes = rule[key]["suffixes"]
                if datatype == "anat":
                    # Remove deprecated suffixes
                    suffixes = [x for x in suffixes if x not in ["T2star", "FLASH", "PD"]]
                elif datatype == "dwi":
                    # suffixes = ["dwi", "sbref"]
                    suffixes = [x for x in suffixes if x in ["dwi", "sbref"]]
                elif datatype == "fmap":
                    # Remove m0scan suffix since it could go in either the perf or fmap directory
                    suffixes = [x for x in suffixes if x not in ["m0scan"]]
                elif datatype == "func":
                    # Remove non-imaging suffixes
                    suffixes = [x for x in suffixes if x not in ["events", "stim", "phase"]]
                elif datatype == "perf":
                    # Remove non-imaging suffixes
                    suffixes = [x for x in suffixes if x not in ["aslcontext", "asllabeling", "stim"]]
                elif datatype == "pet":
                    # Only keep imaging suffixes
                    suffixes = [x for x in suffixes if x in ["pet", "blood"]]
                elif datatype == "meg":
                    # MEG files are weird, can have calibration and crosstalk files with the same datatype/suffix pair
                    suffixes = [x for x in suffixes if x == "meg" and key == "meg"]
                elif datatype == "beh":
                    suffixes = [x for x in suffixes if x not in ["stim"]]

                for suffix in suffixes:

                    lookup_dic[datatype][suffix] = {
                        "search_terms": [suffix.lower()],
                        "accepted_entities": [],
                        "required_entities": [],
                        "conditions": []
                    }

                    if suffix in rule[key]["suffixes"]:

                        entities = rule[key]["entities"]

                        accepted_entities = [
                            x for x in entities.keys()
                            if x not in ["subject", "session"]
                        ]
                        lookup_dic[datatype][suffix]["accepted_entities"] = accepted_entities

                        required_entities = [
                            x for x in entities.keys()
                            if x not in ["subject", "session"]
                            and entities[x] == "required"
                        ]
                        lookup_dic[datatype][suffix]["required_entities"] = required_entities

                        if datatype == "anat":
                            lookup_dic[datatype][suffix]["conditions"].extend(
                                [
                                    'unique_dic["ndim"] == 3',

                                ]
                            )
                            if suffix == "T1w":
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "tfl3d",
                                        "tfl_3d",
                                        "mprage",
                                        "mp_rage",
                                        "spgr",
                                        "tflmgh",
                                        "tfl_mgh",
                                        "t1mpr",
                                        "t1_mpr",
                                        "anatt1",
                                        "anat_t1",
                                        "3dt1",
                                        "3d_t1"
                                    ]
                                )
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        '"inv1" not in sd and "inv2" not in sd and "uni_images" not in sd'
                                    ]
                                )
                            elif suffix == "T2w":
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "anatt2",
                                        "anat_t2",
                                        "3dt2",
                                        "3d_t2",
                                        "t2spc",
                                        "t2_spc"
                                    ]
                                )
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        'unique_dic["EchoTime"] > 100'
                                    ]
                                )
                            elif suffix == "FLAIR":
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "t2spacedafl",
                                        "t2_space_da_fl",
                                        "t2space_da_fl",
                                        "t2space_dafl",
                                        "t2_space_dafl"
                                    ]
                                )
                            elif suffix == "T2starw":
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "qsm"
                                    ]
                                )
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        '"EchoNumber" not in unique_dic["sidecar"]'
                                    ]
                                )
                            elif suffix == "MEGRE":
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "qsm"
                                    ]
                                )
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        '"EchoNumber" in unique_dic["sidecar"]'
                                    ]
                                )
                            elif suffix == "MESE":
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        '"EchoNumber" in unique_dic["sidecar"]'
                                    ]
                                )
                            elif suffix in ["MP2RAGE", "IRT1"]:
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        '"InversionTime" in unique_dic["sidecar"]'
                                    ]
                                )
                            elif suffix == "UNIT1":
                                lookup_dic[datatype][suffix]["search_terms"] = [
                                    "uni"
                                ]  # Often appear as "UNI" in sd
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        '"UNI" in unique_dic["ImageType"]',
                                        '"InversionTime" not in unique_dic["sidecar"]'
                                    ]
                                )
                            elif suffix in ["MPM", "MTS"]:
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        '"FlipAngle" in unique_dic["sidecar"]'
                                    ]
                                )
                            elif suffix == "PDT2":
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "fse",
                                        "pd_t2"
                                    ]
                                )
                        elif datatype == "func":
                            if suffix in ["bold", "sbref"]:
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "func",
                                        "bold",
                                        "fmri",
                                        "fcmri",
                                        "fcfmri",
                                        "rsfmri",
                                        "rsmri",
                                        "task",
                                        "rest"
                                    ]
                                )
                                if suffix == "bold":
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            'unique_dic["ndim"] == 4',
                                            'unique_dic["NumVolumes"] > 1',
                                            'unique_dic["RepetitionTime"] > 0',
                                            'not any(x in unique_dic["ImageType"] '
                                            'for x in ["DERIVED", "PERFUSION", "DIFFUSION", "ASL", "UNI"])'
                                        ]
                                    )
                                elif suffix == "sbref":
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            '"DIFFUSION" not in unique_dic["ImageType"]',
                                            '"sbref" in sd and unique_dic["NumVolumes"] == 1',
                                            'unique_dic["ndim"] == 3',
                                            'not any(x in unique_dic["ImageType"] '
                                            'for x in ["DERIVED", "PERFUSION", "DIFFUSION", "ASL", "UNI"])'
                                        ]
                                    )
                        elif datatype == "dwi":
                            if suffix in ["dwi", "sbref"]:
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "dwi",
                                        "dti",
                                        "dmri"
                                    ]
                                )
                                if suffix == "dwi":
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            'any(".bvec" in x for x in unique_dic["paths"])',
                                            # '"DIFFUSION" in unique_dic["ImageType"]',
                                            'unique_dic["NumVolumes"] > 1',
                                            'not any(x in sd for x in ["trace", "_fa_", "adc"])'
                                        ]
                                    )
                                elif suffix == "sbref":
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            'any(".bvec" in x for x in unique_dic["paths"])',
                                            # '"DIFFUSION" in unique_dic["ImageType"]',
                                            'not any(x in sd for x in ["trace", "_fa_", "adc"])',
                                            'unique_dic["ndim"] == 3',
                                            '("b0" in sd or "bzero" in sd or "sbref" in sd) '
                                            'and unique_dic["NumVolumes"] == 1'
                                        ]
                                    )
                        elif datatype == "fmap":
                            if suffix in ["epi", "magnitude1", "magnitude2", "phasediff",
                                          "phase1", "phase2", "magnitude", "fieldmap"]:
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "fmap",
                                        "fieldmap",
                                        "field_map",
                                        "grefieldmap",
                                        "gre_field_map",
                                        "distortionmap",
                                        "distortion_map"
                                    ]
                                )
                                if suffix == "epi":
                                    lookup_dic[datatype][suffix]["search_terms"].extend(
                                        [
                                            "fmap_spin",
                                            "fmap_se",
                                            "fmap_ap",
                                            "fmap_pa",
                                            "fieldmap_spin",
                                            "fieldmap_ap",
                                            "fieldmap_pa",
                                            "fieldmap_se",
                                            "spinecho",
                                            "spin_echo",
                                            "sefmri",
                                            "semri",
                                            "pepolar",
                                            "topup"
                                        ]
                                    )
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            'unique_dic["NumVolumes"] <= 10',
                                            '"EchoNumber" not in unique_dic["sidecar"]',
                                            'unique_dic["sidecar"]["Manufacturer"] != "GE"'
                                        ]
                                    )
                                elif suffix == "magnitude1":
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            '"EchoNumber" in unique_dic["sidecar"]',
                                            'unique_dic["EchoNumber"] == 1',
                                            '"_e1_ph" not in unique_dic["json_path"]'
                                        ]
                                    )
                                elif suffix == "magnitude2":
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            '"EchoNumber" in unique_dic["sidecar"]',
                                            'unique_dic["EchoNumber"] == 2',
                                            '"_e2_ph" not in unique_dic["json_path"]'
                                        ]
                                    )
                                elif suffix == "phasediff":
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            '"EchoNumber" in unique_dic["sidecar"]',
                                            'unique_dic["EchoNumber"] == 2',
                                            '"_e2_ph" in unique_dic["json_path"]',
                                            'len(dataset_list_unique_series) > 2 and "_e1_ph" not in '
                                            'dataset_list_unique_series[index - 2]["json_path"]'
                                        ]
                                    )
                                elif suffix == "phase1":
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            '"EchoNumber" in unique_dic["sidecar"]',
                                            'unique_dic["EchoNumber"] == 1',
                                            '"_e1_ph" in unique_dic["json_path"]'
                                        ]
                                    )
                                elif suffix == "phase2":
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            '"EchoNumber" in unique_dic["sidecar"]',
                                            'unique_dic["EchoNumber"] == 2',
                                            '"_e2_ph" in unique_dic["json_path"]',
                                            'len(dataset_list_unique_series) > 2 and "_e1_ph" in '
                                            'dataset_list_unique_series[index - 2]["json_path"]'
                                        ]
                                    )
                                elif suffix in ["magnitude", "fieldmap"]:  # specific to GE scanners
                                    lookup_dic[datatype][suffix]["conditions"].extend(
                                        [
                                            'unique_dic["sidecar"]["Manufacturer"] == "GE"'
                                        ]
                                    )
                            elif suffix == "TB1TFL":
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "tflb1map",
                                        "tfl_b1map",
                                        "tfl_b1_map"
                                    ]
                                )
                            elif suffix == "TB1RFM":
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "rfmap"
                                    ]
                                )
                        elif datatype == "pet":
                            if suffix == "pet":
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        '"pypet2bids" in unique_dic["sidecar"]["ConversionSoftware"] '
                                        'or unique_dic["Modality"] == "PT"'
                                    ]
                                )
                            elif suffix == "blood":
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        'unique_dic["json_path"].endswith("_blood.json")'
                                    ]
                                )
                        elif datatype == "meg":
                            if suffix == "meg":
                                lookup_dic[datatype][suffix]["search_terms"].extend(
                                    [
                                        "_ds_",
                                        "_fif_",
                                        "_sqd_",
                                        "_con_",
                                        "_raw_",
                                        "_ave_",
                                        "_mrk_",
                                        "_kdf_",
                                        "_mhd_",
                                        "_trg_",
                                        "_chn_",
                                        "_dat_",
                                        "emptyroom"
                                    ]
                                )
                                lookup_dic[datatype][suffix]["conditions"].extend(
                                    [
                                        '"MNE-BIDS" in unique_dic["sidecar"]["ConversionSoftware"] '
                                        'and unique_dic["Modality"] == "MEG"'
                                    ]
                                )

    # Add  DWI derivatives (TRACEW, FA, ADC) to lookup dictionary
    lookup_dic["dwi_derivatives"] = {
        "exclude": {
            "search_terms": ["trace", "_fa_", "adc"],
            "accepted_entities": [],
            "required_entities": [],
            "conditions": [
                '"DIFFUSION" in unique_dic["ImageType"]'
            ]
        }
    }

    return lookup_dic


def datatype_suffix_identification(dataset_list_unique_series, lookup_dic, config):
    """
    Uses metadata to try to determine the identity (i.e. datatype and suffix)
    of each unique acquisition in uploaded dataset.

    Parameters
    ----------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.

    lookup_dic : dictionary
        Dictionary of information pertaining to datatypes and suffixes in the BIDS specification.
        Included is a series of rules/heuristics to help map imaging sequences to their appropriate
        datatype and suffix labels.

    config : boolean
        True if an ezBIDS configuration file (*ezBIDS_template.json) was detected in the upload

    Returns
    -------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.
    """
    print("")
    print("Datatype & suffix identification")
    print("------------------------------------")
    """
    Schema datatype and suffix labels are helpful, but typically
    researchers label their imaging protocols in less standardized ways.
    ezBIDS will attempt to determine datatype and suffix labels based on
    common keys/labels.
    """
    for index, unique_dic in enumerate(dataset_list_unique_series):
        # Not ideal using json_path because it's only the first sequence in the series_idx group...
        json_path = unique_dic["json_path"]

        if unique_dic["type"] == "exclude" and unique_dic["finalized_match"] is False:
            unique_dic["error"] = "Uploaded imaging data file contains an improper format " \
                "which cannot be read by ezBIDS. Cannot convert file."
            unique_dic["message"] = unique_dic["error"]
        elif unique_dic["finalized_match"] is False:
            # Try checking the json paths themselves for explicit information regarding datatype and suffix
            for datatype in datatypes_yaml:
                if f"/{datatype}/" in json_path:
                    unique_dic["datatype"] = datatype

                rule = yaml.load(open(os.path.join(analyzer_dir, datatype_suffix_rules, datatype) + ".yaml"),
                                 Loader=yaml.FullLoader)

                suffixes = [x for y in [rule[x]["suffixes"] for x in rule] for x in y]

                short_suffixes = [x for x in suffixes if len(x) < 3]

                unhelpful_suffixes = [
                    "fieldmap",
                    "beh",
                    "epi",
                    "magnitude",
                    "magnitude1",
                    "magnitude2",
                    "phasediff"
                ]

                bad_suffixes = short_suffixes + unhelpful_suffixes

                # Remove deprecated suffixes
                deprecated_suffixes = ["T2star", "FLASH", "PD", "phase"]
                suffixes = [x for x in suffixes if x not in deprecated_suffixes]

                for suffix in suffixes:
                    if f"_{suffix}.json" in json_path:
                        unique_dic["suffix"] = suffix

                for bad_suffix in bad_suffixes:
                    if f"_{bad_suffix}.json" in json_path:
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

                # Correct BIDS deprecation issue, func/phase no long exists, now func/bold part-phase
                if unique_dic["datatype"] == "func" and unique_dic["suffix"] == "phase":
                    unique_dic["suffix"] = "bold"

                if unique_dic["datatype"] != "" and unique_dic["suffix"] != "":
                    unique_dic["message"] = "Acquisition is believed to be " \
                        f"{unique_dic['datatype']}/{unique_dic['suffix']} " \
                        f"because '{unique_dic['suffix']}' is in the file path. " \
                        f"Please modify if incorrect."

        if json_path.endswith("blood.json"):
            # Set datatype and suffix values for pet/blood if we know it exists
            unique_dic["datatype"] = "pet"
            unique_dic["suffix"] = "blood"
            unique_dic["type"] = "pet/blood"
            unique_dic["message"] = "Acquisition is believed to be pet/blood " \
                "because the file path ends with '_blood.json. " \
                "Please modify if incorrect."

        if json_path.endswith('_physio.tsv.gz'):
            unique_dic["suffix"] = 'physio'
        if json_path.endswith('_physioevents.tsv.gz'):
            unique_dic["suffix"] = 'physioevents'

        """
        If no luck with the json paths, and assuming an ezBIDS configuration file wasn't provided, try discerning
        datatype and suffix with dcm2niix's BidsGuess. And if that doesn't produce anything, try with search terms
        in SeriesDescription (or ProtocolName) and rules.
        """
        if (unique_dic["finalized_match"] is False
                and (unique_dic["datatype"] == "" or unique_dic["suffix"] == "") and unique_dic["type"] == ""):

            json_data = unique_dic["sidecar"]

            # Try discerning datatype and suffix with dcm2niix's BidsGuess
            if "BidsGuess" in json_data:
                bids_guess = json_data["BidsGuess"]
                if len(bids_guess) == 2:  # should always be length of 2, but just to be safe
                    datatype = str(bids_guess[0]).lower()  # in case BidsGuess doesn't make datatype lowercase
                    suffix = bids_guess[1].split("_")[-1]
                    for bids_ref_suffix in suffixes_yaml:  # in case BidsGuess not use proper suffix case format (e.g PET)
                        if bids_ref_suffix != suffix and bids_ref_suffix.lower() == suffix.lower():
                            suffix = bids_ref_suffix
                    # Issue with BidsGuess and func/sbref identification
                    if suffix == "bold":
                        descriptor = unique_dic["descriptor"]
                        sd = unique_dic[descriptor]
                        sd = re.sub("[^A-Za-z0-9]+", "_", sd).lower() + "_"
                        if "sbref" in sd and unique_dic["NumVolumes"] == 1:
                            suffix = "sbref"

                    if datatype.lower() not in [x for x in datatypes_yaml.keys()]:  # assumed to be non-BIDS data
                        if suffix in ["localizer", "scout"] or "_i0000" in unique_dic["paths"][0]:
                            # localizer
                            unique_dic["message"] = "Acquisition was determined to be a localizer sequence, " \
                                "according to dcm2niix's BidsGuess heuristic, and will not be converted to BIDS. " \
                                "Please modify if incorrect."
                        else:
                            # other non-BIDS data
                            unique_dic["message"] = "Acquisition was determined to be a non-BIDS sequence, " \
                                "according to dcm2niix's BidsGuess heuristic, and will not be converted. " \
                                "Please modify if incorrect."
                        unique_dic["type"] = "exclude"
                    else:
                        unique_dic["datatype"] = datatype
                        unique_dic["suffix"] = suffix
                        unique_dic["message"] = f"Acquisition is believed to be " \
                            f"{unique_dic['datatype']}/{unique_dic['suffix']} based on " \
                            "the dcm2niix BidsGuess heuristic. Please modify if incorrect."
                else:
                    pass

            """
            If dcm2niix's BidsGuess can't give us datatype and suffix information, move on to next heuristic (search
            terms in SeriesDescription [or ProtocolName] and rules).
            """
            if (unique_dic["datatype"] == "" or unique_dic["suffix"] == "") and unique_dic["type"] != "exclude":

                descriptor = unique_dic["descriptor"]
                sd = unique_dic[descriptor]

                # Make easier to find search terms in the SeriesDescription (or ProtocolName)
                sd = re.sub("[^A-Za-z0-9]+", "_", sd).lower() + "_"
                # sd_sparse = re.sub("[^A-Za-z0-9]+", "", sd)

                cont = True
                for datatype in lookup_dic.keys():
                    if datatype not in ["localizer", "dwi_derivatives"]:
                        suffixes = lookup_dic[datatype].keys()
                        for suffix in suffixes:
                            search_terms = lookup_dic[datatype][suffix]["search_terms"]
                            conditions = lookup_dic[datatype][suffix]["conditions"]
                            eval_checks = [eval(t, {"sd": sd,
                                                    "unique_dic": unique_dic,
                                                    "dataset_list_unique_series": dataset_list_unique_series,
                                                    "index": index
                                                    }) for t in conditions]
                            if any(x in sd for x in search_terms):
                                # Search term match
                                conditions = [
                                    (x.replace("unique_dic", "").replace('["', "").replace('"]', "").
                                        replace("dataset_list_unique_series[index - 2]", "")) for x in conditions
                                ]
                                search_hit = [x for x in search_terms if re.findall(x, sd)][0]

                                if len([t for t in eval_checks if t is True]) == len(conditions):
                                    # Search term match, as well as all necessary conditions for datatype/suffix pair
                                    unique_dic["datatype"] = datatype
                                    unique_dic["suffix"] = suffix
                                    unique_dic["type"] = ""
                                    if len(conditions):
                                        condition_passes = [
                                            f"({index+1}): {value}" for index, value in enumerate(conditions)
                                        ]
                                        unique_dic["message"] = f"Acquisition is believed to be {datatype}/{suffix} " \
                                            f"because '{search_hit}' is in the {unique_dic['descriptor']} and the " \
                                            f"following conditions are met: {condition_passes}. " \
                                            "Please modify if incorrect."
                                    else:
                                        unique_dic["message"] = f"Acquisition is believed to be {datatype}/{suffix} " \
                                            f"because '{search_hit}' is in the {unique_dic['descriptor']}. " \
                                            "Please modify if incorrect."
                                    cont = False
                                    break
                                else:
                                    unique_dic["type"] = "exclude"
                                    condition_fails_ind = [i for (i, v) in enumerate(eval_checks) if v is False]
                                    condition_fails = [v for (i, v) in enumerate(conditions) if i in condition_fails_ind]
                                    condition_fails = [
                                        f"({index+1}): {value}" for index, value in enumerate(condition_fails)
                                    ]

                                    if (datatype in ["func", "dwi"]
                                            and (unique_dic["ndim"] == 3 and unique_dic["NumVolumes"] > 1)):
                                        """
                                        func and dwi can also have sbref suffix pairings, so 3D dimension data with
                                        only a single volume likely indicates that the sequence was closer to being
                                        identified as a func (or dwi) sbref.
                                        """
                                        suffix = "sbref"

                                    unique_dic["message"] = f"Acquisition was thought to be {datatype}/{suffix} " \
                                        f"because '{search_hit}' is in the {unique_dic['descriptor']}, but the " \
                                        f"following conditions were not met: {condition_fails}. Please modify " \
                                        "if incorrect."

                            elif datatype == "dwi" and suffix == "dwi" and any(".bvec" in x for x in unique_dic["paths"]):
                                unique_dic["datatype"] = datatype
                                unique_dic["suffix"] = suffix
                                unique_dic["message"] = f"Acquisition is believed to be {datatype}/{suffix} " \
                                    "because associated bval/bvec files were found for this sequence. " \
                                    "Please modify if incorrect."
                        if cont is False:
                            break
                    else:
                        # Localizers
                        if datatype == "localizer":
                            search_terms = lookup_dic[datatype]["exclude"]["search_terms"]
                            conditions = lookup_dic["localizer"]["exclude"]["conditions"]
                            eval_checks = [eval(t, {"sd": sd, "unique_dic": unique_dic}) for t in conditions]
                            if (any(x in sd for x in search_terms)
                                    or len([t for t in eval_checks if t]) == len(conditions)):
                                unique_dic["type"] = "exclude"
                                unique_dic["error"] = "Acquisition appears to be a localizer"
                                unique_dic["message"] = "Acquisition is believed to be a " \
                                    "localizer and will therefore not be converted to BIDS. Please " \
                                    "modify if incorrect."
                        # DWI derivatives (TRACEW, FA, ADC)
                        elif datatype == "dwi_derivatives":
                            search_terms = lookup_dic[datatype]["exclude"]["search_terms"]
                            conditions = lookup_dic["dwi_derivatives"]["exclude"]["conditions"]
                            eval_checks = [eval(t, {"sd": sd, "unique_dic": unique_dic}) for t in conditions]
                            if (any(x in sd for x in search_terms)
                                    and len([t for t in eval_checks if t]) == len(conditions)):
                                unique_dic["type"] = "exclude"
                                unique_dic["error"] = "Acquisition appears to be a TRACEW, FA, or " \
                                    "ADC, which are unsupported by ezBIDS and will therefore not " \
                                    "be converted."
                                unique_dic["message"] = "Acquisition is believed to be a dwi derivative " \
                                    "(TRACEW, FA, ADC), which are not supported by BIDS and will not " \
                                    "be converted. Please modify if incorrect."

            """
            Can't determine datatype and suffix pairing, assume not BIDS-compliant acquisition,
            unless user specifies otherwise.
            """
            if ((unique_dic["datatype"] == "" or unique_dic["suffix"] == "")
                    and unique_dic["type"] == "" and unique_dic["message"] is None):
                unique_dic["error"] = "Acquisition cannot be resolved. Please " \
                    "determine whether or not this acquisition should be " \
                    "converted to BIDS."
                unique_dic["message"] = "Acquisition is unknown because there " \
                    "is not enough adequate information. Please modify if " \
                    "acquisition is desired for BIDS conversion, otherwise " \
                    "the acquisition will not be converted."
                unique_dic["type"] = "exclude"

        # Combine datatype and suffix to create type variable, which is needed for internal brainlife.io storage
        if unique_dic["finalized_match"] is False and "exclude" not in unique_dic["type"]:
            unique_dic["type"] = unique_dic["datatype"] + "/" + unique_dic["suffix"]

        """
        For non-normalized anatomical acquisitions, provide message that
        they may have poor CNR and should consider excluding them from BIDS
        conversion if a corresponding normalized acquisition is present.
        """
        if (unique_dic["finalized_match"] is False
                and unique_dic["datatype"] == "anat" and "NORM" not in unique_dic["ImageType"]):
            unique_dic["message"] = unique_dic["message"] + (
                " Additionally, this acquisition appears to be "
                "non-normalized, potentially having poor CNR. "
                "If there is a corresponding normalized acquisition "
                "('NORM' in the ImageType metadata field), consider "
                "excluding this current one from BIDS conversion."
            )

        # Warn user about non-RMS multi-echo anatomical acquisitions
        if (unique_dic["finalized_match"] is False
                and unique_dic["datatype"] == "anat"
                and "EchoNumber" in unique_dic["sidecar"]
                and "MEAN" not in unique_dic["ImageType"]):
            # unique_dic["type"] = "exclude"
            unique_dic["message"] = unique_dic["message"] + " " + (
                "Acquisition also appears to be an anatomical multi-echo, but not the "
                "combined RMS file. If the RMS file exists it is ideal to exclude this "
                "acquisition and only save the RMS file, not the individual echoes.")

    """
    If there's multi-echo anatomical data and we have the mean (RMS) file, exclude the
    individual echo sequences, since the BIDs validator will generate an error with them.
    """
    if config is False:
        anat_ME_RMS = [
            ind for (ind, v) in enumerate(dataset_list_unique_series)
            if v["datatype"] == "anat"
            and "MEAN" in v["ImageType"]
        ]

        if len(anat_ME_RMS):
            for anat_ME_RMS_index in anat_ME_RMS:
                sd = dataset_list_unique_series[anat_ME_RMS_index][descriptor]
                anat_ind_ME_indices = [
                    x for (x, v) in enumerate(dataset_list_unique_series)
                    if re.sub("[^A-Za-z0-9]+", "", v[descriptor]) == re.sub("[^A-Za-z0-9]+", "", sd).replace("RMS", "")
                ]

                for anat_ind_ME_index in anat_ind_ME_indices:
                    dataset_list_unique_series[anat_ind_ME_index]["message"] = (
                        " A mean RMS anatomical file combining the multiple echoes has been found, "
                        "thus this individual anatomical echo file will be excluded from conversion. "
                        "Please modify if incorrect."
                    )
                    dataset_list_unique_series[anat_ind_ME_index]["type"] = "exclude"

    return dataset_list_unique_series


def entity_labels_identification(dataset_list_unique_series, lookup_dic):
    """
    Function to determine acquisition entity label information (e.g. dir-, echo-)
    based on acquisition metadata. Entities are then sorted in accordance with
    BIDS specification ordering.

    Parameters
    ----------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.

    lookup_dic : dictionary
        Dictionary of information pertaining to datatypes and suffixes in the BIDS specification.
        Included is a series of rules/heuristics to help map imaging sequences to their appropriate
        datatype and suffix labels.

    Returns
    -------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.
    """
    print("")
    print("Entity label identification")
    print("----------------------------")
    entity_ordering = yaml.load(open(os.path.join(analyzer_dir, entity_ordering_file)), Loader=yaml.FullLoader)

    tb1afi_tr = 1
    tb1srge_td = 1
    for unique_dic in dataset_list_unique_series:
        if unique_dic["finalized_match"] is False:

            series_entities = {}
            descriptor = unique_dic["descriptor"]
            regex = r'[^\w.]'  # "[^A-Za-z0-9]+"
            sd = re.sub(regex, "_", unique_dic[descriptor]).lower() + "_"
            json_path = unique_dic["json_path"]

            # Check to see if entity labels can be determined from BIDS naming convention
            for key in entities_yaml:
                if key not in ["subject", "session", "direction"]:  # ezBIDS already knows PED for dir entity label
                    entity = entities_yaml[key]['entity']
                    if f"_{entity}_" in sd:
                        # series_entities[key] = re.split(regex, sd.split(f"{entity}_")[-1])[0].replace("_", "")
                        # series_entities[key] = re.split('_', sd.split(f"{entity}_")[-1])[0] Used as of 12/13/23
                        series_entities[key] = re.split('[^a-zA-Z0-9]', re.split('_', sd.split(f"{entity}_")[-1])[0])[0]
                    elif f"_{entity}-" in json_path:
                        series_entities[key] = re.split('[^a-zA-Z0-9]', json_path.split(f"{entity}-")[-1])[0]
                    else:
                        series_entities[key] = ""
                else:
                    series_entities[key] = ""

                # MEG data was given a placeholder task entity label, so remove it
                if key == "task" and series_entities["task"] == "unknown":
                    series_entities["task"] = ""

            # If BIDS naming convention isn't detected, do a more thorough check for certain entities labels
            # task
            func_rest_keys = ["rest", "rsfmri", "fcmri", "resting"]
            # if any(x in re.sub("[^A-Za-z0-9]+", "", sd).lower() for x in func_rest_keys) and not series_entities["task"]:
            if any(x in func_rest_keys for x in sd.split('_')) and not series_entities["task"]:
                series_entities["task"] = "rest"
            else:
                match_index = [
                    x for x, y in enumerate(re.search(x, sd, re.IGNORECASE) for x in cog_atlas_tasks) if y is not None
                ]
                if len(match_index):
                    task_name = cog_atlas_tasks[match_index[0]]
                    if len(task_name) < 4:  # Too many possible false positives with short task names
                        if any(f"task-{task_name}" in x for x in [unique_dic["json_path"], unique_dic["SeriesDescription"]]):
                            series_entities["task"] = cog_atlas_tasks[match_index[0]]
                    else:
                        series_entities["task"] = cog_atlas_tasks[match_index[0]]

            if (any(x in re.sub("[^A-Za-z0-9]+", "", sd).lower() for x in ["noise", "emptyroom"])
                    or series_entities["subject"] == "emptyroom"):  # for MEG data
                series_entities["task"] = "noise"

            # dir (short for direction; required for fmap/epi and highly recommended for dwi/dwi)
            if any(x in unique_dic["type"] for x in ["fmap/epi", "dwi/dwi"]):
                series_entities["direction"] = unique_dic["direction"]

            # echo
            if (unique_dic["EchoNumber"]
                and not any(x in unique_dic["type"]for x in
                            [
                                "fmap/epi",
                                "fmap/magnitude1",
                                "fmap/magnitude2",
                                "fmap/phasediff",
                                "fmap/phase1",
                                "fmap/phase2",
                                "fmap/fieldmap"])):
                series_entities["echo"] = str(unique_dic["EchoNumber"])

            # flip
            if (any(x in unique_dic["type"] for x in ["anat/VFA", "anat/MPM", "anat/MTS", "fmap/TB1EPI", "fmap/TB1DAM"])
                    and "FlipAngle" in unique_dic["sidecar"]):
                regex = re.compile('flip([1-9]*)')
                try:
                    series_entities["flip"] = regex.findall(re.sub("[^A-Za-z0-9]+", "", sd))[0]
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

            if unique_dic["sidecar"]["Manufacturer"] in ["Elekta", "Neuromag", "MEGIN"]:  # For specific MEG instances
                sds = [x["SeriesDescription"] for x in dataset_list_unique_series]
                # For MEG data, certain systems contain crosstalk and calibration file pairs
                if any(".fif" in x for x in sds) and any(".dat" in x for x in sds):
                    if unique_dic["SeriesDescription"].endswith(".dat"):  # calibration file
                        series_entities["acquisition"] = "calibration"
                    elif unique_dic["SeriesDescription"].endswith(".fif"):  # crosstalk file
                        series_entities["acquisition"] = "crosstalk"

            # inversion
            if (any(x in unique_dic["type"] for x in ["anat/MP2RAGE", "anat/IRT1"])
                    and "InversionTime" in unique_dic["sidecar"]):
                # inversion_time = unique_dic["sidecar"]["InversionTime"]
                regex = re.compile('inv([1-9]*)')
                try:
                    series_entities["inversion"] = regex.findall(re.sub("[^A-Za-z0-9]+", "", sd))[0]
                except:
                    series_entities["inversion"] = ""

            # part
            if "REAL" in unique_dic["ImageType"]:
                series_entities["part"] = "real"
            elif "IMAGINARY" in unique_dic["ImageType"]:
                series_entities["part"] = "imag"
            elif "fmap" not in unique_dic["type"] and "PHASE" in unique_dic['ImageType']:
                series_entities["part"] = "phase"
            else:
                pass

            # rec (reconstruction)
            if series_entities['reconstruction'] == 'pointspreadfunctionmodellingtimeofflight':
                series_entities['reconstruction'] = 'PSTOF'

            # Make sure any found entities are allowed for specific datatype/suffix pair
            if unique_dic["type"] != "exclude":
                datatype = unique_dic["datatype"]
                suffix = unique_dic["suffix"]
                exposed_entities = [x[0] for x in series_entities.items() if x[1] != ""]

                for exposed_entity in exposed_entities:
                    accepted_entities = lookup_dic[datatype][suffix]["accepted_entities"]
                    if exposed_entity not in accepted_entities:
                        if datatype == "anat" and exposed_entity == "echo":
                            """
                            BIDS is probably going to allow echo entity label for anatomical,
                            even though currently the BIDS validator will fail in this instance.
                            See https://github.com/bids-standard/bids-specification/pull/1570
                            """
                            pass
                        else:
                            series_entities[exposed_entity] = ""

            """
            Replace periods in series entities with "p", if found. If other
            non alphanumeric characters are found in the entity labels, remove them
            """
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


def check_part_entity(dataset_list_unique_series, config):
    """
    Certain data contain the part-phase entity key/value pair. If this occurs, expose the part-mag key/value pair
    for the corresponding data.

    Parameters
    ----------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.

    config : boolean
        True if an ezBIDS configuration file (*ezBIDS_template.json) was detected in the upload.

    Returns
    -------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.
    """
    if config is False:
        part_phase_data = [x for x in dataset_list_unique_series if x["entities"]["part"] == "phase"]

        for part in part_phase_data:
            mag_data = [
                x for x in dataset_list_unique_series if x != part
                and x["SeriesDescription"] == part["SeriesDescription"]
                and x["type"] == part["type"]
                and ({key: val for key, val in x["entities"].items() if key != "part"}
                     == {key: val for key, val in part["entities"].items() if key != "part"})
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

    Parameters
    ----------
    dataset_list : list
        List of dictionaries containing pertinent and unique information about
        the data, primarily coming from the metadata in the json files.

    Returns
    -------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.
    """
    for unique_dic in dataset_list_unique_series:
        for data in dataset_list:
            if data["series_idx"] == unique_dic["series_idx"]:
                data["entities"] = unique_dic["entities"]
                data["type"] = unique_dic["type"]
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
        the data, primarily coming from the metadata in the json files.

    Returns
    -------
    objects_list : list
        List of dictionaries of all dataset acquisitions.
    """
    objects_list = []

    entity_ordering = yaml.load(open(os.path.join(analyzer_dir, entity_ordering_file)), Loader=yaml.FullLoader)

    # Find unique subject/session idx pairs in dataset and sort them
    subj_ses_pairs = [[x["subject_idx"], x["session_idx"]] for x in dataset_list]
    unique_subj_ses_pairs = sorted([list(i) for i in set(tuple(i) for i in subj_ses_pairs)])

    for unique_subj_ses in unique_subj_ses_pairs:
        scan_protocol = [
            x for x in dataset_list
            if x["subject_idx"] == unique_subj_ses[0]
            and x["session_idx"] == unique_subj_ses[1]
        ]

        objects_data = []

        """
        Peruse scan protocol to check for potential issues and add some
        additional information.
        """
        for protocol in scan_protocol:
            if protocol["nibabel_image"] == "n/a":
                protocol["headers"] = "n/a"
            else:
                image = protocol["nibabel_image"]
                protocol["headers"] = str(image.header).splitlines()[1:]

                object_img_array = image.dataobj
                if object_img_array.dtype not in ["<i2", "<u2", "<f4", "int16", "uint16"]:
                    # Weird edge case where data array is RGB instead of integer
                    protocol["exclude"] = True
                    protocol["error"] = "The data array for this " \
                        "acquisition is improper, suggesting that " \
                        "this isn't an imaging file or is a non-BIDS " \
                        "specified acquisition and will not be converted. " \
                        "Please modify if incorrect."
                    protocol["message"] = protocol["error"]
                    protocol["type"] = "exclude"

                # Check for negative dimensions and exclude from BIDS conversion if they exist
                if len([x for x in image.shape if x < 0]):
                    protocol["exclude"] = True
                    protocol["type"] = "exclude"
                    protocol["error"] = "Image contains negative dimension(s) and cannot be converted to BIDS format"
                    protocol["message"] = "Image contains negative dimension(s) and cannot be converted to BIDS format"

            if protocol["error"]:
                protocol["error"] = [protocol["error"]]
            else:
                protocol["error"] = []

            objects_entities = dict(zip([x for x in entities_yaml], [""] * len([x for x in entities_yaml])))

            # Re-order entities to what BIDS expects
            objects_entities = dict(sorted(objects_entities.items(), key=lambda pair: entity_ordering.index(pair[0])))

            # Make items list (part of objects list)
            items = []
            for item in protocol["paths"]:
                if item.endswith(".bval"):
                    items.append({"path": item,
                                  "name": "bval"})
                elif item.endswith(".bvec"):
                    items.append({"path": item,
                                  "name": "bvec"})
                elif item.endswith(".json"):
                    items.append({"path": item,
                                  "name": "json",
                                  "sidecar": protocol["sidecar"]})
                    if item.endswith("blood.json"):
                        path = item.split(".json")[0] + ".tsv"
                        headers = [x for x in pd.read_csv(path, sep="\t").columns]
                        items.append({"path": path,
                                      "name": "tsv",
                                      "headers": headers})
                elif item.endswith(".nii.gz"):
                    items.append({"path": item,
                                  "name": "nii.gz",
                                  "pngPaths": [],
                                  "headers": protocol["headers"]})
                elif item.endswith(tuple(MEG_extensions)):
                    if item.endswith('.ds'):
                        name = '.ds'
                    else:
                        name = Path(item).suffix
                    items.append({"path": item,
                                  "name": name,
                                  "pngPaths": [],
                                  "headers": protocol["headers"]})
                elif item.endswith('tsv.gz'):
                    items.append({
                        "path": item,
                        "name": 'tsv.gz',
                        "pngPaths": [],
                        "headers": protocol["headers"]
                    })

            # Objects-level info for ezBIDS_core.json
            objects_info = {
                "subject_idx": protocol["subject_idx"],
                "session_idx": protocol["session_idx"],
                "series_idx": protocol["series_idx"],
                "message": protocol["message"],
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
                    "section_id": 1
                }
            }
            objects_data.append(objects_info)

        objects_list.append(objects_data)

    # Flatten list of lists
    objects_list = [x for y in objects_list for x in y]

    return objects_list


def extract_series_info(dataset_list_unique_series):
    """
    Extracts a subset of the acquisition information, which will be displayed on
    the Series-level page of the ezBIDS UI.

    Parameters
    ----------
    dataset_list_unique_series : list of dictionaries
        A modified version of dataset_list, where this list contains only the
        dictionaries of acquisitions with a unique series group ID.

    Returns
    -------
    ui_series_info_list : list
        List of dictionaries containing subset of acquisition information to be
        displayed to user on the ezBIDS Series Mapping web page.
    """
    ui_series_info_list = []
    for unique_dic in dataset_list_unique_series:
        ui_series_info = {
            "SeriesDescription": unique_dic["SeriesDescription"],
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
            "PED": unique_dic["direction"],
            "entities": unique_dic["entities"],
            "type": unique_dic["type"],
            "error": unique_dic["error"],
            "message": unique_dic["message"],
            "object_indices": []
        }

        ui_series_info_list.append(ui_series_info)

    return ui_series_info_list


def check_dwi_b0maps(dataset_list_unique_series):
    for unique_dic in dataset_list_unique_series:
        if (unique_dic['type'] == 'dwi/dwi'
            and unique_dic['NumVolumes'] < 10
                and (not any(x.endswith('.bval') for x in unique_dic['paths']) and not unique_dic['exclude'])
                or any(x in unique_dic['SeriesDescription'] for x in ('b0map', '_b0_', 'b0_'))):

            # What we (likely have are DWI b0map sequences, which should be mapped as fmap/epi according to BIDS)
            unique_dic['datatype'] = 'fmap'
            unique_dic['suffix'] = 'epi'
            unique_dic['type'] = 'fmap/epi'
            if any(x in unique_dic['SeriesDescription'] for x in ('b0map', '_b0_', 'b0_')):
                more_message = ', and b0map, _b0_, or b0_ is in the sequence description'
            else:
                more_message = ''
            unique_dic["message"] = "Acquisition was determined to be fmap/epi because either there are no " \
                f"corresponding bval/bvec files, or the number of volumes is < 10 {more_message}. In BIDS parlance, " \
                "this DWI b0map should be fmap/epi rather than dwi/dwi " \
                "(for reference, see https://neurostars.org/t/bids-b0-correction-for-dwi/3802). " \
                "Please modify if incorrect."

    return dataset_list_unique_series


# Begin (Apply functions)
print("########################################")
print("Beginning conversion process of uploaded dataset")
print("########################################")
print("")

# Load dataframe containing all uploaded files
try:
    uploaded_img_list = natsorted(pd.read_csv("list", header=None, lineterminator='\n').to_numpy().flatten().tolist())
except:
    # Need for [rare] instances where a comma (or other escape character) is in the file path
    uploaded_img_list = natsorted(
        pd.read_csv("list", sep=' ', header=None, lineterminator='\n').to_numpy().flatten().tolist()
    )

# Remove dots in file names (that aren't extensions). This screws up the bids-validator otherwise
uploaded_img_list = fix_multiple_dots(uploaded_img_list)

# Generate MEG json files, if MEG data was provided
generate_MEG_json_sidecars(uploaded_img_list)

# Filter uploaded files list for files that ezBIDS can't use and check for ezBIDS configuration file
uploaded_files_list, exclude_data, config, config_file = modify_uploaded_dataset_list(uploaded_img_list)

# # Generate list of all possible Cognitive Atlas task terms
cog_atlas_tasks = find_cog_atlas_tasks(cog_atlas_url)

# Create the dataset list of dictionaries
dataset_list = generate_dataset_list(uploaded_files_list, exclude_data)


# Get pesudo subject (and session) info
dataset_list = organize_dataset(dataset_list)

# Determine subject (and session) information
dataset_list, subjects_information, participants_info = determine_sub_ses_IDs(dataset_list, bids_compliant)

# Make a new list containing the dictionaries of only unique dataset acquisitions
dataset_list, dataset_list_unique_series = determine_unique_series(dataset_list, bids_compliant)


# If ezBIDS configuration file detected in upload, use that for datatype, suffix, and entity identifications
if config is True:
    readme, dataset_description_dic, participants_column_info, dataset_list_unique_series, subjects_information, events = \
        template_configuration(dataset_list_unique_series, subjects_information, config_file)

else:
    # README
    readme = generate_readme(DATA_DIR, bids_compliant)

    # dataset description information
    dataset_description_dic = generate_dataset_description(DATA_DIR, bids_compliant)

    # participantsColumn portion of ezBIDS_core.json
    participants_column_info = generate_participants_columns(DATA_DIR, bids_compliant)

    # Events timing file information
    events = {
        "columnKeys": None,
        "columns": {
            "onsetLogic": "eq",
            "onset": None,
            "onset2": None,
            "onsetUnit": "sec",
            "durationLogic": "eq",
            "duration": None,
            "duration2": None,
            "durationUnit": "sec",
            "sampleLogic": "eq",
            "sample": None,
            "sample2": None,
            "sampleUnit": "samples",
            "trialType": None,
            "responseTimeLogic": "eq",
            "responseTime": None,
            "responseTime2": None,
            "responseTimeUnit": "sec",
            "values": None,
            "HED": None,
            "stim_file": None
        },
        "loaded": False,
        "sampleValues": {},
        "trialTypes": {
            "desc": "Indicator of type of action that is expected",
            "levels": {},
            "longName": "Event category"
        }
    }

# Generate lookup information directory to help with datatype and suffix identification (and to some degree, entities)
lookup_dic = create_lookup_info()

# Identify datatype and suffix information
dataset_list_unique_series = datatype_suffix_identification(dataset_list_unique_series, lookup_dic, config)

# Look for DWI b0maps, which are actually fmap/epi in BIDS parlance
dataset_list_unique_series = check_dwi_b0maps(dataset_list_unique_series)

# Identify entity label information
dataset_list_unique_series = entity_labels_identification(dataset_list_unique_series, lookup_dic)

print("")
print("--------------------------")
print("ezBIDS sequence message")
print("--------------------------")
for index, unique_dic in enumerate(dataset_list_unique_series):
    print(unique_dic["message"])
    print("")

dataset_list_unique_series = check_part_entity(dataset_list_unique_series, config)

# If BIDS-compliant dataset uploaded, set and apply IntendedFor mapping
dataset_list_unique_series = set_IntendedFor_B0FieldIdentifier_B0FieldSource(dataset_list_unique_series, bids_compliant)

# Port series level information to all other acquisitions (i.e. objects level) with same series info
dataset_list = update_dataset_list(dataset_list, dataset_list_unique_series)

# Apply a few other changes to the objects level
objects_list = modify_objects_info(dataset_list)

# Map unique series IDs to all other acquisitions in dataset that have those parameters
print("------------------")
print("ezBIDS overview")
print("------------------")
for index, unique_dic in enumerate(dataset_list_unique_series):
    print(
        f"Unique data acquisition file {unique_dic['nifti_path']}, "
        f"Series Description {unique_dic['SeriesDescription']}, "
        f"was determined to be {unique_dic['type']}, "
        f"with entity labels {[x for x in unique_dic['entities'].items() if x[-1] != '']}"
    )
    print("")
    print("")

# Extract important series information to display in ezBIDS UI
ui_series_info_list = extract_series_info(dataset_list_unique_series)

# Convert information to dictionary
EZBIDS = {
    "readme": readme,
    "datasetDescription": dataset_description_dic,
    "subjects": subjects_information,
    "participantsColumn": participants_column_info,
    "participantsInfo": participants_info,
    "series": ui_series_info_list,
    "objects": objects_list,
    "events": events
}

# Write dictionary to ezBIDS_core.json
with open("ezBIDS_core.json", "w") as fp:
    json.dump(EZBIDS, fp, indent=3)

print(f"--- Analyzer completion time: {time.perf_counter() - start_time} seconds ---")
