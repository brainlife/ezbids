#!/usr/bin/env python3

"""
Takes the ezBIDS data (finalized.json) and uses MNE-BIDS to perform the BIDS conversion for this
specific modality data.
"""

import sys
import json
from mne.io import read_raw
from mne_bids import (BIDSPath, write_raw_bids)

# Begin:
finalized_json_data = json.load(open(sys.argv[1]), strict=False)
bids_root_dir = sys.argv[2]

# subjects = finalized_json_data["subjects"]  # Is this the final say?
subjects = [x["_entities"]["subject"] for x in finalized_json_data["objects"]]

# Let's see how many MEG objects there are
for obj in finalized_json_data["objects"]:
    obj_type = obj["_type"]
    if "meg" in obj_type:
        datatype = "meg"
        img_data = obj["_SeriesDescription"]

        raw = read_raw(img_data, verbose=0)

        # Get entity information
        entities = obj["_entities"]
        sub_idx = obj["subject_idx"]
        ses_idx = obj["session_idx"]

        # sub
        sub = subjects[sub_idx]["subject"]

        # ses
        ses = subjects[sub_idx]["sessions"][ses_idx]
        if ses["session"] == "" or ses["exclude"] is True:
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

        # Create an MNE BIDSpath
        bids_path = BIDSPath(
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

        print("Converting MEG data to BIDS")
        empty_room = None
        if "emptyroom" in subjects and sub != "emptyroom":
            er_idx = subjects.index("emptyroom")
            raw_er_data = finalized_json_data["objects"][er_idx]["SeriesDescription"]
            raw_er = read_raw(raw_er_data, verbose=0)
            empty_room = raw_er

        write_raw_bids(raw, bids_path=bids_path, verbose=0, empty_room=empty_room, overwrite=True)

print("Finished MEG BIDS conversion (with MNE-BIDS)")
print("")
