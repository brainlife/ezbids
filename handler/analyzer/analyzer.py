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
        List of dictionaries containing the AcquisitionDate and ses # (if applicable)
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
        
        #Find subjID from json (some files contain neither PatientName nor PatientID)
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
        
        #Select subjID to display to ezBIDS users
        #Order of importance is: PatientName > PatientID > PatientBirthDate
        if PatientName:
            sub = PatientName
        elif PatientID:
            sub = PatientID
        else:
            sub = PatientBirthDate
        sub = re.sub('[^A-Za-z0-9]+', '', sub)
        
        #Find Acquisition Date & Time
        if 'AcquisitionDateTime' in json_data:
            AcquisitionDate = json_data['AcquisitionDateTime'].split('T')[0]
            AcquisitionTime = json_data['AcquisitionDateTime'].split('T')[-1]
        else:
            AcquisitionDate = None
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
                       'sub': sub,
                       'ses': '',
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
                       'dir': PED,
                       'IntendedFor': 'N/A',
                       'TaskName': '',
                       "include": True,
                       'filesize': filesize,
                       "NumVolumes": volume_count,
                       'error': None,
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
    subjectIDs_info = list({x['sub']:{'sub':x['sub'], 'PatientID':x['PatientID'], 'PatientName':x['PatientName'], 'PatientBirthDate':x['PatientBirthDate'], 'phenotype':{'sex':x['PatientSex'], 'age':x['PatientAge']}} for x in data_list}.values())
    subjectIDs_info = sorted(subjectIDs_info, key = lambda i: i['sub'])
    
    acquisition_dates = list({(x['sub'], x['AcquisitionDate']):{'sub':x['sub'], 'AcquisitionDate':x['AcquisitionDate'], 'ses': ''} for x in data_list}.values())
    acquisition_dates = sorted(acquisition_dates, key = lambda i: i['AcquisitionDate'])
    
    #Insert ses info if applicable
    subj_ses = [[x['sub'], x['AcquisitionDate'], x['ses']] for x in data_list]
    subj_ses = sorted([list(x) for x in set(tuple(x) for x in subj_ses)], key = lambda i: i[1])
    
    for i in np.unique(np.array([x[0] for x in subj_ses])):
        sub_indices = [x for x,y in enumerate(subj_ses) if y[0] == i]
        if len(sub_indices) > 1:
            for j, k in enumerate(sub_indices):
                subj_ses[k][-1] = '0' + str(j+1)
    
    subj_ses = sorted([list(x) for x in set(tuple(x) for x in subj_ses)], key = lambda i: i[1])
    
    for x,y in enumerate(acquisition_dates):
        y['ses'] = subj_ses[x][-1]
        
    #Sort list of dictionaries by subject, AcquisitionDate, SeriesNumber, and json_path
    data_list = sorted(data_list, key=itemgetter('sub', 'AcquisitionDate', 'SeriesNumber', 'json_path'))
    
    #Add session info to data_list, if applicable
    for i in range(len(acquisition_dates)):
        for j in range(len(data_list)):
            if data_list[j]['sub'] == acquisition_dates[i]['sub'] and data_list[j]['AcquisitionDate'] == acquisition_dates[i]['AcquisitionDate']:
                data_list[j]['ses'] = acquisition_dates[i]['ses']
        
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
        if 'SequenceName' in data_list_unique_series[i]['sidecar']:
            SequenceName = data_list_unique_series[i]['sidecar']['SequenceName']
        elif 'ScanningSequence' in data_list_unique_series[i]['sidecar']:
            SequenceName = data_list_unique_series[i]['sidecar']['ScanningSequence']
        else:
            SequenceName = 'N/A'
        
        #Populate some labels fields (based on ReproIn convention)
        if 'sub-' in SD:
            series_entities['sub'] = SD.split('sub-')[-1].split('_')[0]
        else:
            series_entities['sub'] = None
        
        if '_ses-' in SD:
            series_entities['ses'] = SD.split('_ses-')[-1].split('_')[0]
        else:
            series_entities['ses'] = None
            
        if '_run-' in SD:
            series_entities['run'] = SD.split('_run-')[-1].split('_')[0]
        else:
            series_entities['run'] = ''
        
        if '_task-' in SD:
            series_entities['task'] = SD.split('_task-')[-1].split('_')[0]
        else:
            pass
        
        if '_acq-' in SD:
            series_entities['acq'] = SD.split('_acq-')[-1].split('_')[0]
        else:
            series_entities['acq'] = ''
            
        if '_ce-' in SD:
            series_entities['ce'] = SD.split('_ce-')[-1].split('_')[0]
        else:
            series_entities['ce'] = ''
            
        if '_echo-' in SD:
            series_entities['echo'] = SD.split('_echo-')[-1].split('_')[0]
        else:
            series_entities['echo'] = ''
        
        
        #Make easier to find key characters/phrases in SD by removing non-alphanumeric characters and make everything lowercase
        SD = re.sub('[^A-Za-z0-9]+', '', SD).lower()
        
        ### Determine DataTypes and ModalityLabels #######
        # Magnitude/Phasediff and Spin echo (SE) field maps
        if any(x in SD for x in ['fmap', 'fieldmap']) or SequenceName in ['epse2d', 'fm2d2r']:
            data_list_unique_series[i]['DataType'] = 'fmap'
            #Magnitude/Phasediff field maps
            if 'EchoNumber' in data_list_unique_series[i]['sidecar']:
                if data_list_unique_series[i]['EchoNumber'] == 1:
                    data_list_unique_series[i]['ModalityLabel'] = 'magnitude1'
                    data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/magnitude1 because "fmap" or "fieldmap" is in SeriesDescription, and EchoNumber == 1 in metadata. Please modify if incorrect'
                elif data_list_unique_series[i]['EchoNumber'] == 2:
                    if 'PHASE' in data_list_unique_series[i]['ImageType']:
                        data_list_unique_series[i]['ModalityLabel'] = 'phasediff'
                        data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/phasediff because "fmap" or "fieldmap" is in SeriesDescription, and "PHASE" is in the ImageType field of the metadata. Please modify if incorrect'
                    else:
                        data_list_unique_series[i]['ModalityLabel'] = 'magnitude2'
                        data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/magnitude2 because "fmap" or "fieldmap" is in SeriesDescription, and EchoNumber == 2 in metadata. Please modify if incorrect'
            #Spin echo field maps
            else:
                data_list_unique_series[i]['ModalityLabel'] = 'epi'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/epi because "fmap" or "fieldmap" is in SeriesDescription, and does not contain metadata info associated with magnitude/phasediff acquisitions. Please modify if incorrect'
                series_entities['dir'] = data_list_unique_series[i]['dir']
            
        #DWI
        elif any('.bvec' in x for x in data_list_unique_series[i]['paths']):
            #Some "dwi" acquisitions are actually fmap/epi; check for this
            bval = np.loadtxt([x for x in data_list_unique_series[i]['paths'] if 'bval' in x][0])
            if np.max(bval) <= 50 and bval.size < 10:
                data_list_unique_series[i]['DataType'] = 'fmap'
                data_list_unique_series[i]['ModalityLabel'] = 'epi'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be fmap/epi meant for dwi because there are bval & bvec files with the same SeriesNumber, but the max b-values are <= 50 and the number of b-values is less than 10. Please modify if incorrect'
                series_entities['dir'] = data_list_unique_series[i]['dir']
            elif any(x in SD for x in ['trace','fa','adc']) and ('dti' in SD or 'dwi' in SD):
                data_list_unique_series[i]['include'] = False
                data_list_unique_series[i]['error'] = 'Acquisition appears to be a TRACE, FA, or ADC, which are unsupported by ezBIDS and will therefore not be converted'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be TRACE, FA, or ADC because there are bval & bvec files with the same SeriesNumber, and "trace", "fa", or "adc" are in the SeriesDescription. Please modify if incorrect'
            else:
                data_list_unique_series[i]['DataType'] = 'dwi'
                data_list_unique_series[i]['ModalityLabel'] = 'dwi'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be dwi/dwi because there are bval & bvec files with the same SeriesNumber, "dwi" or "dti" is in the SeriesDescription, and it does not appear to be dwi product data. Please modify if incorrect'
                series_entities['dir'] = data_list_unique_series[i]['dir']
        
        elif any(x in SD for x in ['trace','fa','adc']) and 'dti' in SD or 'dwi' in SD:
            data_list_unique_series[i]['include'] = False
            data_list_unique_series[i]['error'] = 'Acquisition appears to be a TRACE, FA, or ADC, which are unsupported by ezBIDS and will therefore not be converted'
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be TRACE, FA, or ADC because there are bval & bvec files with the same SeriesNumber, and "trace", "fa", or "adc" are in the SeriesDescription. Please modify if incorrect'
        
        #Functional bold and phase
        elif any(x in SD for x in ['bold','func','fmri','epi','mri','task']) and 'sbref' not in SD:
            data_list_unique_series[i]['DataType'] = 'func'
            if 'rest' in SD or 'rsfmri' in SD:
                series_entities['task'] = 'rest'
            if 'MOSAIC' and 'PHASE' in data_list_unique_series[i]['ImageType']:
                data_list_unique_series[i]['ModalityLabel'] = 'phase'
                data_list_unique_series[i]['message'] = 'Acquisition is believed to be func/phase because "bold","func","fmri","epi","mri", or"task" is in the SeriesDescription (but not "sbref"), and "MOSAIC" and "PHASE" are in the ImageType field of the metadata. Please modify if incorrect'
            else:
                data_list_unique_series[i]['ModalityLabel'] = 'bold'
                if data_list_unique_series[i]['EchoNumber']:
                    series_entities['echo'] = '0' +  str(data_list_unique_series[i]['EchoNumber'])
            if data_list_unique_series[i]['EchoNumber']:
                series_entities['echo'] = '0' +  str(data_list_unique_series[i]['EchoNumber'])
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be func/bold because "bold","func","fmri","epi","mri", or"task" is in the SeriesDescription (but not "sbref"). Please modify if incorrect'

        #Functional single band reference (sbref)
        elif 'sbref' in SD:
            data_list_unique_series[i]['DataType'] = 'func'
            data_list_unique_series[i]['ModalityLabel'] = 'sbref'
            if 'rest' in SD or 'rsfmri' in SD:
                series_entities['task'] = 'rest'
            if data_list_unique_series[i]['EchoNumber']:
                series_entities['echo'] = '0' + str(data_list_unique_series[i]['EchoNumber'])
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be func/sbref because "sbref" is in the SeriesDescription'
        
        #T1w
        elif any(x in SD for x in ['t1w','tfl3d','mprage']) or 'tfl3d1_16ns' in SequenceName:
            data_list_unique_series[i]['DataType'] = 'anat'
            data_list_unique_series[i]['ModalityLabel'] = 'T1w'
            if data_list_unique_series[i]['EchoNumber']:
                series_entities['echo'] = '0' + str(data_list_unique_series[i]['EchoNumber'])
            data_list_unique_series[i]['message'] = 'Acquisition is believed to be anat/T1w because "t1w","tfl3d","tfl","mprage" is in the SeriesDescription, or "tfl3d1_16ns" is in the SequenceName. Please modify if incorrect'
        
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

        #Localizers or other non-BIDS compatible acquisitions
        elif any(x in SD for x in ['localizer','scout']):
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
            
            
        #Assume not BIDS-compliant acquisition unless user specifies so
        else: 
            data_list_unique_series[i]['include'] = False
            data_list_unique_series[i]['error'] = 'Acquisition cannot be resolved. Please determine whether or not this acquisition should be converted to BIDS'
            data_list_unique_series[i]['message'] = 'Acquisition is unknown because there is not enough adequate information, primarily in the SeriesDescription. Please modify if acquisition is desired for BIDS conversion, otherwise the acqusition will not be converted'
            data_list_unique_series[i]['br_type'] = 'exclude'
            
        if data_list_unique_series[i]['include'] == True:
            data_list_unique_series[i]['br_type'] = data_list_unique_series[i]['DataType'] + '/' + data_list_unique_series[i]['ModalityLabel']
    
        #Combine info above into dictionary, which will be displayed to user through the UI
        series_info = {"SeriesDescription": data_list_unique_series[i]['SeriesDescription'],
                        "SeriesNumber": data_list_unique_series[i]['SeriesNumber'],
                        'series_id': data_list_unique_series[i]['series_id'],
                        'EchoTime': data_list_unique_series[i]['EchoTime'],
                        'ImageType': data_list_unique_series[i]['ImageType'],
                        'MultibandAccelerationFactor': data_list_unique_series[i]['MultibandAccelerationFactor'],
                        "entities": series_entities,
                        "type": data_list_unique_series[i]['br_type'],
                        "message": data_list_unique_series[i]['message'],
                        "repetitionTimes": [],
                        "object_indices": []
                        }
        series_list.append(series_info)
        print('Unique data acquisition file {}, Series Description {}, was determined to be {}'.format(data_list_unique_series[i]['nifti_path'], data_list_unique_series[i]['SeriesDescription'], data_list_unique_series[i]['br_type']))
        print('')
        print('')

    return series_list


def identify_objects_info(sub_protocol, series_list, series_seriesID_list):
    '''
    Takes list of dictionaries with key and unique information, and uses it to 
    determine the DataType and Modality labels of the unique acquisitions. 
    Other information (e.g. run, acq, ce) will be determined if the data follows 
    the ReproIn naming convention for SeriesDescriptions.

    Parameters
    ----------
    sub_protocol: list
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
    sub_protocol: list
        Same as above but with updated information
    '''
    func_sbref_run = 1
    func_phase_run = 1
    bold_run = 1
    dwi_run = 1
    fmap_se_run = 1
    fmap_magphase_run = 1
    objects_entities_list = []
    series_func_list = []
    
    for p in range(len(sub_protocol)):
        if p == 0:
            protocol_index = 0
            
        sub_protocol[p]['protocol_index'] = protocol_index
        protocol_index += 1
        sub_protocol[p]['headers'] = str(nib.load(sub_protocol[p]['nifti_path']).header).splitlines()[1:]
                
        
        #Weird issue where data array is RGB instead on intger
        object_img_array = nib.load(sub_protocol[p]['nifti_path']).dataobj
        if object_img_array.dtype not in ['<i2', '<u2']:
            sub_protocol[p]['include'] = False
            sub_protocol[p]['error'] = 'The data array is for this acquisition is improper, likely suggesting some issue with the corresponding DICOMS'
            sub_protocol[p]['message'] = sub_protocol[p]['error']
        else:
            if sub_protocol[p]['NumVolumes'] > 1:
                object_img_array = nib.load(sub_protocol[p]['nifti_path']).dataobj[..., 1]
            else:
                object_img_array =nib.load(sub_protocol[p]['nifti_path']).dataobj[:]
                    
            if not os.path.isfile('{}.png'.format(sub_protocol[p]['nifti_path'][:-7])):            
                
                slice_x = object_img_array[floor(object_img_array.shape[0]/2), :, :]
                slice_y = object_img_array[:, floor(object_img_array.shape[1]/2), :]
                slice_z = object_img_array[:, :, floor(object_img_array.shape[2]/2)]
                fig, axes = plt.subplots(1,3)
                for i, slice in enumerate([slice_x, slice_y, slice_z]):
                    axes[i].imshow(slice.T, cmap="gray", origin="lower")
                    axes[i].axis('off')
                plt.savefig('{}.png'.format(sub_protocol[p]['nifti_path'][:-7]), bbox_inches='tight')
            
        index = series_seriesID_list.index(sub_protocol[p]['series_id'])
        objects_entities = {'sub': '', 'ses': '', 'run': '', 'acq': '', 'ce': '', 'echo': ''}
        
        #Port series level information down to the object level
        sub_protocol[p]['include'] = data_list_unique_series[index]['include']
        sub_protocol[p]['DataType'] = data_list_unique_series[index]['DataType']
        sub_protocol[p]['ModalityLabel'] = data_list_unique_series[index]['ModalityLabel']
        sub_protocol[p]['br_type'] = data_list_unique_series[index]['br_type']
        sub_protocol[p]['error'] = data_list_unique_series[index]['error']
        sub_protocol[p]['sub'] = subjects[s]
            
        if 'run' in series_list[index]['entities'] and series_list[index]['entities']['run']:
            objects_entities['run'] = series_list[index]['entities']['run']
        if 'task' in series_list[index]['entities'] and series_list[index]['entities']['task']:
            objects_entities['task'] = series_list[index]['entities']['task']
            sub_protocol[p]['TaskName'] = series_list[index]['entities']['task']
        if 'acq' in series_list[index]['entities'] and series_list[index]['entities']['acq']:
            objects_entities['acq'] = series_list[index]['entities']['acq']
        if 'ce' in series_list[index]['entities'] and series_list[index]['entities']['ce']:
            objects_entities['ce'] = series_list[index]['entities']['ce']
        if 'echo' in series_list[index]['entities'] and series_list[index]['entities']['echo']:
            objects_entities['echo'] = series_list[index]['entities']['echo']
        
        #Determine other important BIDS information (i.e. run, dir, etc) for specific acquisitions
        #T1w
        if sub_protocol[p]['br_type'] == 'anat/T1w' and sub_protocol[p]['include'] == True:
            #non-normalized T1w images that have poor CNR, so best to not have in BIDS if there's an actual good T1w available
            if 'NORM' not in sub_protocol[p]['ImageType']:
                # index_next = series_seriesID_list.index(sub_protocol[p+1]['series_id'])
                # sub_protocol[p+1]['br_type'] = data_list_unique_series[index_next]['br_type']
                if p+1 == len(sub_protocol):
                    sub_protocol[p]['include'] = True 
                    sub_protocol[p]['error'] = None
                elif sub_protocol[p+1]['br_type'] == 'anat/T1w' and 'NORM' not in sub_protocol[p+1]['ImageType']:
                    sub_protocol[p]['include'] = True 
                    sub_protocol[p]['error'] = None
                elif sub_protocol[p+1]['br_type'] != 'anat/T1w':
                    sub_protocol[p]['include'] = True 
                    sub_protocol[p]['error'] = None
                else:
                    sub_protocol[p]['include'] = False  
                    sub_protocol[p]['error'] = 'Acquisition is a poor resolution T1w (non-normalized); Please check to see if this T1w acquisition should be converted to BIDS. Otherwise, this object will not be included in the BIDS output'
        
        #Functional bold
        elif sub_protocol[p]['br_type'] == 'func/bold':
            #Instances where functional bold acquisitions have less than 30 volumes (probably a restart/failure occurred, or some kind of non-BIDS test)
            if sub_protocol[p]['NumVolumes'] < 30:
                sub_protocol[p]['include'] = False
                sub_protocol[p]['error'] = 'Functional run only contains {} volumes; ezBIDS flags functional runs with under 30 volumes. Please check to see whether this should be excluded or not from BIDS conversion'.format(sub_protocol[p]['NumVolumes'])
            else:
                if objects_entities['run'] == '':
                    if not len([x for x in series_func_list if x[0] == sub_protocol[p]['series_id']]):
                        series_func_list.append([sub_protocol[p]['series_id'], 1])
                        bold_run = 1
                        sub_protocol[p]['bold_run'] = '01'
                    else:
                        func_index = [x for x, y in enumerate(series_func_list) if y[0] == sub_protocol[p]['series_id']][0]
                        series_func_list[func_index][1] += 1
                        bold_run = series_func_list[func_index][1]
                        
                    if bold_run < 10:
                        sub_protocol[p]['bold_run'] = '0' + str(bold_run)
                    else:
                        sub_protocol[p]['bold_run'] = str(bold_run)
                        
                    objects_entities['run'] = sub_protocol[p]['bold_run']
                else:
                    sub_protocol[p]['bold_run'] = objects_entities['run']
                
        #Functional phase
        elif sub_protocol[p]['br_type'] == 'func/phase':
            if objects_entities['run'] == '':
                if not len([x for x in series_func_list if x[0] == sub_protocol[p]['series_id']]):
                    series_func_list.append([sub_protocol[p]['series_id'], 1])
                    func_phase_run = 1
                    sub_protocol[p]['func_phase_run'] = '01'
                else:
                    func_index = [x for x, y in enumerate(series_func_list) if y[0] == sub_protocol[p]['series_id']][0]
                    series_func_list[func_index][1] += 1
                    func_phase_run = series_func_list[func_index][1]
                    
                if func_phase_run < 10:
                    sub_protocol[p]['func_phase_run'] = '0' + str(func_phase_run)
                else:
                    sub_protocol[p]['func_phase_run'] = str(func_phase_run)
                    
                objects_entities['run'] = sub_protocol[p]['func_phase_run']
            else:
                sub_protocol[p]['func_phase_run'] = objects_entities['run']
                    
        
        #Functional single band reference (sbref)
        elif sub_protocol[p]['br_type'] == 'func/sbref':
            if p+1 < len(sub_protocol):
                index_next = series_seriesID_list.index(sub_protocol[p+1]['series_id'])
                sub_protocol[p+1]['br_type'] = data_list_unique_series[index_next]['br_type']
                
            #Rare instances where sbref is not followed by functional bold
            if sub_protocol[p+1]['br_type'] != 'func/bold':
                sub_protocol[p]['include'] = False
                sub_protocol[p]['error'] = 'Single band reference (sbref) acquisition is not immediately followed by a functional bold acquisition that is being converted to BIDS. This object will not be included in the BIDS output'
                
            #Set include to False if functional bold after it has less than 30 volumes, which will cause it to not be converted to BIDS
            elif nib.load(sub_protocol[p+1]['nifti_path']).shape[3] < 30:
                sub_protocol[p]['include'] = False
                sub_protocol[p]['error'] = 'Functional bold acquisition following this sbref contains less than 30 volumes, therefore BIDS conversion for this acqusition (and the preceding sbref) not recommended.'
            else:    
                if objects_entities['run'] == '':
                    if not len([x for x in series_func_list if x[0] == sub_protocol[p]['series_id']]):
                        series_func_list.append([sub_protocol[p]['series_id'], 1])
                        func_sbref_run = 1
                        sub_protocol[p]['func_sbref_run'] = '01'
                    else:
                        func_index = [x for x, y in enumerate(series_func_list) if y[0] == sub_protocol[p]['series_id']][0]
                        series_func_list[func_index][1] += 1
                        func_sbref_run = series_func_list[func_index][1]
                        
                    if func_sbref_run < 10:
                        sub_protocol[p]['func_sbref_run'] = '0' + str(func_sbref_run)
                    else:
                        sub_protocol[p]['func_sbref_run'] = str(func_sbref_run)
                        
                    objects_entities['run'] = sub_protocol[p]['func_sbref_run']
                else:
                    sub_protocol[p]['func_sbref_run'] = objects_entities['run']
                
        #DWI
        elif sub_protocol[p]['br_type'] == 'dwi/dwi':
            if dwi_run < 10:
                sub_protocol[p]['dwi_run'] = '0' + str(dwi_run)
            else:
                sub_protocol[p]['dwi_run'] = str(dwi_run)
            objects_entities['run'] = sub_protocol[p]['dwi_run']
            objects_entities['dir'] = sub_protocol[p]['dir']
            dwi_run +=1
        
        #Spin echo fmaps
        elif sub_protocol[p]['br_type'] == 'fmap/epi':
            objects_entities['dir'] = sub_protocol[p]['dir']    
                    
        objects_entities_list.append(objects_entities)
        
    #Add run number to anatomicals that have multiple acquisitions
    #Not ideal to use run #'s for anatomical acquisitions, but best solution for now
    t1w_index = [x['protocol_index'] for x in sub_protocol if x['include'] == True and x['br_type'] == 'anat/T1w']
    t2w_index = [x['protocol_index'] for x in sub_protocol if x['include'] == True and x['br_type'] == 'anat/T2w']
    flair_index = [x['protocol_index'] for x in sub_protocol if x['include'] == True and x['br_type'] == 'anat/FLAIR']    
    
    if len(t1w_index) > 1:
        t1w_run = 1
        for t1w in t1w_index:
            objects_entities_list[t1w]['run'] = '0' + str(t1w_run)
            t1w_run += 1
    
    if len(t2w_index) > 1:        
        t2w_run = 1
        for t2w in t2w_index:
            objects_entities_list[t2w]['run'] = '0' + str(t2w_run)
            t2w_run += 1
            
    if len(flair_index) > 1:        
        flair_run = 1
        for flair in flair_index:
            objects_entities_list[flair]['run'] = '0' + str(flair_run)
            flair_run += 1
            
    # #If object-level entitites match series-level entities, make object-level entities blank
    # check = [x['entities'] for x in series_list if x['series_id'] == sub_protocol[p]['series_id']][0]
    # try:
    #     if objects_entities_list[p]['dir'] == check['dir']:
    #         objects_entities_list[p]['dir'] == ''
    # except:
    #     pass
                
    return sub_protocol, objects_entities_list
    

def fmap_intended_for(sub_protocol, total_objects_indices):
    '''
    Determine IntendedFor fields for fmap acquisitions 
    
    Parameters
    ----------
    sub_protocol: list
        List of dictionary, containing pertinent information needed 
        for the UI side of ezBIDS
    
    Returns
    ----------
    sub_protocol: list
        Same as above, but with updated information from the checks
    '''
    
    br_types = [sub_protocol[x]['br_type'] for x in range(len(sub_protocol))]
    include = [sub_protocol[x]['include'] for x in range(len(sub_protocol))]
    errors = [sub_protocol[x]['error'] for x in range(len(sub_protocol))]
    messages = [sub_protocol[x]['message'] for x in range(len(sub_protocol))]
    phase_encoding_directions = [sub_protocol[x]['dir'] for x in range(len(sub_protocol))]
    section_indices = [x for x, y in enumerate(br_types) if x == 0 or ('localizer' in y and 'localizer' not in br_types[x-1])]
    total_objects_indices = total_objects_indices
    
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
            bold_indices = [total_objects_indices+k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'func/bold' and include[k+x] == True]
            dwi_indices = [total_objects_indices+k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'dwi/dwi' and include[k+x] == True]
            non_fmap_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if 'fmap' not in y]
            
            if y == 'fmap/epi' and 'max b-values' not in messages[k+x]:
                fmap_se_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and 'max b-values' not in messages[k+x]]
                
                #If no func/bold acquisitions in section then the fmap/epi in this section are pointless, therefore won't be converted to BIDS
                if len(bold_indices) == 0:
                    for fm in fmap_se_indices:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = 'No valid func/bold objects found in section. This object will not be included in the BIDS output'
                        sub_protocol[fm]['error'] = errors[fm]
                    
                #Only one fmap/epi acquisition in section. Can't be converted b/c need pair
                if len(fmap_se_indices) == 1:
                    for fm in fmap_se_indices:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = 'Only one spin echo field map found; need pair. This object will not be included in the BIDS output'
                        sub_protocol[fm]['error'] = errors[fm]
                
                #If more than two fmap/epi acquisitions, only accept most recent pair in section
                if len(fmap_se_indices) > 2:
                    for fm in fmap_se_indices[:-2]:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = 'Multiple spin echo pairs detected in section; only selecting last pair for BIDS conversion. The other pair objects will not be included in the BIDS output'
                        sub_protocol[fm]['error'] = errors[fm]
                        
                #Re-determine the fmap/epi indices in light of the checks above
                fmap_se_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and include[k+x] == True]
                
                #If fmap/epi pair don't have opposing phase encoding directions, won't be converted to BIDS
                if len(fmap_se_indices) == 2:
                    fmap_se_PEDs = [y for x,y in enumerate(phase_encoding_directions) if k+x in fmap_se_indices]
                    if fmap_se_PEDs[0][::-1] != fmap_se_PEDs[1]:
                        for fm in fmap_se_indices:
                            include[fm] = False
                            sub_protocol[fm]['include'] = include[fm]
                            errors[fm] = 'Spin echo fmap pair does not have opposite phase encoding directions. This object will not be included in the BIDS output'
                            sub_protocol[fm]['error'] = errors[fm]
                
                #Re-determine the fmap/epi indices again
                fmap_se_indices = [k+x for x,y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and include[k+x] == True]

                if len(fmap_se_indices) == 2:
                    for fm in fmap_se_indices:
                        sub_protocol[fm]['IntendedFor'] = bold_indices
                        
           
            #Magnitude/Phasediff fmaps
            elif y in ['fmap/magnitude1','fmap/magnitude2','fmap/phasediff']:
                #Remove duplicate magnitude/phasediff fmaps. Only the last three in each section will be kept
                fmap_magphase_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y in ['fmap/magnitude1', 'fmap/magnitude2', 'fmap/phasediff']]
                
                #If no func/bold acquisitions in section then the magnitude/phasediff in this section are pointless, therefore won't be converted to BIDS
                if len(bold_indices) == 0:
                    for fm in fmap_magphase_indices:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = 'No valid func/bold objects found in section. This object will not be included in the BIDS output'
                        sub_protocol[fm]['error'] = errors[fm]
                  
                #Only one magnitude/phasediff acquisition in section. Can't be converted
                if len(fmap_magphase_indices) == 1:
                    for fm in fmap_magphase_indices:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = 'Need pair for magnitude/phasediff field maps. This object will not be included in the BIDS output'
                        sub_protocol[fm]['error'] = errors[fm]
                        
                #If more than three magnitude/phasediff acquisitions, only accept most recent three in section
                if len(fmap_magphase_indices) > 3:
                    for fm in fmap_magphase_indices[:-3]:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = 'More than three magnitude/phasediff field map acquisitions found in section. Only selecting most recent three. Others will not be included in the BIDS output'
                        sub_protocol[fm]['error'] = errors[fm]
                        
                #Re-determine the magnitude/phasediff indices in light of the checks above
                fmap_magphase_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y in ['fmap/magnitude1', 'fmap/magnitude2', 'fmap/phasediff'] and include[k+x] != False]        
                
                if len(fmap_magphase_indices) == 3:
                    for fm in fmap_magphase_indices:
                        sub_protocol[fm]['IntendedFor'] = bold_indices
                        
            
            #Spin-echo fmaps for DWI
            elif y == 'fmap/epi' and 'max b-values' in messages[k+x]:
                fmap_se_dwi_indices = [k+x for x, y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and 'max b-values' in messages[k+x]]
            
                #If no dwi/dwi acquisitions in section then the fmap/epi_dwi in this section are pointless, therefore won't be converted to BIDS
                if len(dwi_indices) == 0:
                    for fm in fmap_se_dwi_indices:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = 'No valid dwi/dwi objects found in section. This object will not be included in the BIDS output'
                        sub_protocol[fm]['error'] = errors[fm]
                  
                #If more than one fmap/epi_dwi acquisitions, only accept most recent one in section
                if len(fmap_se_dwi_indices) > 1:
                    for fm in fmap_se_dwi_indices[:-1]:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = 'More than one dwi-specific field maps detected in section; only selecting last one for BIDS conversion. Other object will not be included in the BIDS output'
                        sub_protocol[fm]['error'] = errors[fm]
                
                #Re-determine the fmap/epi_dwi indices in light of the checks above
                fmap_se_dwi_indices = [total_objects_indices+k+x for x,y in enumerate(br_types[section_start:section_end]) if y == 'fmap/epi' and 'max b-values' in messages[k+x] and include[k+x] != False]
                if len(fmap_se_dwi_indices) == 1:
                    for fm in fmap_se_dwi_indices:
                        sub_protocol[fm]['IntendedFor'] = dwi_indices
            else:
                pass
            
            #Add IntendedFor to all non-fmap acquisitions
            #This allows IntendedFor fields to auto-fill if user changes datatype on UI
            for nfm in non_fmap_indices:
                if 'dwi' in sub_protocol[nfm]['br_type']:
                    sub_protocol[nfm]['IntendedFor'] = dwi_indices
                else:
                    sub_protocol[nfm]['IntendedFor'] = bold_indices
                        
    return sub_protocol    


def build_objects_list(sub_protocol, objects_entities_list):
    '''
    Create ezBIDS.json file, which provides all information used by the UI
    to display to users
    
    Parameters
    ----------
    sub_protocol: list
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
    for i in range(len(sub_protocol)):
        
        #Provide log output for acquisitions not deemed appropriate for BIDS conversion
        if sub_protocol[i]['include'] == False:
            print('* {} not recommended for BIDS conversion: {}'.format(sub_protocol[i]['SeriesDescription'], sub_protocol[i]['error']))
        
        #Remove identifying information from sidecars
        remove_fields = ['SeriesInstanceUID', 'StudyInstanceUID', 
                         'ReferringPhysicianName', 'StudyID', 'PatientName', 
                         'PatientID', 'AccessionNumber', 'PatientBirthDate', 
                         'PatientSex', 'PatientWeight']
        for remove in remove_fields:
            if remove in sub_protocol[i]['sidecar']:
                del sub_protocol[i]['sidecar'][remove]
                
        #Make items list (part of objects list)
        items = []
        for item in sub_protocol[i]['paths']:
            if '.bval' in item:
                items.append({'path':item, 'name':'bval'})
            elif '.bvec' in item:
                items.append({'path':item, 'name':'bvec'})
            elif '.json' in item:
                items.append({'path':item, 'name':'json', 'sidecar':sub_protocol[i]['sidecar']})
            elif '.nii.gz' in item:
                items.append({'path':item, 'name':'nii.gz', 'headers':sub_protocol[i]['headers']})

        if sub_protocol[i]['error']:
            sub_protocol[i]['error'] = [sub_protocol[i]['error']]
            
        #Objects-level info for ezBIDS.json
        objects_info = {"include": sub_protocol[i]['include'],
                    "series_id": sub_protocol[i]['series_id'],
                    "PatientName": sub_protocol[i]['PatientName'],
                    "PatientID": sub_protocol[i]['PatientID'],
                    "PatientBirthDate": sub_protocol[i]['PatientBirthDate'],
                    "AcquisitionDate": sub_protocol[i]['AcquisitionDate'],
                    'SeriesNumber': sub_protocol[i]['sidecar']['SeriesNumber'],
                    "pngPath": '{}.png'.format(sub_protocol[i]['nifti_path'][:-7]),
                    "IntendedFor": sub_protocol[i]['IntendedFor'],
                    "entities": objects_entities_list[i],
                    "items": items,
                    "analysisResults": {
                        "NumVolumes": sub_protocol[i]['NumVolumes'],
                        "errors": sub_protocol[i]['error'],
                        "filesize": sub_protocol[i]['filesize']
                    },
                    "paths": sub_protocol[i]['paths']
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
dir_list = pd.read_csv('list', header=None)

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
subjects = [acquisition_dates[x]['sub'] for x in range(len(acquisition_dates))]
sessions = [acquisition_dates[x]['ses'] for x in range(len(acquisition_dates))]
series_seriesID_list = [series_list[x]['series_id'] for x in range(len(series_list))]

#Loop through all unique subjectIDs
for s in range(len(acquisition_dates)):
    
    if acquisition_dates[s]['ses'] == '':
        print('Beginning conversion process for subject {} protocol acquisitions'.format(acquisition_dates[s]['sub']))
        print('-------------------------------------------------------------------')
        print('')
     
    else:
        print('Beginning conversion process for subject {}, session {} protocol acquisitions'.format(acquisition_dates[s]['sub'], acquisition_dates[s]['ses']))
        print('-------------------------------------------------------------------')
        print('')
    
    #Get initial sub_protocol list from subsetting by subject/session
    sub_protocol = [x for x in data_list if x['sub'] == acquisition_dates[s]['sub'] and x['ses'] == acquisition_dates[s]['ses']]
    
    #Update sub_protocol based on object-level checks
    sub_protocol, objects_entities_list = identify_objects_info(sub_protocol, series_list, series_seriesID_list)
    
    #update sub_protocol based on fmap IntendedFor checks
    sub_protocol = fmap_intended_for(sub_protocol, total_objects_indices)
    
    #Build objects_list
    objects_list = build_objects_list(sub_protocol, objects_entities_list)
    
    total_objects_indices += len(sub_protocol)
    
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
          "sessions": acquisition_dates,
          "participantsColumn": participantsColumn,
          "series": series_list,
          "objects": objects_list
          }

#Write out ezBIDS.json
ezBIDS_file_name = 'ezBIDS.json'
with open(ezBIDS_file_name, 'w') as fp: 
    json.dump(ezBIDS, fp, indent=3) 


                

            
                
    
    
    


    
    
    
    
    
    

    
