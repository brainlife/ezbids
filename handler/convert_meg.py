#!/usr/bin/env python3

"""
Takes the ezBIDS data (finalized.json) and uses MNE-BIDS to perform the BIDS conversion for this
specific modality data.

Regarding emptyroom recordings and their BIDS specification, there are 4 scenarios:
1). One noise recording per subject (one subject in day)
2). One noise recording per day (multiple subjects in day)
3). One or very few noise recordings per full dataset
4). No noise recordings in entire dataset

Given the difficulty in determing the various ways imaging data may match with emptyroom data, will have a separate
sub-emptyroom folder. This will makes things simplier.
"""

import sys
import json
from datetime import datetime
from mne.io import read_raw
from mne_bids import (BIDSPath, write_raw_bids)

# Begin:
finalized_json_data = json.load(open(sys.argv[1]), strict=False)
bids_root_dir = sys.argv[2]

sub_info = finalized_json_data["subjects"]
subjects = [x["subject"] for x in sub_info]

# See how many MEG objects there are
objects = finalized_json_data["objects"]
for obj in objects:
    obj_type = obj["_type"]
    if "meg" in obj_type:
        datatype = "meg"

        raw = read_raw(obj["_SeriesDescription"], verbose=0)

        # Get entity information
        entities = obj["_entities"]
        sub_idx = obj["subject_idx"]
        ses_idx = obj["session_idx"]

        # sub
        sub = sub_info[sub_idx]["subject"]

        # ses
        ses_info = sub_info[sub_idx]["sessions"][ses_idx]
        if ses_info["session"] != "":
            ses = ses_info["session"]
            if ses_info["exclude"] is True:
                ses = None
        else:
            ses = None

        # task
        task = entities["task"]

        # acquisition
        if entities["acquisition"] == "":
            acq = None
        else:
            acq = entities["acquisition"]

        # run
        if entities["run"] == "":
            run = None
        else:
            run = entities["run"]

        # processing
        if entities["processing"] == "":
            proc = None
        else:
            proc = entities["processing"]

        # split
        if entities["split"] == "":
            split = None
        else:
            split = entities["split"]

        # Set up BIDS configuration (for MEG data only)
        if sub == "emptyroom":
            raw_er = raw
            # Specify the BIDS path for emptyroom (ER) recording
            bids_path_er = BIDSPath(
                subject=sub,
                session=ses,
                task="noise",
                acquisition=acq,
                run=run,
                processing=proc,
                split=split,
                datatype=datatype,
                root=bids_root_dir
            )

            # Write ER data to BIDS structure
            write_raw_bids(raw_er, bids_path=bids_path_er, overwrite=True)
        else:
            raw_data = raw
            # Specify the BIDS path for imaging data
            bids_path_data = BIDSPath(
                subject=sub,
                session=ses,
                task=task,
                acquisition=acq,
                run=run,
                processing=proc,
                split=split,
                datatype=datatype,
                root=bids_root_dir
            )

            raw_data_dt = [
                int(x) for x in obj["AcquisitionDate"].split("-") + obj["AcquisitionTime"].split(":")[:-1]
            ]
            raw_data_datetime = datetime(
                raw_data_dt[0],
                raw_data_dt[1],
                raw_data_dt[2],
                raw_data_dt[3],
                raw_data_dt[4]
            )

            # Does ER data exist?
            num_er = [x for x in subjects if x == "emptyroom"]
            er_datetimes = []
            if len(num_er):
                """
                Determine which ER datetime recording is closest (and before) the imaging data. For reference, see
                https://www.geeksforgeeks.org/python-find-the-closest-date-from-a-list/#
                """
                er_sub_idxs = [idx for idx, value in enumerate(subjects) if value == "emptyroom"]
                er_objs = [x for x in objects if x["subject_idx"] in er_sub_idxs]
                er_objs_acq_datetimes = [
                    x["AcquisitionDate"].split("-") + x["AcquisitionTime"].split(":")[:-1] for x in er_objs
                ]

                for i in er_objs_acq_datetimes:
                    er_datetimes.append(datetime(int(i[0]), int(i[1]), int(i[2]), int(i[3]), int(i[4])))

                # get all differences with date as values
                clos_dict = {abs(raw_data_datetime.timestamp() - date.timestamp()): date for date in er_datetimes}

                # extracting minimum key using min()
                res = clos_dict[min(clos_dict.keys())]

                corr_er = [
                    x for x in er_objs if x["AcquisitionDate"] == res.strftime("%Y-%m-%d")
                    and res.strftime("%H:%M") in x["AcquisitionTime"]
                ][0]  # Should only be length of 1

                raw_er = read_raw(corr_er["_SeriesDescription"], verbose=0)

                # Write MEG data to BIDS structure (with corresponding ER)
                write_raw_bids(raw_data, bids_path=bids_path_data, empty_room=raw_er, overwrite=True)

            else:
                # Write MEG data to BIDS structure (no corresponding ER)
                write_raw_bids(raw_data, bids_path=bids_path_data, overwrite=True)

print("Finished MEG BIDS conversion (with MNE-BIDS)")
print("")
