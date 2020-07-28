#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 26 08:37:56 2020

@author: dlevitas
"""

import os, sys, re, json, warnings

import matplotlib
matplotlib.use('Agg')


import pandas as pd
import numpy as np
import nibabel as nib
from io import StringIO
from nilearn.image import load_img, index_img
from nilearn.plotting import plot_img


warnings.filterwarnings("ignore")

#data_dir = '/media/data/ezbids/siemens/20190520.Dan_STD_1025.9986@thwjames_DanSTD'
#data_dir = '/media/data/ezbids/ge/20180918GE'
#data_dir = '/media/data/ezbids/siemens/DAN_STD'
#data_dir = '/media/data/ezbids/dicoms/umass-philips'
#data_dir = '/media/data/ezbids/dicoms/rosetta/philips/philips_1_5T_intera'
#data_dir = '/media/data/ezbids/dicoms/rosetta/General_electric/GE-SignaHD-Excite'
data_dir = '/media/data/ezbids/dicoms/Avesani'
#data_dir = sys.argv[1]
os.chdir(data_dir)

#def extractor():
    
#Load list generated from UI, and organize the nifti/json files by their series number    
dir_list = pd.read_csv('list', header=None)
dir_list.columns = ['path']
sn_list = []
new_sn_list = []
for d in range(len(dir_list)):
    
    try:
        sn = dir_list['path'][d].split('sn-')[1].split('.')[0]
        sn_list.append(sn)
    except:
        sn = dir_list['path'][d].split('sn-')[-1].split('_')[0]
        sn_list.append(sn)
        
    if int(re.match(r"([0-9]+)",sn).group()) < 10:
        new_sn = '0' + sn
    else:
        new_sn = sn
        
    new_sn_list.append(new_sn)
    
dir_list['sn'] = pd.Series(sn_list, index=dir_list.index)
dir_list['new_sn'] = pd.Series(new_sn_list, index=dir_list.index)
dir_list.sort_values(by='new_sn', inplace=True, ignore_index=True)
    

#Get nifti, json (i.e. sidecar), and SeriesNumber (SN) file lists
json_list = [x for x in dir_list['path'] if '.json' in x and 'ezbids' not in x]
nifti_list = [x for x in dir_list['path'] if '.nii.gz' in x or '.bval' in x or '.bvec' in x]    
SNs_list = [dir_list['sn'][x] for x in range(len(dir_list['sn'])) if '.json' in dir_list['path'][x]]

#participantsColumn portion of ezBIDS.json
participantsColumn = {"sex": {"LongName": "gender", "Description": "generic gender field", "Levels": {"M": "male", "F": "female"}},
                      "age": {"LongName": "age", "Units": "years"}}

#Create list for later
data_list = []

#Parse through nifti and sidecar data for pertinent information
for j in range(len(json_list)):
    #Load sidecar data
    json_data = open(json_list[j])
    json_data = json.load(json_data, strict=False)
    
    #Select SeriesNumbers
    SN = SNs_list[j]
    
    #Specify direction based on PhaseEncodingDirection (PED)
    #May not be as straight forward, see: https://github.com/rordenlab/dcm2niix/issues/412
    try:
        phase_encoding_direction = json_data['PhaseEncodingDirection']
        if phase_encoding_direction == 'j-':
            PED = 'AP'
        elif phase_encoding_direction == 'j':
            PED = 'PA'
        elif phase_encoding_direction == 'i-':
            PED = 'RL'
        elif phase_encoding_direction == 'i':
            PED = 'LR'
        else:
            PED = ''
    except:
        PED = ''
        
    #Nifti (and bval/bvec) file(s) associated with specific sidecar
    nifti_paths_for_json = [x for x in nifti_list if 'sn-{}.'.format(SN) in x or 'sn-{}_'.format(SN) in x]
    
    #Nifti file size
    filesize = os.stat(nifti_paths_for_json[0]).st_size
    
    #Find StudyID from sidecar
    try:
        studyID = json_data['StudyID']
    except:
        studyID = ''
    
    #Find subjID from sidecar (some sidecars have neither PatientName nor PatientID)
    try:
        subjID = json_data['PatientName']
    except:
        #subjID = json_data['PatientID']
        subjID = ''
        
    #Find how many volumes are in sidecar's corresponding nifti file
    try:
        volume_count = nib.load(json_list[j][:-4] + 'nii.gz').shape[3]
    except:
        volume_count = 1
        
    #Relative paths of sidecar and nifti per SeriesNumber
    paths = nifti_paths_for_json + [json_list[j]]
    
    #File extensions for nifti and sidecar
    nifti_name, json_name = ['nii.gz', 'json']
        
    
    mapping_dic = {'StudyID': studyID, 
           'PatientID': subjID, 
           'SessionID': '',
           'SeriesNumber': json_data['SeriesNumber'],
           'PatientSex': json_data['PatientSex'],
           'AcquisitionDate': json_data['AcquisitionDateTime'].split('T')[0],
           'AcquisitionTime': json_data['AcquisitionDateTime'].split('T')[-1],
           'SeriesDescription': json_data['SeriesDescription'],
           'ProtocolName': json_data['ProtocolName'], 
           'ImageType': json_data['ImageType'],
           'SeriesNumber': json_data['SeriesNumber'],
           'RepetitionTime': json_data['RepetitionTime'],
           'DataType': '',
           'ModalityLabel': '',
           'sbref_run': '',
           'func_run': '',
           'dwi_run': '',
           'fmap_run': '',
           'dir': PED,
           'TaskName': 'rest',
           "include": True,
           'filesize': filesize,
           "VolumeCount": volume_count,
           'error': 'N/A',
           'qc': '',
           'nifti_path': [x for x in nifti_paths_for_json if '.nii.gz' in x][0],
           'json_path': json_list[j],
           'paths': paths,
           'pngPath': '',
           'nifti_name': nifti_name,
           'json_name': json_name,
           'headers': '',
           'sidecar':json_data,
           'second_check': ''
           }
    data_list.append(mapping_dic)
    
    subjectIDs = list(set([x['PatientID'] for x in data_list]))
    for s in range(len(subjectIDs)):
        subjectIDs[s] = {'PatientID': subjectIDs[s], 'sub': None, 'phenotype': {} }
        
    acquisition_dates = list(set([x['AcquisitionDate'] for x in data_list]))
    for a in range(len(acquisition_dates)):
        acquisition_dates[s] = {'AcquisitionDate': acquisition_dates[s], 'ses': ''}
    
#Only keep dictionary with unique SeriesDescription values
data_list_unique_SD = []
series_description_list = []
series_number_list = []
for SD in data_list:
    if SD['SeriesDescription'] not in series_description_list or SD['SeriesNumber'] not in series_number_list:
        data_list_unique_SD.append(SD)
        series_description_list.append(SD['SeriesDescription'])
        series_number_list.append(SD['SeriesNumber'])

#Set up variables for determining features needed for BIDS conversion
sbref_run = 1
func_run = 1
dwi_run = 1
participants_list = []
series_list = []
objects_list = []


#if any(x in descriptions[d] for x in ['T1w','tfl3d','mprage','tfl_1084B']):
#Let's try to auto-populate some of the BIDS fields
for i in range(len(data_list_unique_SD)):
    
    s = StringIO()
    sys.stdout = s
    print(nib.load(data_list_unique_SD[i]['nifti_path']).header)
    data_list_unique_SD[i]['headers'] = s.getvalue().splitlines()[1:]
    
    # data_list_unique_SD[i]['headers'] = ''
    
    img = load_img(data_list_unique_SD[i]['nifti_path'])
    
    if not os.path.isfile('{}.png'.format(data_list_unique_SD[i]['nifti_path'][:-7])):
        # img = load_img(data_list_unique_SD[i]['nifti_path'])
        if img.ndim == 4:
            ref_img = index_img(img, -1)
        else:
            ref_img = img
        plot_img(ref_img, colorbar=False, display_mode='ortho', 
                  draw_cross=False, annotate=False, threshold=None, 
                  output_file='{}.png'.format(data_list_unique_SD[i]['nifti_path'][:-7]))
            
        
    participants_info = {data_list_unique_SD[i]['PatientID']:
                         {"session": '',
                          "age": '',
                          "sex": data_list_unique_SD[i]['PatientSex']
                          }
                         }
    participants_list.append(participants_info)
    
    
    SD = data_list_unique_SD[i]['SeriesDescription']
    TR = data_list_unique_SD[i]['RepetitionTime']
    
    #Populate some labels fields (primarily based on ReproIn convention)
    entities = {}
    if 'sub-' in SD:
        entities['sub'] = SD.split('sub-')[-1].split('_')[0]
    else:
        entities['sub'] = data_list_unique_SD[i]['PatientID']
    
    if '_ses-' in SD:
        entities['ses'] = SD.split('_ses-')[-1].split('_')[0]
    else:
        entities['ses'] = data_list_unique_SD[i]['SessionID']
        
    if '_run-' in SD:
        entities['run'] = SD.split('_run-')[-1].split('_')[0]
    else:
        entities['run'] = ''
    
    if '_acq-' in SD:
        entities['acq'] = SD.split('_acq-')[-1].split('_')[0]
    else:
        entities['acq'] = ''
        
    if '_ce-' in SD:
        entities['ce'] = SD.split('_ce-')[-1].split('_')[0]
    else:
        entities['ce'] = ''
        
    
    try:
        SequenceName = data_list_unique_SD[i]['sidecar']['SequenceName']
    except:
        SequenceName = ''
        
    try:
        EchoTime = data_list_unique_SD[i]['sidecar']['EchoTime']*1000
    except:
        EchoTime = 0
    
    
    fmap_intendedFor = []
    
    
    #Check for localizer(s)
    if any(x in SD for x in ['Localizer','localizer','SCOUT','Scout','scout']):
        data_list_unique_SD[i]['include'] = False
        data_list_unique_SD[i]['error'] = 'Acquisition appears to be a localizer; will not be converted to BIDS'
        data_list_unique_SD[i]['second_check'] = 'no'
    
    #Check for T1w anatomical
    elif any(x in SD for x in ['T1W','T1w','t1w','tfl3d','mprage','MPRAGE']) or 'tfl3d1_16ns' in SequenceName or (EchoTime <= 10 and EchoTime > 0):
        if 'NORM' in data_list_unique_SD[i]['ImageType'] and 'tfl3d1_16ns' in SequenceName:
            data_list_unique_SD[i]['DataType'] = 'anat'
            data_list_unique_SD[i]['ModalityLabel'] = 'T1w'
        elif 'NORM' not in data_list_unique_SD[i]['ImageType'] and 'tfl3d1_16ns' in SequenceName:
            data_list_unique_SD[i]['include'] = False  
            data_list_unique_SD[i]['error'] = 'Acquisition is a poor resolution T1w; recommended not be converted to BIDS'
            data_list_unique_SD[i]['second_check'] = 'no'
        else:
            data_list_unique_SD[i]['DataType'] = 'anat'
            data_list_unique_SD[i]['ModalityLabel'] = 'T1w'
          
    #Check for T2w anatomical
    elif any(x in SD for x in ['T2W','T2w','t2w']) or (EchoTime > 100):
        data_list_unique_SD[i]['DataType'] = 'anat'
        data_list_unique_SD[i]['ModalityLabel'] = 'T2w'
        
    #Check for FLAIR anatomical
    elif any(x in SD for x in ['FLAIR','Flair','flair','t2_space_da-fl']):
        data_list_unique_SD[i]['DataType'] = 'anat'
        data_list_unique_SD[i]['ModalityLabel'] = 'FLAIR'
        
    #Check for single-band reference (SBRef)
    elif any(x in SD for x in ['SBRef','sbref']):
        data_list_unique_SD[i]['DataType'] = 'func'
        data_list_unique_SD[i]['ModalityLabel'] = 'sbref'
        if entities['run'] == '':
            if sbref_run < 10:
                entities['run'] = '0' + str(sbref_run)
            else:
                entities['run'] = str(sbref_run)
        sbref_run +=1
        if '_task-' in SD:
            data_list_unique_SD[i]['TaskName'] = SD.split('_task-')[-1].split('_')[0]
            data_list_unique_SD[i]['sidecar']['TaskName'] = SD.split('_task-')[-1].split('_')[0]
            entities['task'] = SD.split('_task-')[-1].split('_')[0]
        else:
            entities['task'] = 'rest'
            
    #Check for functional
    elif any(x in SD for x in ['BOLD','Bold','bold','FUNC','Func','func','FMRI','fMRI','fmri','EPI']) and ('SBRef' not in SD or 'sbref' not in SD) or (img.ndim == 4 and TR < 5) :
        data_list_unique_SD[i]['DataType'] = 'func'
        data_list_unique_SD[i]['ModalityLabel'] = 'bold'
        if entities['run'] == '':
            if func_run < 10:
                entities['run'] = '0' + str(func_run)
            else:
                entities['run'] = str(func_run)
        func_run +=1
        if '_task-' in SD:
            data_list_unique_SD[i]['TaskName'] = SD.split('_task-')[-1].split('_')[0]
            data_list_unique_SD[i]['sidecar']['TaskName'] = SD.split('_task-')[-1].split('_')[0]
            entities['task'] = SD.split('_task-')[-1].split('_')[0]
        else:
            entities['task'] = 'rest'
    
    #Check for DWI
    elif any(x in SD for x in ['DWI','dwi','DTI','dti']) or 'ep_b' in SequenceName:
        data_list_unique_SD[i]['DataType'] = 'dwi'
        data_list_unique_SD[i]['ModalityLabel'] = 'dwi'
        if entities['run'] == '':
            if dwi_run < 10:
                entities['run'] = '0' + str(dwi_run)
            else:
                entities['run'] = str(dwi_run)
        dwi_run +=1
        entities['dir'] = data_list_unique_SD[i]['dir']
    
    #Check for field maps
    elif any(x in SD for x in ['fmap','FieldMap','field_mapping']) or 'epse2d' in SequenceName:
        data_list_unique_SD[i]['DataType'] = 'fmap'
        data_list_unique_SD[i]['ModalityLabel'] = 'epi'
        entities['run'] = str(data_list_unique_SD[i]['dwi_run'])
        entities['dir'] = data_list_unique_SD[i]['dir']
    
    #Can't determine acquisition type. Assume it's not BIDS
    else:
        data_list_unique_SD[i]['include'] = False
        data_list_unique_SD[i]['error'] = 'Cannot determine acquisition type'
        data_list_unique_SD[i]['second_check'] = 'yes'
        
        
    
    if data_list_unique_SD[i]['ModalityLabel'] == 'dwi':
        run =str( data_list_unique_SD[i]['dwi_run'])
    elif data_list_unique_SD[i]['ModalityLabel'] == 'bold':
        run = str(data_list_unique_SD[i]['func_run'])
    else:
        run = ''
        
    if data_list_unique_SD[i]['DataType'] == '' and data_list_unique_SD[i]['ModalityLabel'] == '':
        br_type = ''
    else:
        br_type = data_list_unique_SD[i]['DataType'] + '/' + data_list_unique_SD[i]['ModalityLabel']
        
    series_info = {"include": data_list_unique_SD[i]['include'],
                   "SeriesDescription": SD,
                   "SeriesNumber": data_list_unique_SD[i]['SeriesNumber'],
                   "entities": entities,
                   "type": br_type
                   }
    series_list.append(series_info)
    
    
    objects_info = {"include": data_list_unique_SD[i]['include'],
                   "SeriesDescription": SD,
                   "SeriesNumber": data_list_unique_SD[i]['SeriesNumber'],
                   "PatientID": data_list_unique_SD[i]['PatientID'],
                   "AcquisitionDate": data_list_unique_SD[i]['AcquisitionDate'],
                   "pngPath": '{}.png'.format(data_list_unique_SD[i]['nifti_path'][:-7]),
                   "entities": entities,
                   "type": br_type,
                   "items": [
                           {
                               "path": data_list_unique_SD[i]['nifti_path'],
                               "name": data_list_unique_SD[i]['nifti_name'],
                               "headers": data_list_unique_SD[i]['headers']
                            },
                           {
                               "path": data_list_unique_SD[i]['json_path'],
                               "name": data_list_unique_SD[i]['json_name'],
                               "sidecar": data_list_unique_SD[i]['sidecar']
                            }
                        ],
                   "analysisResults": {
                       "VolumeCount": data_list_unique_SD[i]['VolumeCount'],
                       "messages": [
                           ""
                        ],
                       "errors": data_list_unique_SD[i]['error'],
                       "qc": data_list_unique_SD[i]['qc'],
                       "filesize": data_list_unique_SD[i]['filesize']
                    },
                   "paths": data_list_unique_SD[i]['paths']
                  }
    objects_list.append(objects_info)

    
    ezBIDS = {"subjects": subjectIDs,
              "sessions": acquisition_dates,
              "participantsColumn": participantsColumn,
              "series": series_list,
              "objects": objects_list
              }

    ezBIDS_file_name = 'ezBIDS.json'
    with open(ezBIDS_file_name, 'w') as fp: 
        json.dump(ezBIDS, fp, indent=3) 
            
    
    #return dir_list, json_list, data_list, data_list_unique_SD

#dir_list, json_list, data_list, data_list_unique_SD = extractor()
    
    
    
    

