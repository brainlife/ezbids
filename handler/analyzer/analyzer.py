#!/usr/bin/env python3
"""
Created on Fri Jun 26 08:37:56 2020

@author: dlevitas
"""
from __future__ import division
import os, sys, json, warnings
import pandas as pd
import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
from operator import itemgetter
from math import floor

warnings.filterwarnings("ignore")

data_dir = sys.argv[1]
os.chdir(data_dir)

print('########################################')
print('Beginning conversion process of dataset')
print('########################################')
print('')

#def extractor():

def show_slices(slices):
    fig, axes = plt.subplots(1, len(slices))
    for i, slice in enumerate(slices):
        axes[i].imshow(slice.T, cmap="gray", origin="lower")
    plt.imsave()
    
#Load list generated from UI, and organize the nifti/json files by their series number    
dir_list = pd.read_csv('list', header=None)
dir_list.columns = ['path']
#Remove Philips proprietary files in dir_list if they exist
dir_list = dir_list[~dir_list.path.str.contains('PARREC|Parrec|parrec')].reset_index(drop=True)    

#Get nifti, json (i.e. sidecar), and SeriesNumber (SN) file lists
json_list = [x for x in dir_list['path'] if '.json' in x and 'ezbids' not in x]
nifti_list = [x for x in dir_list['path'] if '.nii.gz' in x or '.bval' in x or '.bvec' in x]

#participantsColumn portion of ezBIDS.json
participantsColumn = {"sex": {"LongName": "gender", "Description": "generic gender field", "Levels": {"M": "male", "F": "female"}},
                      "age": {"LongName": "age", "Units": "years"}}

#Create list for later
data_list = []

#Parse through nifti and sidecar data for pertinent information
print('Determining unique acquisitions in dataset')
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
        
    #Nifti (and bval/bvec) file(s) associated with specific sidecar
    nifti_paths_for_json = [x for x in nifti_list if json_list[j][:-4] in x]
    
    #Nifti file size
    filesize = os.stat(nifti_paths_for_json[0]).st_size
    
    #Find StudyID from sidecar
    if 'StudyID' in json_data:
        studyID = json_data['StudyID']
    else:
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
    if 'PatientSex' in json_data: 
        PatientSex = json_data['PatientSex']
    else:
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
        MultibandAccelerationFactor = -999
        
    #Find how many volumes are in sidecar's corresponding nifti file
    try:
        volume_count = nib.load(json_list[j][:-4] + 'nii.gz').shape[3]
    except:
        volume_count = 1
        
    #Relative paths of sidecar and nifti files (per SeriesNumber)
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
                   'EchoTime': EchoTime,
                   'InversionTime': InversionTime,
                   'MultibandAccelerationFactor': MultibandAccelerationFactor,
                   'DataType': '',
                   'ModalityLabel': '',
                   'series_id': 0,
                   'sbref_run': '',
                   'bold_run': '',
                   'dwi_run': '',
                   'fmap_se_run': '',
                   'fmap_magphase_run': '',
                   'acq': '',
                   'ce': '',
                   'run': '',
                   'dir': PED,
                   'TaskName': 'rest',
                   "include": True,
                   'filesize': filesize,
                   "VolumeCount": volume_count,
                   'error': None,
                   'br_type': '',
                   'nifti_path': [x for x in nifti_paths_for_json if '.nii.gz' in x][0],
                   'json_path': json_list[j],
                   'paths': paths,
                   'pngPath': '',
                   'nifti_name': nifti_name,
                   'json_name': json_name,
                   'headers': '',
                   'protocol_index': 0,
                   'fmap_dwi_check': 0,
                   'sidecar':json_data
                   }
    data_list.append(mapping_dic)
    
data_list = sorted(data_list, key=itemgetter('sub', 'SeriesNumber'))
subjectIDs_info = list({x['sub']:{'sub':x['sub'], 'PatientID':x['PatientID'], 'PatientName':x['PatientName'], 'PatientBirthDate':x['PatientBirthDate']} for x in data_list}.values())
acquisition_dates = list({x['sub']:{'AcquisitionDate':x['AcquisitionDate'], 'ses': ''} for x in data_list}.values())

#Create series level and object level dictionaries based on unique SeriesDescription and/or SeriesNumber
# data_list_unique_objects = []
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


#SERIES LEVEL
series_list = []
#Determine DataType and ModalityLabel of series list acquisitions
for i in range(len(data_list_unique_series)):
    
    series_entities = {}
    SD = data_list_unique_series[i]['SeriesDescription']
    EchoTime = data_list_unique_series[i]['EchoTime']
    TR = data_list_unique_series[i]['RepetitionTime']
    try:
        SequenceName = data_list_unique_series[i]['sidecar']['SequenceName']
    except:
        SequenceName = data_list_unique_series[i]['sidecar']['ScanningSequence']
    
    
    #Populate some labels fields (based on ReproIn convention)
    if 'sub-' in SD:
        series_entities['sub'] = SD.split('sub-')[-1].split('_')[0]
    else:
        # series_entities['sub'] = data_list_unique_series[i]['sub']
        series_entities['sub'] = None
    
    if '_ses-' in SD:
        series_entities['ses'] = SD.split('_ses-')[-1].split('_')[0]
    else:
        # series_entities['ses'] = data_list_unique_series[i]['SessionID']
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
    
    
    #First use values from fields such as TR, TE, TI, etc to determine DataType and/or ModalityLabel
    if data_list_unique_series[i]['VolumeCount'] > 1: #DWI, functional, functional phase, and SE fmap are 4D
        #DWI
        if any(x in SD for x in ['DWI','dwi','DTI','dti']) or 'ep_b' in SequenceName:
            if data_list_unique_series[i]['VolumeCount'] < 10: #Probably field map meant for dwi acquisition instead. Based on number of volumes
                data_list_unique_series[i]['DataType'] = 'fmap'
                data_list_unique_series[i]['ModalityLabel'] = 'epi'
                data_list_unique_series[i]['fmap_dwi_check'] = 1
            else:
                data_list_unique_series[i]['DataType'] = 'dwi'
                data_list_unique_series[i]['ModalityLabel'] = 'dwi'
                
            series_entities['dir'] = data_list_unique_series[i]['dir']
            
        #Functional
        elif any(x in SD for x in ['BOLD','Bold','bold','FUNC','Func','func','FMRI','fMRI','fmri','EPI']) and ('SBRef' not in SD or 'sbref' not in SD):
            data_list_unique_series[i]['DataType'] = 'func'
            if data_list_unique_series[i]['EchoNumber']:
                data_list_unique_series[i]['ModalityLabel'] = 'multiecho'
                series_entities['echo'] = data_list_unique_series[i]['EchoNumber']
            else:
                data_list_unique_series[i]['ModalityLabel'] = 'bold'
                        
        #Spin echo (SE) field maps
        elif any(x in SD for x in ['fmap','FieldMap','fieldmap','SE']) or 'epse2d' in SequenceName or 'fm2d2r' in SequenceName:
            data_list_unique_series[i]['DataType'] = 'fmap'
            data_list_unique_series[i]['ModalityLabel'] = 'epi'
            series_entities['dir'] = data_list_unique_series[i]['dir']
            
        #Can't determine acquisition type
        else:
            #Multiband factor would indicate functional bold
            if data_list_unique_series[i]['MultibandAccelerationFactor'] > 0:
                data_list_unique_series[i]['DataType'] = 'func'
                data_list_unique_series[i]['ModalityLabel'] = 'bold'
                
            #Blanket statement that acquisitions with a TR of 3 sec or less are functional bold
            elif data_list_unique_series[i]['RepetitionTime'] <= 3:
                data_list_unique_series[i]['DataType'] = 'func'
                data_list_unique_series[i]['ModalityLabel'] = 'bold'
                
            #Assume not BIDS unless user specifies so
            else: 
                data_list_unique_series[i]['include'] = False
                data_list_unique_series[i]['error'] = 'Acquisition cannot be resolved. Please determine if this acquisition should be converted to BIDS'
    
            
    else: #localizers, sbref, T1w, T2w, FLAIR, magnitude/phasediff fmap are 3D
        #Localizers or other non-BIDS compatible acquisitions
        if any(x in SD for x in ['LOCALIZER','Localizer','localizer','SCOUT','Scout','scout']):
            data_list_unique_series[i]['include'] = False
            data_list_unique_series[i]['error'] = 'Acquisition appears to be a localizer or other non-compatible BIDS acquisition'

        #T1w
        elif any(x in SD for x in ['T1W','T1w','t1w','tfl3d','tfl','mprage','MPRAGE']) or 'tfl3d1_16ns' in SequenceName:
            data_list_unique_series[i]['DataType'] = 'anat'
            if data_list_unique_series[i]['EchoNumber']:
                data_list_unique_series[i]['ModalityLabel'] = 'multiecho'
                series_entities['echo'] = data_list_unique_series[i]['EchoNumber']
            else:
                data_list_unique_series[i]['ModalityLabel'] = 'T1w'
        
        #FLAIR
        elif any(x in SD for x in ['FLAIR','Flair','flair','t2_space_da-fl']):
            data_list_unique_series[i]['DataType'] = 'anat'
            data_list_unique_series[i]['ModalityLabel'] = 'FLAIR'
            
        #T2w
        elif any(x in SD for x in ['T2W','T2w','t2w']):
            data_list_unique_series[i]['DataType'] = 'anat'
            data_list_unique_series[i]['ModalityLabel'] = 'T2w'
        
        #Single band reference (sbref)
        elif any(x in SD for x in ['SBRef','sbref']):
            data_list_unique_series[i]['DataType'] = 'func'
            data_list_unique_series[i]['ModalityLabel'] = 'sbref'
        
        #Magnitude/Phasediff field maps
        elif 'EchoNumber' in data_list_unique_series[i]['sidecar']: #Probably magnitude/phasediff
            data_list_unique_series[i]['DataType'] = 'fmap'
            if data_list_unique_series[i]['EchoNumber'] == 1:
                data_list_unique_series[i]['ModalityLabel'] = 'magnitude1'
            else:
                if 'PHASE' in data_list_unique_series[i]['ImageType']:
                    data_list_unique_series[i]['ModalityLabel'] = 'phasediff'
                else:
                    data_list_unique_series[i]['ModalityLabel'] = 'magnitude2'
            
        #Do another pass if the SeriesDescription information isn't insightful
        else:
            if EchoTime < 10: #Probably T1w
                data_list_unique_series[i]['DataType'] = 'anat'
                data_list_unique_series[i]['ModalityLabel'] = 'T1w'
            
            elif data_list_unique_series[i]['InversionTime'] is not None and data_list_unique_series[i]['InversionTime'] > 0: #Probably FLAIR
                data_list_unique_series[i]['DataType'] = 'anat'
                data_list_unique_series[i]['ModalityLabel'] = 'FLAIR'
            
            elif EchoTime > 100: #Probably T2w
                data_list_unique_series[i]['DataType'] = 'anat'
                data_list_unique_series[i]['ModalityLabel'] = 'T2w'
            
            elif (EchoTime > 10 and EchoTime < 100): #Probably sbref
                data_list_unique_series[i]['DataType'] = 'func'
                data_list_unique_series[i]['ModalityLabel'] = 'sbref'
            
            #Can't determine acquisition type. Assume it's not BIDS unless user specifies so
            else:
                data_list_unique_series[i]['include'] = False
                data_list_unique_series[i]['error'] = 'Acquisition cannot be resolved. Please determine if this acquisition should be converted to BIDS'
    
    if data_list_unique_series[i]['DataType'] == '' and data_list_unique_series[i]['ModalityLabel'] == '':
        data_list_unique_series[i]['br_type'] = 'N/A'
    else:
        data_list_unique_series[i]['br_type'] = data_list_unique_series[i]['DataType'] + '/' + data_list_unique_series[i]['ModalityLabel']
        

    series_info = {"SeriesDescription": data_list_unique_series[i]['SeriesDescription'],
                    "SeriesNumber": data_list_unique_series[i]['SeriesNumber'],
                    'series_id': data_list_unique_series[i]['series_id'],
                    "entities": series_entities,
                    "type": data_list_unique_series[i]['br_type'],
                    "unique_TRs": [],
                    "png_objects_indices": []
                    }
    series_list.append(series_info)
    print('Unique data acquisition file {}, Series Description {}, was determined to be {}'.format(data_list_unique_series[i]['nifti_path'][2:], data_list_unique_series[i]['SeriesDescription'], data_list_unique_series[i]['br_type']))
    
print('')
print('')
#OBJECTS LEVEL
objects_list = []
subjects = [subjectIDs_info[x]['sub'] for x in range(len(subjectIDs_info))]
series_seriesID_list = [series_list[x]['series_id'] for x in range(len(series_list))]
data_list_index = -1
for s in range(len(subjects)):
    
    print('Beginning conversion process for subject {} individual acquisitions'.format(subjects[s]))
    print('-------------------------------------------------------------------')
    print('')
    
    sub_protocol = [x for x in data_list if x['sub'] == subjects[s]]
    sbref_run = 1
    bold_run = 1
    dwi_run = 1
    fmap_se_run = 1
    fmap_magphase_run = 1
    objects_entities_list = []
    
    for p in range(len(sub_protocol)):
        if p == 0:
            protocol_index = 0
            
        sub_protocol[p]['protocol_index'] = protocol_index
        data_list_index += 1
        protocol_index += 1
        sub_protocol[p]['headers'] = str(nib.load(sub_protocol[p]['nifti_path']).header).splitlines()[1:]
                
        if sub_protocol[p]['VolumeCount'] > 1:
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
            plt.savefig('{}.png'.format(sub_protocol[p]['nifti_path'][:-7]))
            
        index = series_seriesID_list.index(sub_protocol[p]['series_id'])
        objects_entities = {'sub': subjects[s], 'ses': '', 'run': '', 'acq': '', 'ce': ''}
        
        #Port Series level information down to the object level
        sub_protocol[p]['include'] = data_list_unique_series[index]['include']
        sub_protocol[p]['DataType'] = data_list_unique_series[index]['DataType']
        sub_protocol[p]['ModalityLabel'] = data_list_unique_series[index]['ModalityLabel']
        sub_protocol[p]['br_type'] = data_list_unique_series[index]['br_type']
        sub_protocol[p]['error'] = data_list_unique_series[index]['error']
        sub_protocol[p]['sub'] = subjects[s]
        
        # if series_list[index]['entities']['run']:
        #     sub_protocol[p]['run'] = series_list[index]['entities']['run']
        # if series_list[index]['entities']['task']:
        #     sub_protocol[p]['TaskName'] = series_list[index]['entities']['task']
        # if series_list[index]['entities']['acq']:
        #     sub_protocol[p]['acq'] = series_list[index]['entities']['acq']
        # if series_list[index]['entities']['ce']:
        #     sub_protocol[p]['ce'] = series_list[index]['entities']['ce']
            
        
        #Determine other important BIDS information (i.e. run, dir, etc) for specific acquisitions        
        #T1w
        if sub_protocol[p]['br_type'] == 'anat/T1w' or sub_protocol[p]['br_type'] == 'anat/multiecho':
            #non-normalized T1w images that have poor CNR, so best to not have in BIDS if there's an actual good T1w available
            if 'NORM' not in sub_protocol[p]['ImageType'] and sub_protocol[p]['br_type'] == 'anat/T1w':
                sub_protocol[p]['include'] = False  
                sub_protocol[p]['error'] = 'Acquisition is a poor resolution T1w (non-normalized); Please check to see if this T1w acquisition should be converted to BIDS'
            else:
                sub_protocol[p]['include'] = True 
                sub_protocol[p]['error'] = ''
        
        #BOLD
        elif sub_protocol[p]['br_type'] == 'func/bold' or sub_protocol[p]['br_type'] == 'func/multiecho':
            #Instances where functional bold acquisitions have less than 30 volumes (probably a restart/failure occurred, or some kind of non-BIDS test)
            if sub_protocol[p]['VolumeCount'] < 30:
                sub_protocol[p]['include'] = False
                sub_protocol[p]['error'] = 'Functional run only contains {} volumes; ezBIDS minimum threshold is 30. Will not set for BIDS conversion unless specified so'.format(sub_protocol[p]['VolumeCount'])
            else:
                if bold_run < 10:
                    sub_protocol[p]['bold_run'] = '0' + str(bold_run)
                else:
                    sub_protocol[p]['bold_run'] = str(bold_run)
                objects_entities['run'] = sub_protocol[p]['bold_run']
                bold_run +=1
        
        #single band reference (sbref)
        elif sub_protocol[p]['br_type'] == 'func/sbref':
            if p+1 < len(sub_protocol):
                # index_next = series_SeriesDescription_list.index(sub_protocol[p+1]['SeriesDescription'])
                index_next = series_seriesID_list.index(sub_protocol[p+1]['series_id'])
                sub_protocol[p+1]['br_type'] = data_list_unique_series[index_next]['br_type']
                
            #Rare instances where sbref is not followed by functional bold
            if sub_protocol[p+1]['br_type'] not in ['func/bold', 'func/multiecho']:
                sub_protocol[p]['include'] = False
                sub_protocol[p]['error'] = 'Single band reference (sbref) acquisition is not immediately followed by a functional bold acquisition that is being converted to BIDS. Will not set for BIDS conversion'
                
            #Set include to False if functional bold after it has less than 20 volumes, which will cause it to not be converted to BIDS
            elif nib.load(sub_protocol[p+1]['nifti_path']).shape[3] < 20:
                sub_protocol[p]['include'] = False
                sub_protocol[p]['error'] = 'Functional bold acquisition following this sbref contains less than 20 volumes, causing it to not be converted to BIDS. Thus this sbref that precedes the functional bold will not set for BIDS conversion'
            else:    
                if sbref_run < 10:
                    sub_protocol[p]['sbref_run'] = '0' + str(sbref_run)
                else:
                    sub_protocol[p]['sbref_run'] = str(sbref_run)
                objects_entities['run'] = sub_protocol[p]['sbref_run']
                sbref_run += 1
                
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
        
            
    #Deal with field maps (i.e. set up IntendedFor field)
    descriptions = [sub_protocol[x]['SeriesDescription'] for x in range(len(sub_protocol))]
    modality_labels = [sub_protocol[x]['ModalityLabel'] for x in range(len(sub_protocol))]
    phase_encoding_directions = [sub_protocol[x]['dir'] for x in range(len(sub_protocol))]
    section_indices = [x for x, value in enumerate(descriptions) if any(x in value for x in ['Localizer','localizer','SCOUT','Scout','scout'])]
    section_indices = [section_indices[x] for x in range(len(section_indices)) if section_indices[x] == 0 or section_indices[x] - section_indices[x-1] > 1]
    include = [sub_protocol[x]['include'] for x in range(len(sub_protocol))]
    errors = [sub_protocol[x]['error'] for x in range(len(sub_protocol))]
    fmap_dwi_check = [sub_protocol[x]['fmap_dwi_check'] for x in range(len(sub_protocol))]
    fmap_intended_for_list = []
    fmap_counter = 0
    fmap_intended_for_index = 0
    
    #Add run number to anatomicals that have multiple acquisitions
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
        
    for i in range(len(sub_protocol)):
        
        if len(section_indices) == 0:
            section_indices = [0]
        if 0 not in section_indices:
            section_indices.insert(0,0)
            
        for j in range(len(section_indices)):
            section_start = section_indices[j]
                    
            try:
                section_end = section_indices[j+1]
            except:
                section_end = len(descriptions)
        
            section = descriptions[section_start:section_end]
            
            #SE EPI fmaps
            if 'epi' in modality_labels[section_start:section_end] and not any(x in descriptions for x in ['DWI','dwi','DTI','dti']):
                #Remove duplicate SE fmaps. Only the last two in each section will be kept
                fmap_se_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'epi']
                if len(fmap_se_indices) == 1:
                    if sub_protocol[i]['fmap_dwi_check'] == 0:
                        include[i] = False
                        sub_protocol[i]['include'] = include[i]
                        errors[i] = ['Only one spin echo field map found; need pair. Will not set for BIDS conversion']
                        sub_protocol[i]['error'] = errors[i]
                    else:
                        include[i] = True
                        sub_protocol[i]['include'] = include[i]
                        
                    
                if len(fmap_se_indices) > 2 and sum(fmap_dwi_check) == 0:
                    for fm in fmap_se_indices[:-2]:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = ['Multiple spin echo pairs detected in section; only selecting last pair for BIDS conversion']
                        sub_protocol[fm]['error'] = errors[fm]
                        
                #Remove SE fmaps where phase encoding directions aren't opposite
                if len(fmap_se_indices) > 1:
                    if list(np.array(phase_encoding_directions)[fmap_se_indices[-2:]])[0][::-1] != list(np.array(phase_encoding_directions)[fmap_se_indices[-2:]])[1] and sum(fmap_dwi_check) == 0:
                        for fm in fmap_se_indices[-2:]:
                            include[fm] = False
                            sub_protocol[fm]['include'] = include[fm]
                            errors[fm] = ['Spin echo fmap pair does not have opposite phase encoding directions. Will no set for BIDS conversion']
                            sub_protocol[fm]['error'] = errors[fm]
                    else:
                        pass
                                 
                fmap_se_indices_final = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'epi' and include[section_indices[j]+x] != False]
                
                if sub_protocol[i]['fmap_dwi_check'] == 0:
                    applied_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'bold' and include[section_indices[j]+x] != False]
                else:
                    applied_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'dwi' and include[section_indices[j]+x] != False]
                    
                try:
                    if fmap_se_indices_final:
                        if not len(applied_indices) and len(fmap_se_indices):
                            for fm in fmap_se_indices:
                                include[fm] = False
                                sub_protocol[fm]['include'] = include[fm]
                                errors[fm] = ['Spin echo pair detected in section, but no functional data in section to be applied to. Will not set for BIDS conversion']
                                sub_protocol[fm]['error'] = errors[fm]
                        
                        if sub_protocol[i]['fmap_dwi_check'] == 0:
                            fmap_intended_for = [section_indices[j] + x for x in range(len(section)) if modality_labels[section_start:section_end][x] == 'bold' and include[section_indices[j] + x] != False and include[fmap_se_indices_final[-1]] != False]
                        else:
                            fmap_intended_for = [section_indices[j] + x for x in range(len(section)) if modality_labels[section_start:section_end][x] == 'dwi' and include[section_indices[j] + x] != False and include[fmap_se_indices_final[-1]] != False]
                            
                        fmap_intended_for_list.append(fmap_intended_for)
                except:
                    pass
            
                        
            #Magnitude/Phasediff fmaps
            if ('magnitude1' or 'magnitude2') in modality_labels[section_start:section_end]:
                #Remove duplicate magnitude/phasediff fmaps. Only the last two in each section will be kept
                fmap_magphase_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'magnitude1' or value == 'phasediff']
                if len(fmap_magphase_indices) == 1:
                    include[fmap_magphase_indices[0]] = False
                    sub_protocol[fmap_magphase_indices[0]]['include'] = include[fmap_magphase_indices[0]]
                    errors[fmap_magphase_indices[0]] = ['Need pair for magnitude/phasediff field maps. Will not set for BIDS conversion']
                    sub_protocol[fmap_magphase_indices[0]]['error'] = errors[fmap_magphase_indices[0]]
                if len(fmap_magphase_indices) > 2:
                    for fm in fmap_magphase_indices[:-2]:
                        include[fm] = False
                        sub_protocol[fm]['include'] = include[fm]
                        errors[fm] = ['More than two magnitude/phasediff field maps found in section. Only selecting most recent pair for BIDS conversion']
                        sub_protocol[fm]['error'] = errors[fm]
                        
            #Determine which functional data the field maps will be applied to
            fmap_magphase_indices_final = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'magnitude1' or value == 'phasediff' and include[section_indices[j]+x] != False]        
            bold_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'bold' and include[section_indices[j]+x] != False]
            
            try:
                if fmap_magphase_indices_final:
                    if not len(bold_indices) and len(fmap_magphase_indices_final):
                        for fm in fmap_magphase_indices_final:
                            include[fm] = False
                            sub_protocol[fm]['include'] = include[fm]
                            errors[fm] = ['No functional data in section found for magnitude/phasediff to act on. Will not convert to BIDS']
                            sub_protocol[fm]['error'] = errors[fm]
                    
                    fmap_intended_for = [section_indices[j] + x for x in range(len(section)) if modality_labels[section_start:section_end][x] == 'bold' and include[section_indices[j] + x] != False and include[fmap_magphase_indices_final[-1]] != False]
                    fmap_intended_for_list.append(fmap_intended_for)
            except:
                pass
            
        
        # if sub_protocol[i]['ModalityLabel'] in ['epi','magnitude1','magnitude2','phasediff']:
        if len(fmap_intended_for_list) > 0:
            IntendedFor = fmap_intended_for_list[fmap_intended_for_index]
            fmap_counter += 1
            if fmap_counter > 1:
                fmap_intended_for_index += 1
                fmap_counter = 0
        else:
            IntendedFor = None
            
        check = [x['entities'] for x in series_list if x['series_id'] == sub_protocol[i]['series_id']] [0]
        try:
            if objects_entities_list[i]['dir'] == check['dir']:
                objects_entities_list[i]['dir'] == ''
        except:
            pass
            
        if sub_protocol[i]['include'] == False:
            print('{} not recommended for BIDS conversion: {}'.format(sub_protocol[i]['SeriesDescription'], sub_protocol[i]['error']))
        
        if not sub_protocol[i]['error']:
            error = None
        else:
            error = [sub_protocol[i]['error']]
        
        data_list[data_list_index] = sub_protocol[i]
        objects_info = {"include": sub_protocol[i]['include'],
                    "series_id": sub_protocol[i]['series_id'],
                    "PatientName": sub_protocol[i]['PatientName'],
                    "PatientID": sub_protocol[i]['PatientID'],
                    "PatientBirthDate": sub_protocol[i]['PatientBirthDate'],
                    "AcquisitionDate": sub_protocol[i]['AcquisitionDate'],
                    "pngPath": '{}.png'.format(sub_protocol[i]['nifti_path'][:-7]),
                    "IntendedFor": IntendedFor,
                    "entities": objects_entities_list[i],
                    "type": sub_protocol[i]['br_type'],
                    "items": [
                            {
                                "path": sub_protocol[i]['nifti_path'],
                                "name": sub_protocol[i]['nifti_name'],
                                "headers": sub_protocol[i]['headers']
                            },
                            {
                                "path": sub_protocol[i]['json_path'],
                                "name": sub_protocol[i]['json_name'],
                                "sidecar": sub_protocol[i]['sidecar']
                            }
                        ],
                    "analysisResults": {
                        "VolumeCount": sub_protocol[i]['VolumeCount'],
                        "errors": error,
                        "filesize": sub_protocol[i]['filesize']
                    },
                    "paths": sub_protocol[i]['paths']
                  }
        objects_list.append(objects_info)

for s in range(len(series_list)):
    series_list[s]['png_objects_indices'] = [x for x in range(len(objects_list)) if objects_list[x]['series_id'] == series_list[s]['series_id']]
    series_list[s]['unique_TRs'] = [objects_list[x]['items'][1]['sidecar']['RepetitionTime'] for x in range(len(objects_list)) if objects_list[x]['series_id'] == series_list[s]['series_id']] 
        
ezBIDS = {"subjects": subjectIDs_info,
          "sessions": acquisition_dates,
          "participantsColumn": participantsColumn,
          "series": series_list,
          "objects": objects_list
          }

ezBIDS_file_name = 'ezBIDS.json'
with open(ezBIDS_file_name, 'w') as fp: 
    json.dump(ezBIDS, fp, indent=3) 
  

