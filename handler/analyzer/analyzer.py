#!/usr/bin/env python3
"""
Created on Fri Jun 26 08:37:56 2020

@author: dlevitas
"""
from __future__ import division
import os, sys, re, json, warnings
import pandas as pd
import numpy as np
import nibabel as nib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from operator import itemgetter
from math import floor

warnings.filterwarnings("ignore")
os.environ[ 'MPLCONFIGDIR' ] = '/tmp/'

######## Functions ########
def select_unique_data(dir_list):
    '''
    Takes list of nifti, json, and bval/bvec files generated frm dcm2niix to find the 
        unique data within the entire list. The contents of the list can be data
        from an entire dataset, a single subject, etc

    Parameters
    ----------
    dir_list : pd.DataFrame()
        List of nifti, json, and bval/bvec files generated from dcm2niix

    Returns
    -------
    data_list_unique_series: list
        List of dictionaries containing pertinent and unique information about the
            data, primarily coming from the metadata in the json files
            
    subjectIDs_info: list
        List of dictionaries containing subject identification info, such as
        PatientID, PatientName, PatientBirthDatge
    
    acquisition_dates: list    
        List of dictionaries containing the AcquisitionDate and sessions # (if applicable)
    '''
    
    #Load list generated from dcm2niix, and organize the nifti/json files by their SeriesNumber   
    dir_list.columns = ['path']
    
    #Remove Philips proprietary files in dir_list if they exist
    dir_list = dir_list[~dir_list.path.str.contains('PARREC|Parrec|parrec')].reset_index(drop=True)    
    
    #Get separate nifti and json (i.e. sidecar) lists
    json_list = [x for x in dir_list['path'] if '.json' in x and 'ezbids' not in x]
    nifti_list = [x for x in dir_list['path'] if '.nii.gz' in x or '.bval' in x or '.bvec' in x]
        
    #Create list for appending dictionaries to
    data_list = []
    
    #Parse through nifti and json data for pertinent information
    print('Determining unique acquisitions in list')
    print('------------------------------------------')
    for j in range(len(json_list)):
        json_data = open(json_list[j])
        json_data = json.load(json_data, strict=False)
        
        #Select SeriesNumbers
        SN = json_data['SeriesNumber']
            
        #Specify direction based on PhaseEncodingDirection (PED)
        #May not be as straight forward, see: https://github.com/rordenlab/dcm2niix/issues/412
        try:
            phase_encoding_direction = json_data['PhaseEncodingDirection']
            if phase_encoding_direction == 'j-':
                PED = 'AP'
            elif phase_encoding_direction == 'j':
                PED = 'PA'
            elif phase_encoding_direction == 'i':
                PED = 'RL'
            elif phase_encoding_direction == 'i-':
                PED = 'LR'
            else:
                PED = ''
        except:
            PED = ''
        
            
        #Nifti (and bval/bvec) file(s) associated with specific json file
        nifti_paths_for_json = [x for x in nifti_list if json_list[j][:-4] in x]
        nifti_paths_for_json = [x for x in nifti_paths_for_json if '.json' not in x]
            
        #Find nifti file size
        filesize = os.stat(nifti_paths_for_json[0]).st_size
        
        #Find StudyID from json
        if 'StudyID' in json_data:
            studyID = json_data['StudyID']
        else:
            studyID = ''
        
        #Find subjectID from json (some files contain neither PatientName nor PatientID)
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
            
        #Find PatientSex
        if 'PatientSex' in json_data:
            PatientSex = json_data['PatientSex']
            if PatientSex not in ['M','F']:
                PatientSex = 'N/A'
        else:
            PatientSex = 'N/A'
        
        #Select subjectID to display to ezBIDS users
        #Order of importance is: PatientName > PatientID > PatientBirthDate
        if PatientName:
            subject = PatientName
        elif PatientID:
            subject = PatientID
        else:
            subject = PatientBirthDate
        subject = re.sub('[^A-Za-z0-9]+', '', subject)
        
        #Find Acquisition Date & Time
        if 'AcquisitionDateTime' in json_data:
            AcquisitionDate = json_data['AcquisitionDateTime'].split('T')[0]
            AcquisitionTime = json_data['AcquisitionDateTime'].split('T')[-1]
        else:
            AcquisitionDate = '0000-00-00'
            AcquisitionTime = None
            
        #Find RepetitionTime
        if 'RepetitionTime' in json_data:
            RepetitionTime = json_data['RepetitionTime']
        else:
            RepetitionTime = 'N/A'
        
        #Find EchoNumber
        if 'EchoNumber' in json_data:
            EchoNumber = json_data['EchoNumber']
        else:
            EchoNumber = None
        
        #Find EchoTime
        if 'EchoTime' in json_data:
            EchoTime = json_data['EchoTime']*1000
        else:
            EchoTime = 0
            
        #Find InversionTime
        if 'InversionTime' in json_data:
            InversionTime = json_data['InversionTime']
        else:
            InversionTime = None
        
        #Find MultibandAccerationFactor
        if 'MultibandAccelerationFactor' in json_data:
            MultibandAccelerationFactor = json_data['MultibandAccelerationFactor']
        else:
            MultibandAccelerationFactor = 'N/A'
            
        #Find how many volumes are in jsons's corresponding nifti file
        try:
            volume_count = nib.load(json_list[j][:-4] + 'nii.gz').shape[3]
        except:
            volume_count = 1
           
        #Relative paths of json and nifti files (per SeriesNumber)
        paths = sorted(nifti_paths_for_json + [json_list[j]])
            
        #Organize all from individual SeriesNumber in dictionary
        mapping_dic = {'StudyID': studyID,
                       'PatientName': PatientName,
                       'PatientID': PatientID,
                       'PatientBirthDate': PatientBirthDate,
                       'PatientSex': PatientSex,
                       'PatientAge': 'N/A',
                       'subject': subject,
                       'sessions': '',
                       'SeriesNumber': json_data['SeriesNumber'],
                       'AcquisitionDate': AcquisitionDate,
                       'AcquisitionTime': AcquisitionTime,
                       'SeriesDescription': json_data['SeriesDescription'],
                       'ProtocolName': json_data['ProtocolName'], 
                       'ImageType': json_data['ImageType'],
                       'SeriesNumber': json_data['SeriesNumber'],
                       'RepetitionTime': RepetitionTime,
                       'EchoNumber': EchoNumber,
                       'EchoTime': EchoTime,
                       'InversionTime': InversionTime,
                       'MultibandAccelerationFactor': MultibandAccelerationFactor,
                       'DataType': '',
                       'ModalityLabel': '',
                       'series_id': 0,
                       'direction': PED,
                       'IntendedFor': [],
                       'TaskName': '',
                       "include": True,
                       'filesize': filesize,
                       "NumVolumes": volume_count,
                       'error': None,
                       'section_ID': 1,
                       'message': '',
                       'protocol_index': 0,
                       'br_type': '',
                       'nifti_path': [x for x in nifti_paths_for_json if '.nii.gz' in x][0],
                       'json_path': json_list[j],
                       'paths': paths,
                       'pngPath': '',
                       'headers': '',
                       'sidecar':json_data
                       }
        data_list.append(mapping_dic)
        
    #Curate subjectID and acquisition date info to display in UI
    subjectIDs_info = list({x['subject']:{'subject':x['subject'], 'PatientID':x['PatientID'], 'PatientName':x['PatientName'], 'PatientBirthDate':x['PatientBirthDate'], 'phenotype':{'sex':x['PatientSex'], 'age':x['PatientAge']}, 'exclude': False, 'sessions': []} for x in data_list}.values())

                 
    subjectIDs_info = sorted(subjectIDs_info, key = lambda i: i['subject'])
    
    acquisition_dates = list({(x['subject'], x['AcquisitionDate']):{'subject':x['subject'], 'AcquisitionDate':x['AcquisitionDate'], 'sessions': ''} for x in data_list}.values())
    acquisition_dates = sorted(acquisition_dates, key = lambda i: i['AcquisitionDate'])
    
    #Insert sessionss info if applicable
    subject_sessions = [[x['subject'], x['AcquisitionDate'], x['sessions']] for x in data_list]
    subject_sessions = sorted([list(x) for x in set(tuple(x) for x in subject_sessions)], key = lambda i: i[1])
    
    for i in np.unique(np.array([x[0] for x in subject_sessions])):
        subject_indices = [x for x,y in enumerate(subject_sessions) if y[0] == i]
        if len(subject_indices) > 1:
            for j, k in enumerate(subject_indices):
                subject_sessions[k][-1] = str(j+1)
    
    subject_sessions = sorted([list(x) for x in set(tuple(x) for x in subject_sessions)], key = lambda i: i[1])
    
    for x,y in enumerate(acquisition_dates):
        y['sessions'] = subject_sessions[x][-1]
        
    
    for si in range(len(subjectIDs_info)):
        for ss in subject_sessions:
            if ss[0] == subjectIDs_info[si]['subject']:
                subjectIDs_info[si]['sessions'].append({'AcquisitionDate': ss[1], 'sessions': ss[2], 'exclude': False})
        subjectIDs_info[si].update({'validationErrors': []})
        

        
    #Sort list of dictionaries by subject, AcquisitionDate, SeriesNumber, and json_path
    data_list = sorted(data_list, key=itemgetter('subject', 'AcquisitionDate', 'SeriesNumber', 'json_path'))
    
    #Add sessions info to data_list, if applicable
    for i in range(len(acquisition_dates)):
        for j in range(len(data_list)):
            if data_list[j]['subject'] == acquisition_dates[i]['subject'] and data_list[j]['AcquisitionDate'] == acquisition_dates[i]['AcquisitionDate']:
                data_list[j]['sessions'] = acquisition_dates[i]['sessions']
        
    #Unique data is determined from four values: SeriesDescription, EchoTime, ImageType, MultibandAccelerationFactor
    data_list_unique_series = []
    series_tuples = []
    series_id = 0      
    
    for x in range(len(data_list)):  
        tup = (data_list[x]['SeriesDescription'], data_list[x]['EchoTime'], data_list[x]['ImageType'], data_list[x]['MultibandAccelerationFactor'], series_id)
        if tup[:-1] not in [y[:-1] for y in series_tuples]: 
            data_list[x]['series_id'] = series_id
            series_id += 1
            data_list_unique_series.append(data_list[x])
        else:
            data_list[x]['series_id'] = series_tuples[[y[:-1] for y in series_tuples].index(tup[:-1])][-1]
                
        series_tuples.append(tup)
        
    return data_list, data_list_unique_series, subjectIDs_info, acquisition_dates
    

def identify_series_info(data_list_unique_series):
    '''
    Takes list of dictionaries with key and unique information, and uses it to 
        determine the DataType and Modality labels of the unique acquisitions. 
        Other information (e.g. run, acq, ce) will be determined if the data 
        follows the ReproIn naming convention for SeriesDescriptions.

    Parameters
    ----------
    data_list_unique_series : list
        List of dictionaries continaing key information about the data

    Returns
    -------
    series_list: list
        List of dictionaries containing pertinent about the unique acquisitions.
        This information is displayed to the user through the UI, which grabs 
        this information.
    '''
    
    
    #Determine DataType and ModalityLabel of series list acquisitions
    series_list = []
    for i in range(len(data_list_unique_series)):
        
        series_entities = {}
        SD = data_list_unique_series[i]['SeriesDescription']
        EchoTime = data_list_unique_series[i]['EchoTime']
        TR = data_list_unique_series[i]['RepetitionTime']
        mp2rage_inv = 1
        if 'SequenceName' in data_list_unique_series[i]['sidecar']:
            SequenceName = data_list_unique_series[i]['sidecar']['SequenceName']
        elif 'ScanningSequence' in data_list_unique_series[i]['sidecar']:
            SequenceName = data_list_unique_series[i]['sidecar']['ScanningSequence']
        else:
            SequenceName = 'N/A'
        
        #Populate some labels fields (based on ReproIn convention)
        if 'sub-' in SD:
            series_entities['subject'] = SD.split('sub-')[-1].split('_')[0]
        else:
            series_entities['subject'] = None
        
        if '_ses-' in SD:
            series_entities['sessions'] = SD.split('_ses-')[-1].split('_')[0]
        else:
            series_entities['sessions'] = None
            
        if '_run-' in SD:
            series_entities['run'] = SD.split('_run-')[-1].split('_')[0]
            if series_entities['run'][0] == '0':
                series_entities['run'] = series_entities['run'][1:]
        else:
            series_entities['run'] = ''
        
        if '_task-' in SD:
            series_entities['task'] = SD.split('_task-')[-1].split('_')[0]
        else:
            pass
        
        if '_dir-' in SD:
            series_entities['direction'] = SD.split('_dir-')[-1].split('_')[0]
        else:
            series_entities['direction'] = ''
    
        if '_acq-' in SD:
            series_entities['acquisition'] = SD.split('_acq-')[-1].split('_')[0]
        else:
            series_entities['acquisition'] = ''
            
        if '_ce-' in SD:
            series_entities['ceagent'] = SD.split('_ce-')[-1].split('_')[0]
        else:
            series_entities['ceagent'] = ''
            
        if '_echo-' in SD:
            series_entities['echo'] = SD.split('_echo-')[-1].split('_')[0]
            if series_entities['echo'][0] == '0':
                series_entities['echo'] = series_entities['echo'][1:]
        else:
            series_entities['echo'] = ''
        
        if '_fa-' in SD:
            series_entities['fa'] = SD.split('_fa-')[-1].split('_')[0]
        else:
            series_entities['fa'] = ''
            
        if '_inv-' in SD:
            series_entities['inv'] = SD.split('_inv-')[-1].split('_')[0]
            if series_entities['inv'][0] == '0':
                series_entities['inv'] = series_entities['inv'][1:]
        else:
            series_entities['inv'] = ''
            
        if '_part-' in SD:
            series_entities['part'] = SD.split('_part-')[-1].split('_')[0]
        else:
            series_entities['part'] = ''
        
        
        #Make easier to find key characters/phrases in SD by removing non-alphanumeric characters and make everything lowercase
        SD = re.sub('[^A-Za-z0-9]+', '', SD).lower()
        
        ### Determine DataTypes and ModalityLabels #######
        #Localizers or other non-BIDS compatible acquisitions
        if any(x in SD for x in ['localizer','scout']):
            data_list_unique_series[i]['include'] = False
            data_list_unique_series[i]['error'] = 'Acquisition appears to be a localizer or other non-compatible BIDS acquisition'
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be some form of localizer because "localizer" or "scout" is in the SeriesDescription. Please modify if incorrect. ezBIDS does not convert locazliers to BIDS'
            data_list_unique_series[i]['br_type'] = 'exclude (localizer)'
            
        #Arterial Spin Labeling (ASL)
        elif any(x in SD for x in ['asl']):
            data_list_unique_series[i]['include'] = False
            data_list_unique_series[i]['DataType'] = 'asl'
            data_list_unique_series[i]['ModalityLabel'] = 'asl'
            data_list_unique_series[i]['error'] = 'Acqusition appears to be ASL, which is currently not supported by ezBIDS at this time, but will be in the future'
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be asl/asl because "asl" is in the SeriesDescription. Please modify if incorrect. Currently, ezBIDS does not support ASL conversion to BIDS'
            
        #Angiography
        elif any(x in SD for x in ['angio']):
            data_list_unique_series[i]['include'] = False
            data_list_unique_series[i]['DataType'] = 'anat'
            data_list_unique_series[i]['ModalityLabel'] = 'angio'
            data_list_unique_series[i]['error'] = 'Acqusition appears to be an Angiography acquisition, which is currently not supported by ezBIDS at this time, but will be in the future'
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be anat/angio because "angio" is in the SeriesDescription. Please modify if incorrect. Currently, ezBIDS does not support Angiography conversion to BIDS'
                    
        #Magnitude/Phase[diff] and Spin Echo (SE) field maps
        elif any(x in SD for x in ['fmap','fieldmap','spinecho','sefmri','semri']):
            data_list_unique_series[i]['DataType'] = 'fmap'
            
            #Magnitude/Phase[diff] field maps
            if 'EchoNumber' in data_list_unique_series[i]['sidecar']:
                if any(x in data_list_unique_series[i]['json_path'] for x in ['_real.','_imaginary.']):
                    data_list_unique_series[i]['include'] = False
                    data_list_unique_series[i]['error'] = 'Acquisition appears to be a real or imaginary field map that needs to be manually adjusted to magnitude and phase (ezBIDS currently does not have this functionality). This acqusition will not be converted'
                    data_list_unique_series[i]['message'] = data_list_unique_series[i]['error']
                    data_list_unique_series[i]['br_type'] = 'exclude'
                elif data_list_unique_series[i]['EchoNumber'] == 1 and '_e1_ph' not in data_list_unique_series[i]['json_path']:
                    data_list_unique_series[i]['ModalityLabel'] = 'magnitude1'
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/magnitude1 because "fmap" or "fieldmap" is in SeriesDescription, EchoNumber == 1 in metadata, and the subjectstring "_e1_ph" is not in the filename. Please modify if incorrect'
                elif data_list_unique_series[i]['EchoNumber'] == 1 and '_e1_ph' in data_list_unique_series[i]['json_path']:
                    data_list_unique_series[i]['ModalityLabel'] = 'phase1'
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/phase1 because "fmap" or "fieldmap" is in SeriesDescription, EchoNumber == 1 in metadata, and the subjectstring "_e1_ph" is in the filename. Please modify if incorrect'
                elif data_list_unique_series[i]['EchoNumber'] == 2 and '_e2_ph' not in data_list_unique_series[i]['json_path']:
                    data_list_unique_series[i]['ModalityLabel'] = 'magnitude2'
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/magnitude2 because "fmap" or "fieldmap" is in SeriesDescription, EchoNumber == 2 in metadata, and the subjectstring "_e2_ph" is not in the filename. Please modify if incorrect'
                elif data_list_unique_series[i]['EchoNumber'] == 2 and '_e2_ph' in data_list_unique_series[i]['json_path'] and '_e1_ph' in data_list_unique_series[i-2]['json_path']:
                    data_list_unique_series[i]['ModalityLabel'] = 'phase2'
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/phase2 because "fmap" or "fieldmap" is in SeriesDescription, EchoNumber == 2 in metadata, and the subjectstring "_e2_ph" is in the filename and "_e1_ph" the one two before. Please modify if incorrect'
                elif data_list_unique_series[i]['EchoNumber'] == 2 and '_e2_ph' in data_list_unique_series[i]['json_path'] and '_e1_ph' not in data_list_unique_series[i-2]['json_path']:
                    data_list_unique_series[i]['ModalityLabel'] = 'phasediff'
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/phasediff because "fmap" or "fieldmap" is in SeriesDescription, EchoNumber == 2 in metadata, and the subjectstring "_e2_ph" is in the filename but "_e1_ph" not in the one two before. Please modify if incorrect'
                else:
                    data_list_unique_series[i]['include'] = False
                    data_list_unique_series[i]['error'] = 'Acquisition appears to be some form of fieldmap with an EchoNumber, however, unable to determine if it is a magnitude, phase, or phasediff. Please modify if acquisition is desired for BIDS conversion, otherwise the acqusition will not be converted'
                    data_list_unique_series[i]['message'] = data_list_unique_series[i]['error']
                    data_list_unique_series[i]['br_type'] = 'exclude'
                    
            #Spin echo field maps
            else:
                data_list_unique_series[i]['ModalityLabel'] = 'epi'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/epi because "fmap" or "fieldmap" is in SeriesDescription, and does not contain metadata info associated with magnitude/phasediff acquisitions. Please modify if incorrect'
                series_entities['direction'] = data_list_unique_series[i]['direction']
            
        #DWI
        elif any('.bvec' in x for x in data_list_unique_series[i]['paths']):
            
            if any(x in SD for x in ['flair','t2spacedafl']):
                data_list_unique_series[i]['DataType'] = 'anat'
                data_list_unique_series[i]['ModalityLabel'] = 'FLAIR'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be anat/FLAIR because "flair" or "t2spacedafl" is in the SeriesDescription. Please modify if incorrect'

            elif 't2w' in SD:
                data_list_unique_series[i]['DataType'] = 'anat'
                data_list_unique_series[i]['ModalityLabel'] = 'T2w'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be anat/T2w because "t2w" is in the SeriesDescription. Please modify if incorrect'
            
            # elif not any(x in SD for x in ['dwi','dti','dmri','trace','fa','adc']):
            #     data_list_unique_series[i]['include'] = False
            #     data_list_unique_series[i]['error'] = 'Acquisition has bval and bvec files but does not appear to be dwi/dwi or fmap/epi that work on dwi/dwi acquistions. Please modify if incorrect, otherwise will not convert to BIDS'
            #     data_list_unique_series[i]['message'] = data_list_unique_series[i]['error']
            #     data_list_unique_series[i]['br_type'] = 'exclude'
            
            else:    
                #Some "dwi" acquisitions are actually fmap/epi; check for this
                bval = np.loadtxt([x for x in data_list_unique_series[i]['paths'] if 'bval' in x][0])
                if np.max(bval) <= 50 and bval.size < 10:
                    data_list_unique_series[i]['DataType'] = 'fmap'
                    data_list_unique_series[i]['ModalityLabel'] = 'epi'
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/epi meant for dwi because there are bval & bvec files with the same SeriesNumber, but the max b-values are <= 50 and the number of b-values is less than 10. Please modify if incorrect'
                    series_entities['direction'] = data_list_unique_series[i]['direction']
                elif any(x in SD for x in ['trace','fa','adc']) and not any(x in SD for x in ['dti','dwi','dmri']):
                    data_list_unique_series[i]['include'] = False
                    data_list_unique_series[i]['error'] = 'Acquisition appears to be a TRACE, FA, or ADC, which are unsupported by ezBIDS and will therefore not be converted'
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be TRACE, FA, or ADC because there are bval & bvec files with the same SeriesNumber, and "trace", "fa", or "adc" are in the SeriesDescription. Please modify if incorrect'
                    data_list_unique_series[i]['br_type'] = 'exclude'
                else:
                    data_list_unique_series[i]['DataType'] = 'dwi'
                    data_list_unique_series[i]['ModalityLabel'] = 'dwi'
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be dwi/dwi because there are bval & bvec files with the same SeriesNumber, "dwi" or "dti" is in the SeriesDescription, and it does not appear to be dwi product data. Please modify if incorrect'
                    series_entities['direction'] = data_list_unique_series[i]['direction']
        
        #DWI derivatives or other non-BIDS diffusion offshoot acquisitions 
        elif any(x in SD for x in ['trace','fa','adc']) and any(x in SD for x in ['dti','dwi','dmri']):
            data_list_unique_series[i]['include'] = False
            data_list_unique_series[i]['error'] = 'Acquisition appears to be a TRACE, FA, or ADC, which are unsupported by ezBIDS and will therefore not be converted'
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be TRACE, FA, or ADC because there are bval & bvec files with the same SeriesNumber, and "trace", "fa", or "adc" are in the SeriesDescription. Please modify if incorrect'
            data_list_unique_series[i]['br_type'] = 'exclude'
        
        #Functional bold and phase
        elif any(x in SD for x in ['bold','func','fmri','epi','mri','task','rest']) and 'sbref' not in SD:
            data_list_unique_series[i]['DataType'] = 'func'
            if any(x in SD for x in ['rest','rsfmri','fcmri']):
                series_entities['task'] = 'rest'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be func/bold because "bold","func","fmri","epi","mri", or"task" is in the SeriesDescription (but not "sbref"). Please modify if incorrect'
            if 'MOSAIC' and 'PHASE' in data_list_unique_series[i]['ImageType']:
                data_list_unique_series[i]['ModalityLabel'] = 'phase'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be func/phase because "bold","func","fmri","epi","mri", or"task" is in the SeriesDescription (but not "sbref"), and "MOSAIC" and "PHASE" are in the ImageType field of the metadata. Please modify if incorrect'
            else:
                data_list_unique_series[i]['ModalityLabel'] = 'bold'
                if data_list_unique_series[i]['EchoNumber']:
                    series_entities['echo'] = data_list_unique_series[i]['EchoNumber']
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be func/bold because "bold","func","fmri","epi","mri", or"task" is in the SeriesDescription (but not "sbref"). Please modify if incorrect'
            if data_list_unique_series[i]['EchoNumber']:
                series_entities['echo'] = data_list_unique_series[i]['EchoNumber']
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be func/bold because "bold","func","fmri","epi","mri", or"task" is in the SeriesDescription (but not "sbref"). Please modify if incorrect'

        #Functional single band reference (sbref)
        elif 'sbref' in SD:
            data_list_unique_series[i]['DataType'] = 'func'
            data_list_unique_series[i]['ModalityLabel'] = 'sbref'
            if 'rest' in SD or 'rsfmri' in SD:
                series_entities['task'] = 'rest'
            if data_list_unique_series[i]['EchoNumber']:
                series_entities['echo'] = data_list_unique_series[i]['EchoNumber']
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be func/sbref because "sbref" is in the SeriesDescription'
        
        #MP2RAGE (technically not officially part of BIDS, but people still use it)
        elif 'mp2rage' in SD:
            data_list_unique_series[i]['DataType'] = 'anat'
            data_list_unique_series[i]['ModalityLabel'] = 'MP2RAGE'
            if 'InversionTime' not in data_list_unique_series[i]['sidecar']:
                series_entities['acquisition'] = 'UNI'
            else:
                if 'inv1' in SD:
                    series_entities['inv'] = 1
                elif 'inv2' in SD:
                    series_entities['inv'] = 2
                else:
                    series_entitites['inv'] = mp2rage_inv
                    mp2rage_inv += 1
            
            if 'EchoNumber' in data_list_unique_series[i]['sidecar']:
                series_entities['echo'] = data_list_unique_series[i]['sidecar']['EchoNumber']

        #T1w
        elif any(x in SD for x in ['t1w','tfl3d','mprage','spgr']):
            data_list_unique_series[i]['DataType'] = 'anat'
            data_list_unique_series[i]['ModalityLabel'] = 'T1w'
            if data_list_unique_series[i]['EchoNumber']:
                series_entities['echo'] = data_list_unique_series[i]['EchoNumber']
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be anat/T1w because "t1w","tfl3d","tfl","mprage", or "spgr" is in the SeriesDescription. Please modify if incorrect'
        
        #FLAIR
        elif any(x in SD for x in ['flair','t2spacedafl']):
            data_list_unique_series[i]['DataType'] = 'anat'
            data_list_unique_series[i]['ModalityLabel'] = 'FLAIR'
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be anat/FLAIR because "flair" or "t2spacedafl" is in the SeriesDescription. Please modify if incorrect'

        #T2w
        elif 't2w' in SD:
            data_list_unique_series[i]['DataType'] = 'anat'
            data_list_unique_series[i]['ModalityLabel'] = 'T2w'
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be anat/T2w because "t2w" is in the SeriesDescription. Please modify if incorrect'
            
        #Can't discern from SeriesDescription, try using ndim and number of volumes to see if this is a func/bold
        else:
            test = nib.load(data_list_unique_series[i]['nifti_path'])
            if test.ndim == 4 and test.shape[3] >= 50 and not any(x in data_list_unique_series[i]['ImageType'] for x in ['DERIVED','PERFUSION','DIFFUSION','ASL']):
                data_list_unique_series[i]['DataType'] = 'func'
                data_list_unique_series[i]['ModalityLabel'] = 'bold'
                data_list_unique_series[i]['message'] = 'SeriesDescription did not provide hints regarding the type of acquisition; however, it is believed to be a func/bold because it contains >= 50 volumes. Please modify if incorrect'
            
            #Assume not BIDS-compliant acquisition unless user specifies so
            else: 
                data_list_unique_series[i]['include'] = False
                data_list_unique_series[i]['error'] = 'Acquisition cannot be resolved. Please determine whether or not this acquisition should be converted to BIDS'
                data_list_unique_series[i]['message'] = 'Acquisition is unknown because there is not enough adequate information, primarily in the SeriesDescription. Please modify if acquisition is desired for BIDS conversion, otherwise the acqusition will not be converted'
                data_list_unique_series[i]['br_type'] = 'exclude'
                
        
        #Combine DataType and ModalityLabel to form br_type variable (needed for internal brainlife.io storage)
        if data_list_unique_series[i]['include'] == True:
            data_list_unique_series[i]['br_type'] = data_list_unique_series[i]['DataType'] + '/' + data_list_unique_series[i]['ModalityLabel']
        elif data_list_unique_series[i]['include'] == False and 'localizer' not in data_list_unique_series[i]['br_type']:
            data_list_unique_series[i]['br_type'] = 'exclude'
        else:
            pass
    
        #Combine info above into dictionary, which will be displayed to user through the UI
        series_info = {"include": data_list_unique_series[i]['include'],
                       "SeriesDescription": data_list_unique_series[i]['SeriesDescription'],
                       "SeriesNumber": data_list_unique_series[i]['SeriesNumber'],
                       "series_id": data_list_unique_series[i]['series_id'],
                       "EchoTime": data_list_unique_series[i]['EchoTime'],
                       "ImageType": data_list_unique_series[i]['ImageType'],
                       "MultibandAccelerationFactor": data_list_unique_series[i]['MultibandAccelerationFactor'],
                       "entities": series_entities,
                       "type": data_list_unique_series[i]['br_type'],
                       "error": data_list_unique_series[i]['error'],
                       "message": data_list_unique_series[i]['message'],
                       "repetitionTimes": [],
                       "object_indices": []
                        }
        series_list.append(series_info)
        print('Unique data acquisition file {}, Series Description {}, was determined to be {}'.format(data_list_unique_series[i]['nifti_path'], data_list_unique_series[i]['SeriesDescription'], data_list_unique_series[i]['br_type']))
        print('')
        print('')

    return series_list


def identify_objects_info(subject_protocol, series_list, series_seriesID_list):
    '''
    Takes list of dictionaries with key and unique information, and sessions it to 
    determine the DataType and Modality labels of the unique acquisitions. 
    Other information (e.g. run, acq, ce) will be determined if the data follows 
    the ReproIn naming convention for SeriesDescriptions.

    Parameters
    ----------
    subject_protocol: list
        List of dictionary, containing pertinent information needed 
        for the UI side of ezBIDS
        
    series_list: list
        List of dictionaries containing the series-level info for file naming, 
        such as "acq","run","dir","ce", etc.
        
    series_seriesID_list: list
        List of numeric values, each one linked to a unique acquiistion in the
        series list. This is different from SeriesNumber, and is used to port 
        info from the series-level down to the objects-level.

    Returns
    -------
    subject_protocol: list
        Same as above but with updated information
    '''
    func_sbref_run = 1
    func_phase_run = 1
    bold_run = 1
    objects_entities_list = []
    series_func_list = []
    
    for p in range(len(subject_protocol)):
        if p == 0:
            protocol_index = 0
            
        subject_protocol[p]['protocol_index'] = protocol_index
        protocol_index += 1
        subject_protocol[p]['headers'] = str(nib.load(subject_protocol[p]['nifti_path']).header).splitlines()[1:]
                
        image = nib.load(subject_protocol[p]['nifti_path'])
        object_img_array = image.dataobj
        if object_img_array.dtype not in ['<i2', '<u2']: #Weird issue where data array is RGB instead on intger
            subject_protocol[p]['include'] = False
            subject_protocol[p]['error'] = 'The data array is for this acquisition is improper, likely suggesting some issue with the corresponding DICOMS'
            subject_protocol[p]['message'] = subject_protocol[p]['error']
            subject_protocol[p]['br_type'] = 'exclude'
        else:            
            if subject_protocol[p]['NumVolumes'] > 1:
                object_img_array = image.dataobj[..., 1]
            else:
                object_img_array = image.dataobj[:]
                    
            if not os.path.isfile('{}.png'.format(subject_protocol[p]['nifti_path'][:-7])):            
                
                slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
                slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
                slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]
                                                                
                fig, axes = plt.subplots(1,3, figsize=(9,3))
                for i, slice in enumerate([slice_x, slice_y, slice_z]):
                    axes[i].imshow(slice.T, cmap="gray", origin="lower", aspect='auto')
                    axes[i].axis('off')
                plt.subplots_adjust(wspace=0, hspace=0)
                plt.savefig('{}.png'.format(subject_protocol[p]['nifti_path'][:-7]), bbox_inches='tight')
            
        index = series_seriesID_list.index(subject_protocol[p]['series_id'])
        objects_entities = {'subject': '', 'sessions': '', 'run': '', 'task': '', 'direction': '', 'acquisition': '', 'ceagent': '', 'echo': '', 'fa': '', 'inv': '', 'part': ''}
        
        #Port series level information down to the object level
        subject_protocol[p]['include'] = series_list[index]['include']
        subject_protocol[p]['DataType'] = data_list_unique_series[index]['DataType']
        subject_protocol[p]['ModalityLabel'] = data_list_unique_series[index]['ModalityLabel']
        subject_protocol[p]['br_type'] = series_list[index]['type']
        subject_protocol[p]['error'] = series_list[index]['error']
        subject_protocol[p]['subject'] = subjects[s]
                
            
        if 'run' in series_list[index]['entities'] and series_list[index]['entities']['run']:
            objects_entities['run'] = series_list[index]['entities']['run']
        if 'direction' in series_list[index]['entities'] and series_list[index]['entities']['direction']:
            objects_entities['direction'] = series_list[index]['entities']['direction']
        if 'task' in series_list[index]['entities'] and series_list[index]['entities']['task']:
            objects_entities['task'] = series_list[index]['entities']['task']
            subject_protocol[p]['TaskName'] = series_list[index]['entities']['task']
        if 'acquisition' in series_list[index]['entities'] and series_list[index]['entities']['acquisition']:
            objects_entities['acquisition'] = series_list[index]['entities']['acquisition']
        if 'ceagent' in series_list[index]['entities'] and series_list[index]['entities']['ceagent']:
            objects_entities['ceagent'] = series_list[index]['entities']['ceagent']
        if 'echo' in series_list[index]['entities'] and series_list[index]['entities']['echo']:
            objects_entities['echo'] = series_list[index]['entities']['echo']
        
        #Determine other important BIDS information (i.e. run, dir, etc) for specific acquisitions        
        #T1w & T2w
        if subject_protocol[p]['br_type'] in ['anat/T1w','anat/T2w'] and subject_protocol[p]['include'] == True:
            #non-normalized T1w or T2w images that have poor CNR, so best to not have in BIDS if there's an actual good T1w or T2w available
            if 'NORM' not in subject_protocol[p]['ImageType']:
                try:
                    index_next = series_seriesID_list.index(subject_protocol[p+1]['series_id'])
                except:
                    index_next = None
                
                if p+1 == len(subject_protocol):
                    subject_protocol[p]['include'] = True 
                    subject_protocol[p]['error'] = None
                elif subject_protocol[p]['br_type'] == data_list_unique_series[index_next]['br_type'] and 'NORM' not in data_list_unique_series[index_next]['ImageType']:
                    subject_protocol[p]['include'] = True 
                    subject_protocol[p]['error'] = None
                elif subject_protocol[p]['br_type'] != data_list_unique_series[index_next]['br_type']:
                    subject_protocol[p]['include'] = True 
                    subject_protocol[p]['error'] = None
                else:
                    subject_protocol[p]['include'] = False  
                    subject_protocol[p]['error'] = 'Acquisition is a poor resolution {} (non-normalized); Please check to see if this {} acquisition should be converted to BIDS. Otherwise, this object will not be included in the BIDS output'.format(subject_protocol[p]['br_type'], subject_protocol[p]['br_type'])
                    subject_protocol[p]['message'] = subject_protocol[p]['error']
                    subject_protocol[p]['br_type'] = 'exclude'
        
        #Functional bold
        elif subject_protocol[p]['br_type'] == 'func/bold':
            #Instances where functional bold acquisitions have less than 50 volumes (probably a restart/failure occurred, or some kind of non-BIDS test)
            if subject_protocol[p]['NumVolumes'] < 50:
                subject_protocol[p]['include'] = False
                subject_protocol[p]['error'] = 'Functional run only contains {} volumes; ezBIDS flags functional runs with under 50 volumes. Please check to see whether this should be excluded or not from BIDS conversion'.format(subject_protocol[p]['NumVolumes'])
                subject_protocol[p]['br_type'] = 'exclude'
            else:
                if objects_entities['run'] == '':
                    if not len([x for x in series_func_list if x[0] == subject_protocol[p]['series_id']]):
                        series_func_list.append([subject_protocol[p]['series_id'], 1])
                        bold_run = 1
                        subject_protocol[p]['bold_run'] = '1'
                    else:
                        func_index = [x for x, y in enumerate(series_func_list) if y[0] == subject_protocol[p]['series_id']][0]
                        series_func_list[func_index][1] += 1
                        bold_run = series_func_list[func_index][1]
                        
                    if bold_run < 10:
                        subject_protocol[p]['bold_run'] = str(bold_run)
                    else:
                        subject_protocol[p]['bold_run'] = str(bold_run)
                        
                    objects_entities['run'] = subject_protocol[p]['bold_run']
                else:
                    subject_protocol[p]['bold_run'] = objects_entities['run']
                
        #Functional phase
        elif subject_protocol[p]['br_type'] == 'func/phase':
            if objects_entities['run'] == '':
                if not len([x for x in series_func_list if x[0] == subject_protocol[p]['series_id']]):
                    series_func_list.append([subject_protocol[p]['series_id'], 1])
                    func_phase_run = 1
                    subject_protocol[p]['func_phase_run'] = '1'
                else:
                    func_index = [x for x, y in enumerate(series_func_list) if y[0] == subject_protocol[p]['series_id']][0]
                    series_func_list[func_index][1] += 1
                    func_phase_run = series_func_list[func_index][1]
                    
                if func_phase_run < 10:
                    subject_protocol[p]['func_phase_run'] = str(func_phase_run)
                else:
                    subject_protocol[p]['func_phase_run'] = str(func_phase_run)
                    
                objects_entities['run'] = subject_protocol[p]['func_phase_run']
            else:
                subject_protocol[p]['func_phase_run'] = objects_entities['run']
                    

        #Functional single band reference (sbref)
        elif subject_protocol[p]['br_type'] == 'func/sbref':
            if p+1 < len(subject_protocol):
                index_next = series_seriesID_list.index(subject_protocol[p+1]['series_id'])
                subject_protocol[p+1]['br_type'] = data_list_unique_series[index_next]['br_type']
                
            #Rare instances where sbref is not followed by functional bold
            if subject_protocol[p+1]['br_type'] != 'func/bold':
                subject_protocol[p]['include'] = False
                subject_protocol[p]['error'] = 'Single band reference (sbref) acquisition is not immediately followed by a functional bold acquisition that is being converted to BIDS. This object will not be included in the BIDS output'
                subject_protocol[p]['br_type'] = 'exclude'
                
            #Set include to False if functional bold after it has less than 50 volumes, which will cause it to not be converted to BIDS
            elif nib.load(subject_protocol[p+1]['nifti_path']).shape[3] < 50:
                subject_protocol[p]['include'] = False
                subject_protocol[p]['error'] = 'Functional bold acquisition following this sbref contains less than 50 volumes, therefore BIDS conversion for this acqusition (and the preceding sbref) not recommended.'
                subject_protocol[p]['br_type'] = 'exclude'
            else:    
                if objects_entities['run'] == '':
                    if not len([x for x in series_func_list if x[0] == subject_protocol[p]['series_id']]):
                        series_func_list.append([subject_protocol[p]['series_id'], 1])
                        func_sbref_run = 1
                        subject_protocol[p]['func_sbref_run'] = '1'
                    else:
                        func_index = [x for x, y in enumerate(series_func_list) if y[0] == subject_protocol[p]['series_id']][0]
                        series_func_list[func_index][1] += 1
                        func_sbref_run = series_func_list[func_index][1]
                        
                    if func_sbref_run < 10:
                        subject_protocol[p]['func_sbref_run'] = str(func_sbref_run)
                    else:
                        subject_protocol[p]['func_sbref_run'] = str(func_sbref_run)
                        
                    objects_entities['run'] = subject_protocol[p]['func_sbref_run']
                else:
                    subject_protocol[p]['func_sbref_run'] = objects_entities['run']
                    
        objects_entities_list.append(objects_entities)
        
    #Add run number to anat and dwi/dwi that have multiple acquisitions but with the same parameters
    t1w_indices = [x['protocol_index'] for x in subject_protocol if x['include'] == True and x['br_type'] == 'anat/T1w']
    t2w_indices = [x['protocol_index'] for x in subject_protocol if x['include'] == True and x['br_type'] == 'anat/T2w']
    flair_indices = [x['protocol_index'] for x in subject_protocol if x['include'] == True and x['br_type'] == 'anat/FLAIR']
    dwi_indices = [x['protocol_index'] for x in subject_protocol if x['include'] == True and x['br_type'] == 'dwi/dwi']

    for w in [t1w_indices, t2w_indices, flair_indices, dwi_indices]:
        if len(w) > 1:      
            parameter_tuples = []
            parameter_id = 0   
            parameters = [[subject_protocol[y]['SeriesDescription'], subject_protocol[y]['EchoTime'], subject_protocol[y]['ImageType'], subject_protocol[y]['RepetitionTime'], subject_protocol[y]['direction'], parameter_id] for y in w]
            for x in range(len(parameters)):  
                tup = (parameters[x][:])
                if tup[:-1] not in [y[:-1] for y in parameter_tuples]: 
                    tup[-1] = parameter_id
                    parameter_id += 1
                else:
                    tup[-1] = parameter_tuples[[y[:-1] for y in parameter_tuples].index(tup[:-1])][-1]
                        
                parameter_tuples.append(tup)
            
            uniques = list(set([x[-1] for x in parameter_tuples]))
            for u in uniques:
                if len([x for x in parameter_tuples if x[-1] == 0]) == 1:
                    pass
                else:                        
                    run = 1
                    for xx,yy in enumerate(parameter_tuples):
                        if yy[-1] == u:
                            if run < 10:
                                objects_entities_list[w[xx]]['run'] = str(run)
                            else:
                                objects_entities_list[w[xx]]['run'] = str(run)
                            run += 1 
                            
    return subject_protocol, objects_entities_list
    

def fmap_intended_for(subject_protocol, total_objects_indices, objects_entities_list):
    '''
    Determine IntendedFor fields for fmap acquisitions 
    
    Parameters
    ----------
    subject_protocol: list
        List of dictionary, containing pertinent information needed 
        for the UI side of ezBIDS
    
    Returns
    ----------
    subject_protocol: list
        Same as above, but with updated information from the checks
    '''
    
    br_types = [subject_protocol[x]['br_type'] for x in range(len(subject_protocol))]
    include = [subject_protocol[x]['include'] for x in range(len(subject_protocol))]
    errors = [subject_protocol[x]['error'] for x in range(len(subject_protocol))]
    messages = [subject_protocol[x]['message'] for x in range(len(subject_protocol))]
    phase_encoding_directions = [subject_protocol[x]['direction'] for x in range(len(subject_protocol))]
    section_indices = [x for x, y in enumerate(br_types) if x == 0 or ('localizer' in y and 'localizer' not in br_types[x-1])]
    total_objects_indices = total_objects_indices
    fmap_magphase_runcheck = []
    fmap_se_runcheck = []
    fmap_se_dwi_runcheck = []    

    for j,k in enumerate(section_indices):
        '''
        Sections are determined by where the next set of localizers are.
        A "typical" protocol will likely only have 1 section, but if subject
            comes in and out of scanner then there are now two sections.
        Protocols with fmaps will have fmaps for each section.
        '''
        #Determine section start and end points
        section_start = k
        try:
            section_end = section_indices[j+1]
        except:
            section_end = len(br_types)
        
            
        #Check for potential issues
        for x,y in enumerate(br_types[section_start:section_end]):
            subject_protocol[k+x]['section_ID'] = j+1
            bold_indices = [total_objects_indices+k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'func/bold' and include[k+x] == True]
            dwi_indices = [total_objects_indices+k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'dwi/dwi' and include[k+x] == True]
            non_fmap_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if 'fmap' not in y]
            
            #Spin echo fmaps to be applied to func/bold acquisitions
            if y == 'fmap/epi' and 'max b-values' not in messages[k+x]:
                fmap_se_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and 'max b-values' not in messages[k+x]]
                
                #If no func/bold acquisitions in section then the fmap/epi in this section are pointless, therefore won't be converted to BIDS
                if len(bold_indices) == 0:
                    for fm in fmap_se_indices:
                        include[fm] = False
                        subject_protocol[fm]['include'] = include[fm]
                        subject_protocol[fm]['br_type'] = 'exclude'
                        errors[fm] = 'No valid func/bold acquisitions found in section. This is due to the field maps and functional bold acquisitions separated by localizer(s), indicating that subject got out and then re-entered scanner. SDC is unlikely to work, therefore this field map acquisition will not be included in the BIDS output'
                        subject_protocol[fm]['error'] = errors[fm]
                    
                #Only one fmap/epi acquisition in section. Can't be converted b/c need pair
                if len(fmap_se_indices) == 1:
                    for fm in fmap_se_indices:
                        include[fm] = False
                        subject_protocol[fm]['include'] = include[fm]
                        subject_protocol[fm]['br_type'] = 'exclude'
                        errors[fm] = 'Only one spin echo field map found; need pair. This acquisition will not be included in the BIDS output'
                        subject_protocol[fm]['error'] = errors[fm]
                
                #If more than two fmap/epi acquisitions, only accept most recent pair in section
                if len(fmap_se_indices) > 2:
                    for fm in fmap_se_indices[:-2]:
                        include[fm] = False
                        subject_protocol[fm]['include'] = include[fm]
                        subject_protocol[fm]['br_type'] = 'exclude'
                        errors[fm] = 'Multiple spin echo field map pairs detected in section; only selecting last pair for BIDS conversion. The other pair acquisition(s) in this section will not be included in the BIDS output'
                        subject_protocol[fm]['error'] = errors[fm]
                        
                #Re-determine the fmap/epi indices in light of the checks above
                fmap_se_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and include[k+x] == True]
                
                #If fmap/epi pair don't have opposing phase encoding directions, won't be converted to BIDS
                if len(fmap_se_indices) == 2:
                    fmap_se_PEDs = [y for x,y in enumerate(phase_encoding_directions) if k+x in fmap_se_indices]
                    if fmap_se_PEDs[0][::-1] != fmap_se_PEDs[1]:
                        for fm in fmap_se_indices:
                            include[fm] = False
                            subject_protocol[fm]['include'] = include[fm]
                            subject_protocol[fm]['br_type'] = 'exclude'
                            errors[fm] = 'Spin echo fmap pair does not have opposite phase encoding directions. This acquisition will not be included in the BIDS output'
                            subject_protocol[fm]['error'] = errors[fm]
                
                #Re-determine the fmap/epi indices again
                fmap_se_indices = [k+x for x,y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and include[k+x] == True]

                if len(fmap_se_indices) == 2:
                    for fm in fmap_se_indices:
                        subject_protocol[fm]['IntendedFor'] = bold_indices
                        
                if fmap_se_indices not in fmap_se_runcheck:
                    fmap_se_runcheck.append(fmap_se_indices)
                        
            
            #Magnitude/Phase[diff] fmaps
            elif y in ['fmap/magnitude1','fmap/phase1','fmap/magnitude2','fmap/phase2','fmap/phasediff']:
                #Remove duplicate magnitude/phasediff fmaps. Only last group in each section will be kept
                
                if 'magnitude' in y:
                    if 'phase1' in br_types[section_start:section_end][x+1] or 'phase2' in br_types[section_start:section_end][x+1]:
                        fmap_magphase_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y in ['fmap/magnitude1','fmap/phase1','fmap/magnitude2','fmap/phase2']]
                        case = 1
                    else:
                        fmap_magphase_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y in ['fmap/magnitude1','fmap/magnitude2','fmap/phasediff']]
                        case = 0
                        
                elif 'phase1' in y or 'phase2' in y:
                    fmap_magphase_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y in ['fmap/magnitude1','fmap/phase1','fmap/magnitude2','fmap/phase2']]
                    case = 1
                    
                elif 'phasediff' in y:
                    fmap_magphase_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y in ['fmap/magnitude1','fmap/magnitude2','fmap/phasediff']]
                    case = 0
                
                else:
                    pass
            
                #If no func/bold acquisitions in section then the magnitude/phasediff in this section are pointless, therefore won't be converted to BIDS
                if len(bold_indices) == 0:
                    for fm in fmap_magphase_indices:
                        include[fm] = False
                        subject_protocol[fm]['include'] = include[fm]
                        subject_protocol[fm]['br_type'] = 'exclude'
                        errors[fm] = 'No valid func/bold acquisition found in section. This is due to the field maps and functional bold acquisitions separated by localizer(s), indicating that subject got out and then re-entered scanner. SDC is unlikely to work, therefore this field map acquisition will not be included in the BIDS output'
                        subject_protocol[fm]['error'] = errors[fm]
                  
                #two magnitude images, two phase images
                if case == 1:
                    if len(fmap_magphase_indices) < 4:
                        for fm in fmap_magphase_indices:
                            include[fm] = False
                            subject_protocol[fm]['include'] = include[fm]
                            subject_protocol[fm]['br_type'] = 'exclude'
                            errors[fm] = 'Need four images (2 magnitude, 2 phase). This acquisition will not be included in the BIDS output'
                            subject_protocol[fm]['error'] = errors[fm]
                            
                    if len(fmap_magphase_indices) > 4 and len(fmap_magphase_indices) % 4 == 0:
                        for fm in fmap_magphase_indices[:-4]:
                            include[fm] = False
                            subject_protocol[fm]['include'] = include[fm]
                            subject_protocol[fm]['br_type'] = 'exclude'
                            errors[fm] = 'Multiple images sets of (2 magnitude, 2 phase) field map acquisitions found in section. Only selecting most recent set. Other(s) will not be included in the BIDS output'
                            subject_protocol[fm]['error'] = errors[fm]
                        
                #one (or two) magnitude images, one phasediff images
                if case == 0:
                    if len(fmap_magphase_indices) < 3:
                        for fm in fmap_magphase_indices:
                            include[fm] = False
                            subject_protocol[fm]['include'] = include[fm]
                            subject_protocol[fm]['br_type'] = 'exclude'
                            errors[fm] = 'Need triplet for magnitude/phasediff field maps. This acquisition will not be included in the BIDS output'
                            subject_protocol[fm]['error'] = errors[fm]
                        
                    if len(fmap_magphase_indices) > 3 and len(fmap_magphase_indices) % 3 == 0:
                        for fm in fmap_magphase_indices[:-3]:
                            include[fm] = False
                            subject_protocol[fm]['include'] = include[fm]
                            subject_protocol[fm]['br_type'] = 'exclude'
                            errors[fm] = 'More than three magnitude/phasediff field map acquisitions found in section. Only selecting most recent three. Others will not be included in the BIDS output'
                            subject_protocol[fm]['error'] = errors[fm]
                        
                #Re-determine the magnitude/phasediff indices in light of the checks above
                if case == 0:
                    fmap_magphase_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y in ['fmap/magnitude1','fmap/magnitude2','fmap/phasediff'] and include[k+x] != False]  
                else:
                    fmap_magphase_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y in ['fmap/magnitude1','fmap/phase1','fmap/magnitude2','fmap/phase2'] and include[k+x] != False]        

               
                if len(fmap_magphase_indices) == 3 or len(fmap_magphase_indices) == 4:
                    for fm in fmap_magphase_indices:
                        subject_protocol[fm]['IntendedFor'] = bold_indices
                        
                if fmap_magphase_indices not in fmap_magphase_runcheck:
                    fmap_magphase_runcheck.append(fmap_magphase_indices)
                
                    
            #Spin-echo fmaps for DWI
            elif y == 'fmap/epi' and 'max b-values' in messages[k+x]:
                fmap_se_dwi_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and 'max b-values' in messages[k+x]]
            
                #If no dwi/dwi acquisitions in section then the fmap/epi_dwi in this section are pointless, therefore won't be converted to BIDS
                if len(dwi_indices) == 0:
                    for fm in fmap_se_dwi_indices:
                        include[fm] = False
                        subject_protocol[fm]['include'] = include[fm]
                        subject_protocol[fm]['br_type'] = 'exclude'
                        errors[fm] = 'No valid dwi/dwi acquisition(s) found in section. This is due to the field map and diffusion acquisition(s) separated by localizer(s), indicating that subject got out and then re-entered scanner. SDC is unlikely to work, therefore this field map acquisition will not be included in the BIDS output'
                        subject_protocol[fm]['error'] = errors[fm]
                  
                #If more than one fmap/epi_dwi acquisitions, only accept most recent one in section
                if len(fmap_se_dwi_indices) > 1:
                    for fm in fmap_se_dwi_indices[:-1]:
                        include[fm] = False
                        subject_protocol[fm]['include'] = include[fm]
                        subject_protocol[fm]['br_type'] = 'exclude'
                        errors[fm] = 'More than one dwi-specific field map detected in section; only selecting last one for BIDS conversion. Other acquisition(s) will not be included in the BIDS output'
                        subject_protocol[fm]['error'] = errors[fm]
                
                #Re-determine the fmap/epi_dwi indices in light of the checks above
                fmap_se_dwi_indices = [total_objects_indices+k+x for x,y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and 'max b-values' in messages[k+x] and include[k+x] != False]
                if len(fmap_se_dwi_indices) == 1:
                    for fm in fmap_se_dwi_indices:
                        subject_protocol[fm]['IntendedFor'] = dwi_indices
                        
                if fmap_se_dwi_indices not in fmap_se_dwi_runcheck:
                    fmap_se_dwi_runcheck.append(fmap_se_dwi_indices)
                
            else:
                pass
            
            #Add IntendedFor to all non-fmap acquisitions
            #This allows IntendedFor fields to auto-fill if user changes datatype on UI
            for nfm in non_fmap_indices:
                if 'dwi' in subject_protocol[nfm]['br_type']:
                    subject_protocol[nfm]['IntendedFor'] = dwi_indices
                else:
                    subject_protocol[nfm]['IntendedFor'] = bold_indices
                    
    #Add run label information if fmaps were retaken across sections
    if len(fmap_se_runcheck) > 1:
        for x,y in enumerate(fmap_se_runcheck):
            for z in y:
                objects_entities_list[z]['run'] = str(x+1)                    
                    
    if len(fmap_magphase_runcheck) > 1:
        for x,y in enumerate(fmap_magphase_runcheck):
            for z in y:
                objects_entities_list[z]['run'] = str(x+1)
                
    if len(fmap_se_dwi_runcheck) > 1:
        for x,y in enumerate(fmap_se_dwi_runcheck):
            for z in y:
                objects_entities_list[z]['run'] = str(x+1)
          
    return subject_protocol, objects_entities_list


def build_objects_list(subject_protocol, objects_entities_list):
    '''
    Create ezBIDS.json file, which provides all information used by the UI
    to display to users
    
    Parameters
    ----------
    subject_protocol: list
        List of dictionaries, containing pertinent information needed 
        for the UI side of ezBIDS
        
    objects_entities_list: list
        List of dictionaries containing additional information for files names,
        such as "acq","run","dir","ce", etc
    
    Returns
    ----------
    objects_list: list
        List of dictionaries containing info for the objects-level of ezBIDS.json
    '''
    for i in range(len(subject_protocol)):
        
        #Provide log output for acquisitions not deemed appropriate for BIDS conversion
        if subject_protocol[i]['include'] == False:
            print('')
            print('* {} (sn-{}) not recommended for BIDS conversion: {}'.format(subject_protocol[i]['SeriesDescription'], subject_protocol[i]['SeriesNumber'], subject_protocol[i]['error']))
        
        #Remove identifying information from sidecars
        remove_fields = ['SeriesInstanceUID', 'StudyInstanceUID', 
                         'ReferringPhysicianName', 'StudyID', 'PatientName', 
                         'PatientID', 'AccessionNumber', 'PatientBirthDate', 
                         'PatientSex', 'PatientWeight']
        for remove in remove_fields:
            if remove in subject_protocol[i]['sidecar']:
                del subject_protocol[i]['sidecar'][remove]
                
        #Make items list (part of objects list)
        items = []
        for item in subject_protocol[i]['paths']:
            if '.bval' in item:
                items.append({'path':item, 'name':'bval'})
            elif '.bvec' in item:
                items.append({'path':item, 'name':'bvec'})
            elif '.json' in item:
                items.append({'path':item, 'name':'json', 'sidecar':subject_protocol[i]['sidecar']})
            elif '.nii.gz' in item:
                items.append({'path':item, 'name':'nii.gz', 'headers':subject_protocol[i]['headers']})

        if subject_protocol[i]['error']:
            subject_protocol[i]['error'] = [subject_protocol[i]['error']]
            
        if subject_protocol[i]['br_type'] == 'exclude (localizer)':
            subject_protocol[i]['br_type'] = 'exclude'
                    
        #Objects-level info for ezBIDS.json
        if subject_protocol[i]['br_type'] == 'exclude' and 'Acquisition cannot be resolved' not in subject_protocol[i]['error'][0]:
            objects_info = {"include": subject_protocol[i]['include'],
                    "type": subject_protocol[i]['br_type'],
                    "series_id": subject_protocol[i]['series_id'],
                    "PatientName": subject_protocol[i]['PatientName'],
                    "PatientID": subject_protocol[i]['PatientID'],
                    "PatientBirthDate": subject_protocol[i]['PatientBirthDate'],
                    "AcquisitionDate": subject_protocol[i]['AcquisitionDate'],
                    'SeriesNumber': subject_protocol[i]['sidecar']['SeriesNumber'],
                    "pngPath": '{}.png'.format(subject_protocol[i]['nifti_path'][:-7]),
                    "IntendedFor": subject_protocol[i]['IntendedFor'],
                    "entities": objects_entities_list[i],
                    "items": items,
                    "analysisResults": {
                        "NumVolumes": subject_protocol[i]['NumVolumes'],
                        "errors": subject_protocol[i]['error'],
                        "filesize": subject_protocol[i]['filesize'],
                        "section_ID": subject_protocol[i]['section_ID']
                    },
                    "paths": subject_protocol[i]['paths']
                  }
        else:
            objects_info = {"include": subject_protocol[i]['include'],
                    "series_id": subject_protocol[i]['series_id'],
                    "PatientName": subject_protocol[i]['PatientName'],
                    "PatientID": subject_protocol[i]['PatientID'],
                    "PatientBirthDate": subject_protocol[i]['PatientBirthDate'],
                    "AcquisitionDate": subject_protocol[i]['AcquisitionDate'],
                    'SeriesNumber': subject_protocol[i]['sidecar']['SeriesNumber'],
                    "pngPath": '{}.png'.format(subject_protocol[i]['nifti_path'][:-7]),
                    "IntendedFor": subject_protocol[i]['IntendedFor'],
                    "entities": objects_entities_list[i],
                    "items": items,
                    "analysisResults": {
                        "NumVolumes": subject_protocol[i]['NumVolumes'],
                        "errors": subject_protocol[i]['error'],
                        "filesize": subject_protocol[i]['filesize'],
                        "section_ID": subject_protocol[i]['section_ID']
                    },
                    "paths": subject_protocol[i]['paths']
                  }
        objects_list.append(objects_info)

    return objects_list
    

###################### Begin ######################
    
data_dir = sys.argv[1]
os.chdir(data_dir)

print('########################################')
print('Beginning conversion process of dataset')
print('########################################')
print('')

#Load in list
dir_list = pd.read_csv('list', header=None, sep='\n')

#Determine variables data_list, data_list_unique_series, subjectIDs_info, and acquisition_dates
data_list, data_list_unique_series, subjectIDs_info, acquisition_dates = select_unique_data(dir_list)
    
#Determine series-level info
series_list = identify_series_info(data_list_unique_series)

#participantsColumn portion of ezBIDS.json
participantsColumn = {"sex": {"LongName": "gender", "Description": "generic gender field", "Levels": {"M": "male", "F": "female"}},
                      "age": {"LongName": "age", "Units": "years"}}
    
#Define a few variables that apply across the entire objects level
objects_list = []
total_objects_indices = 0
subjects = [acquisition_dates[x]['subject'] for x in range(len(acquisition_dates))]
sessions = [acquisition_dates[x]['sessions'] for x in range(len(acquisition_dates))]
series_seriesID_list = [series_list[x]['series_id'] for x in range(len(series_list))]

#Loop through all unique subjectIDs
for s in range(len(acquisition_dates)):
    
    if acquisition_dates[s]['sessions'] == '':
        print('')
        print('')
        print('Beginning conversion process for subject {} protocol acquisitions'.format(acquisition_dates[s]['subject']))
        print('-------------------------------------------------------------------')
        print('')
     
    else:
        print('')
        print('')
        print('Beginning conversion process for subject {}, sessions {} protocol acquisitions'.format(acquisition_dates[s]['subject'], acquisition_dates[s]['sessions']))
        print('-------------------------------------------------------------------')
        print('')
    
    #Get initial subject_protocol list from subjectsetting by subject/sessionss
    subject_protocol = [x for x in data_list if x['subject'] == acquisition_dates[s]['subject'] and x['sessions'] == acquisition_dates[s]['sessions']]
    
    #Update subject_protocol based on object-level checks
    subject_protocol, objects_entities_list = identify_objects_info(subject_protocol, series_list, series_seriesID_list)
    
    #update subject_protocol based on fmap IntendedFor checks
    subject_protocol, objects_entities_list = fmap_intended_for(subject_protocol, total_objects_indices, objects_entities_list)
        
    #Build objects_list
    objects_list = build_objects_list(subject_protocol, objects_entities_list)
    
    total_objects_indices += len(subject_protocol)
    
#Extract values to plot for users
for s in range(len(series_list)):
    if series_list[s]['type'] == 'exclude (localizer)':
        series_list[s]['type'] = 'exclude'
    
    series_list[s]['object_indices'] = [x for x in range(len(objects_list)) if objects_list[x]['series_id'] == series_list[s]['series_id']]
    try:
        series_list[s]['repetitionTimes'] = [[x for x in objects_list[x]['items'] if x['name'] == 'json'][0]['sidecar']['RepetitionTime'] for x in range(len(objects_list)) if objects_list[x]['series_id'] == series_list[s]['series_id']] 
    except:
        pass        
    
#Push all info to ezBIDS.json
ezBIDS = {"subjects": subjectIDs_info,
          "participantsColumn": participantsColumn,
          "series": series_list,
          "objects": objects_list
          }

#Write out ezBIDS.json
ezBIDS_file_name = 'ezBIDS.json'
with open(ezBIDS_file_name, 'w') as fp: 
    json.dump(ezBIDS, fp, indent=3) 


                

            
                
    
    
    


    
    
    
    
    
    

    
