#!/usr/bin/env python3

"""
The purpose of this code is to filter BIDS information (data type, suffix, and entity labels) discerned from the
ezBIDS Core. This will be passed to the telemetry service, so that comparisons between what ezBIDS guessed vs the
final product (with user modifications) can be made.

@author: dlevitas
"""

import os
import sys
import json

# Begin
DATA_DIR = sys.argv[1]
os.chdir(DATA_DIR)

# Create telemetry information from the ezBIDS Core json (ezBIDS guesses) as the finalized json (including user edits)


def gather_telemetry(dtype):
    if dtype == 'core':
        json_path = f'{DATA_DIR}/ezBIDS_core.json'
        output_file = "ezBIDS_core_telemetry.json"
        error_message = 'There is no ezBIDS_core.json file, indicating failure during the ezBIDS Core processing. \
            Please contact support for assistance'
    else:
        json_path = f'{DATA_DIR}/finalized.json'
        output_file = "ezBIDS_finalized_telemetry.json"
        error_message = 'There is no ezBIDS finalized file, indicating either failure during ezBIDS or inability to \
            finalize dataset. Please contact support for assistance'

    if os.path.isfile(json_path):
        json_data = open(json_path)
        json_data = json.load(json_data, strict=False)

        for obj in json_data['objects']:

            subject_idx = obj['subject_idx']
            session_idx = obj['session_idx']
            series_idx = obj['series_idx']

            idx = str(subject_idx) + str(session_idx) + str(series_idx)

            seq_file_name = json_data['series'][series_idx]['nifti_path']

            ezBIDS_type = json_data['series'][series_idx]['type']
            if '/' in ezBIDS_type:
                data_type = ezBIDS_type.split('/')[0]
                suffix = ezBIDS_type.split('/')[-1]
            else:
                data_type = 'exclude'
                suffix = 'exclude'

            rationale = json_data['series'][series_idx]['message']

            entities = json_data['series'][series_idx]['entities']
            known_entities = {}
            for entity_key in entities:
                if entities[entity_key] != '':
                    entity_val = entities[entity_key]
                    known_entities[entity_key] = entity_val

            ezBIDS_telemetry_info_list.append([idx, seq_file_name, data_type, suffix, rationale, known_entities])

    else:
        print(error_message)

    if len(ezBIDS_telemetry_info_list) > 1:
        header = ezBIDS_telemetry_info_list[0]
        rows = ezBIDS_telemetry_info_list[1:]
        ezBIDS_telemetry_info_json = []
        for row in rows:
            ezBIDS_telemetry_info_json.append(dict(zip(header, row)))

        with open(output_file, "w") as fp:
            json.dump(ezBIDS_telemetry_info_json, fp, indent=3)


# Execute functionality
for dtype in ['core', 'finalized']:
    ezBIDS_telemetry_info_list = [['idx', 'seq_file_name', 'data_type', 'suffix', 'rationale', 'known_entities']]
    gather_telemetry(dtype)
