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

data_dir = sys.argv[1]
os.chdir(data_dir)

#def extractor():
    
#Load list generated from UI, and organize the nifti/json files by their series number    
dir_list = pd.read_csv('list', header=None)
dir_list.columns = ['path']
#Remove Philips proprietary files in dir_list if they exist
dir_list = dir_list[~dir_list.path.str.contains('PARREC|Parrec|parrec')].reset_index(drop=True)
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
    if 'PatientName' in json_data:
        PatientName = json_data['PatientName']
    else:
        PatientName = None
        
    if 'PatientID' in json_data:
        PatientID = json_data['PatientID']
    else:
        PatientID = None
        
    #Find PatientBirthDate
    if 'PatientBirthDate' in json_data:
        PatientBirthDate = json_data['PatientBirthDate'].replace('-','')
    else:
        PatientBirthDate = None
    
    #Find PatientName
    if PatientName:
        sub = PatientName
    elif PatientID:
        sub = PatientID
    else:
        sub = PatientBirthDate
    
    #Find PatientSex
    try: 
        PatientSex = json_data['PatientSex']
    except:
        PatientSex = None
    
    #Find Acquisition Date & Time
    if 'AcquisitionDateTime' in json_data:
        AcquisitionDate = json_data['AcquisitionDateTime'].split('T')[0]
        AcquisitionTime = json_data['AcquisitionDateTime'].split('T')[-1]
    else:
        AcquisitionDate = None
        AcquisitionTime = None
    
    #Find EchoNumber
    if 'EchoNumber' in json_data:
        EchoNumber = json_data['EchoNumber']
    else:
        EchoNumber = None
        
    #Find InversionTime
    if 'InversionTime' in json_data:
        InversionTime = json_data['InversionTime']
    else:
        InversionTime = None
        
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
                   'PatientName': PatientName,
                   'PatientID': PatientID,
                   'PatientBirthDate': PatientBirthDate,
                   'sub': sub,
                   'SessionID': '',
                   'SeriesNumber': json_data['SeriesNumber'],
                   'PatientSex': PatientSex,
                   'AcquisitionDate': AcquisitionDate,
                   'AcquisitionTime': AcquisitionTime,
                   'SeriesDescription': json_data['SeriesDescription'],
                   'ProtocolName': json_data['ProtocolName'], 
                   'ImageType': json_data['ImageType'],
                   'SeriesNumber': json_data['SeriesNumber'],
                   'RepetitionTime': json_data['RepetitionTime'],
                   'EchoNumber': EchoNumber,
                   'InversionTime': InversionTime,
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
    
    subjectIDs = list(set([x['sub'] for x in data_list]))
    
    for s in range(len(subjectIDs)):
        subjectIDs[s] = {'PatientID': data_list[s]['PatientID'], 'PatientName': data_list[s]['PatientName'],
                         'PatientBirthDate': data_list[s]['PatientBirthDate'], 'sub': subjectIDs[s], 
                         'phenotype': {} }
        
    acquisition_dates = list(set([x['AcquisitionDate'] for x in data_list]))
    for a in range(len(acquisition_dates)):
        acquisition_dates[a] = {'AcquisitionDate': acquisition_dates[a], 'ses': ''}
    
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
fmap_run = 1
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
        if img.ndim == 4:
            ref_img = index_img(img, -1)
        else:
            ref_img = img
        plot_img(ref_img, colorbar=False, display_mode='ortho', 
                  draw_cross=False, annotate=False, threshold=None, 
                  output_file='{}.png'.format(data_list_unique_SD[i]['nifti_path'][:-7]))    
    
    SD = data_list_unique_SD[i]['SeriesDescription']
    TR = data_list_unique_SD[i]['RepetitionTime']
    
    #Populate some labels fields (primarily based on ReproIn convention)
    entities = {}
    if 'sub-' in SD:
        data_list_unique_SD[i]['sub'] = SD.split('sub-')[-1].split('_')[0]
    else:
        entities['sub'] = None
    
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
    
    #Do a first pass of acqusitions based on specific terms in the SeriesDescriptions
    #Check for localizer(s)
    if any(x in SD for x in ['Localizer','localizer','SCOUT','Scout','scout']):
        data_list_unique_SD[i]['include'] = False
        data_list_unique_SD[i]['error'] = 'Acquisition appears to be a localizer; will not be converted to BIDS'
        data_list_unique_SD[i]['second_check'] = 'no'
    
    #Check for T1w anatomical
    #elif any(x in SD for x in ['T1W','T1w','t1w','tfl3d','mprage','MPRAGE']) or 'tfl3d1_16ns' in SequenceName or (EchoTime <= 10 and EchoTime > 0):
    elif any(x in SD for x in ['T1W','T1w','t1w','tfl3d','mprage','MPRAGE']) or 'tfl3d1_16ns' in SequenceName:
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
    elif any(x in SD for x in ['T2W','T2w','t2w']):
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
    elif any(x in SD for x in ['BOLD','Bold','bold','FUNC','Func','func','FMRI','fMRI','fmri','EPI']) and ('SBRef' not in SD or 'sbref' not in SD):
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
    elif any(x in SD for x in ['fmap','FieldMap','field_mapping']) or 'epse2d' in SequenceName or 'fm2d2r' in SequenceName:
        if img.ndim == 4: #SE fmaps
            data_list_unique_SD[i]['DataType'] = 'fmap'
            data_list_unique_SD[i]['ModalityLabel'] = 'epi'
            entities['run'] = str(data_list_unique_SD[i]['fmap_run'])
            entities['dir'] = data_list_unique_SD[i]['dir']
        else: #magnitude/phasediff fmaps
            data_list_unique_SD[i]['DataType'] = 'fmap'
            if data_list_unique_SD[i]['EchoNumber'] == 1:
                data_list_unique_SD[i]['ModalityLabel'] = 'magnitude1'
            else:
                data_list_unique_SD[i]['ModalityLabel'] = 'phasediff'
            entities['run'] = str(data_list_unique_SD[i]['fmap_run'])
            
            
    #Can't determine acquisition type. Assume it's not BIDS
    else:
        data_list_unique_SD[i]['include'] = False
        data_list_unique_SD[i]['error'] = 'Cannot determine acquisition type'
        data_list_unique_SD[i]['second_check'] = 'yes'
        
    
    #Do a second pass, but using values from other fields, such as TR, TE, TI, etc
    if data_list_unique_SD[i]['second_check'] == 'yes':
        if img.ndim == 4: #DWI, functional, functional phase, and SE fmap are 4D
            if TR > 3: #Probably DWI
                data_list_unique_SD[i]['include'] = True
                data_list_unique_SD[i]['DataType'] = 'dwi'
                data_list_unique_SD[i]['ModalityLabel'] = 'dwi'
                data_list_unique_SD[i]['error'] = 'N/A'
                if entities['run'] == '':
                    if dwi_run < 10:
                        entities['run'] = '0' + str(dwi_run)
                    else:
                        entities['run'] = str(dwi_run)
                dwi_run +=1
                entities['dir'] = data_list_unique_SD[i]['dir']
            else: #Probably functional
                if data_list_unique_SD[i]['VolumeCount'] < 20: #Functional runs with less than 20 volumes probably aren't good
                    data_list_unique_SD[i]['error'] = 'Functional contains very few volumes; not complete?'
                else:
                    data_list_unique_SD[i]['include'] = True
                    data_list_unique_SD[i]['DataType'] = 'func'
                    data_list_unique_SD[i]['ModalityLabel'] = 'bold'
                    data_list_unique_SD[i]['error'] = 'N/A'
                    if entities['run'] == '':
                        if func_run < 10:
                            entities['run'] = '0' + str(func_run)
                        else:
                            entities['run'] = str(func_run)
                    func_run +=1
                    entities['task'] = 'rest'
                    
        elif img.ndim == 3: #sbref, T1w, T2w, FLAIR, magnitude/phasediff fmap are 3D
            if 'EchoNumber' in data_list_unique_SD[i]: #Probably magnitude/phasediff
                data_list_unique_SD[i]['include'] = True
                data_list_unique_SD[i]['DataType'] = 'fmap'
                if data_list_unique_SD[i]['EchoNumber'] == 1:
                    data_list_unique_SD[i]['ModalityLabel'] = 'magnitude1'
                else:
                    data_list_unique_SD[i]['ModalityLabel'] = 'phasediff'
                data_list_unique_SD[i]['error'] = 'N/A'
                entities['run'] = str(data_list_unique_SD[i]['fmap_run'])
                
            if (EchoTime <= 10 and EchoTime > 0): #Probably T1w
                data_list_unique_SD[i]['include'] = True
                data_list_unique_SD[i]['DataType'] = 'anat'
                data_list_unique_SD[i]['ModalityLabel'] = 'T1w'
                data_list_unique_SD[i]['error'] = 'N/A'
            
            elif data_list_unique_SD[i]['InversionTime'] is not None and data_list_unique_SD[i]['InversionTime'] > 0: #Probably FLAIR
                data_list_unique_SD[i]['include'] = True
                data_list_unique_SD[i]['DataType'] = 'anat'
                data_list_unique_SD[i]['ModalityLabel'] = 'FLAIR'
                data_list_unique_SD[i]['error'] = 'N/A'
                
            elif EchoTime > 100: #Probably T2w
                data_list_unique_SD[i]['include'] = True
                data_list_unique_SD[i]['DataType'] = 'anat'
                data_list_unique_SD[i]['ModalityLabel'] = 'T2w'
                data_list_unique_SD[i]['error'] = 'N/A'
            
            elif (EchoTime > 10 and EchoTime < 100): #Probably sbref
                data_list_unique_SD[i]['include'] = True
                data_list_unique_SD[i]['DataType'] = 'func'
                data_list_unique_SD[i]['ModalityLabel'] = 'sbref'
                data_list_unique_SD[i]['error'] = 'N/A'
                if entities['run'] == '':
                    if sbref_run < 10:
                        entities['run'] = '0' + str(sbref_run)
                    else:
                        entities['run'] = str(sbref_run)
                sbref_run +=1
                entities['task'] = 'rest'
            else:
                pass
                
                
            
 
    
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
                   "PatientName": data_list_unique_SD[i]['PatientName'],
                   "PatientID": data_list_unique_SD[i]['PatientID'],
                   "PatientBirthDate": data_list_unique_SD[i]['PatientBirthDate'],
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
    
    
    
    

