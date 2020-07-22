#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 26 08:37:56 2020

@author: dlevitas
"""


import os, sys, re, json, warnings
import pandas as pd
import numpy as np
from nilearn.image import load_img, index_img
from nilearn.plotting import plot_img
import matplotlib


warnings.filterwarnings("ignore")
#Force matplotlib to not use any Xwindows backend.
matplotlib.use('Agg')

#data_dir = '/media/data/ezbids/philips/spade'
#data_dir = '/media/data/ezbids/ge/p28'
#data_dir = '/media/data/ezbids/ge/20180918GE'
#data_dir = '/media/data/ezbids/philips/Tong_339037.3'
#data_dir = '/media/data/ezbids/siemens/DAN_STD/DAN_STD_1000_dicoms'
#data_dir = '/media/data/ezbids/siemens/soichi'

data_dir = sys.argv[1]


def extractor(data_dir):
    
    relative_root_level = data_dir.split('/')[-1]
    
    #Organize the nifti/json files by their series number    
    dir_list = pd.read_csv('{}/list'.format(data_dir), header=None)
    dir_list.columns = ['path']
    sn_list = []
    new_sn_list = []
    for d in range(len(dir_list)):
        dir_list['path'][d] = relative_root_level + '/' + dir_list['path'][d].split('./')[-1]
        
        try:
            sn = dir_list.path[d].split('sn-')[1].split('.')[0]
            sn_list.append(sn)
        except:
            sn = dir_list.path[d].split('sn-')[-1].split('_')[0]
            sn_list.append(sn)
            
        if int(re.match(r"([0-9]+)",sn).group()) < 10:
            new_sn = '0' + sn
        else:
            new_sn = sn
            
        new_sn_list.append(new_sn)
        
    dir_list['sn'] = pd.Series(sn_list, index=dir_list.index)
    dir_list['new_sn'] = pd.Series(new_sn_list, index=dir_list.index)
    dir_list.sort_values(by='new_sn', inplace=True, ignore_index=True)
    
    
    #Get nifti and json file lists
    json_list = [x for x in dir_list['path'] if '.json' in x and 'ezbids' not in x]
    nifti_list = [x.split('./')[-1] for x in dir_list['path'] if '.nii.gz' in x or '.bval' in x or '.bvec' in x]    
    SNs_list = [dir_list['sn'][x] for x in range(len(dir_list['sn'])) if '.json' in dir_list['path'][x]]
    print(json_list)
    
    participantsColumn = {"sex": {"LongName": "gender", "Description": "generic gender field", "Levels": {"M": "male", "F": "female"}},
                          "age": {"LongName": "age", "Units": "years"}}
    
    #Parse through json data for pertinent information
    data_list = []
    for j in range(len(json_list)):
        #json_data = open('{}/{}'.format(data_dir.replace(relative_root_level,'')[:-1], json_list[j]))
        json_data = open(json_list[j])
        json_data = json.load(json_data, strict=False)
        
        SN = SNs_list[j]
        
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
            
        # nifti_paths_for_json = [x for x in nifti_list if '{}-sn-{}'.format(json_list[j].split('-sn-')[0], str(json_data['SeriesNumber'])) in x]
        # nifti_paths_for_json = ['{}/{}'.format(data_dir,x) for x in nifti_list if '{}sn-{}.'.format(json_list[j].split('sn-')[0], str(json_data['SeriesNumber'])) in x or '{}sn-{}_'.format(json_list[j].split('sn-')[0], str(json_data['SeriesNumber'])) in x]
        nifti_paths_for_json_relative = ['{}/{}'.format(relative_root_level,x) for x in nifti_list if 'sn-{}.'.format(SN) in x or 'sn-{}_'.format(SN) in x]
        nifti_paths_for_json_absolute = ['{}/{}'.format(data_dir.replace(relative_root_level, ''),x) for x in nifti_list if 'sn-{}.'.format(SN) in x or 'sn-{}_'.format(SN) in x]
        filesize = os.stat(nifti_paths_for_json_absolute[0]).st_size
        
        
        try:
            subjID = json_data['PatientName']
        except:
            subjID = json_data['PatientID']
            
            
        try:
            volume_count = nib.load('{}/{}'.format(data_dir,json_list[j][:-4] + 'nii.gz')).shape[3]
        except:
            volume_count = 1
            
        paths_relative = nifti_paths_for_json_relative + ['{}/{}'.format(relative_root_level,json_list[j])]
        paths = nifti_paths_for_json_absolute + ['{}/{}'.format(data_dir,json_list[j])]
        
        # for p in range(len(paths)):
        #     if paths[p].split('.')[-1] == 'gz':
        #         name = 'nii.gz'
        #     elif paths[p].split('.')[-1] == 'json':
        #         name = ''
        #     elif
        #         name = paths[p].split('.')[-1]
        
        name = 'nii.gz'
            
        
        mapping_dic = {'StudyID': json_data['StudyID'], 
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
               'func_run': '',
               'dwi_run': '',
               'dir': PED,
               'TaskName': '',
               "include": True,
               'filesize': filesize,
               "VolumeCount": volume_count,
               'error': 'N/A',
               'qc': '',
               'path': nifti_paths_for_json_absolute,
               'paths': paths_relative,
               'name': name,
               'sidecar':json_data
               }
        data_list.append(mapping_dic)
        
        subjectIDs = list(set([x['PatientID'] for x in data_list]))
        for s in range(len(subjectIDs)):
            subjectIDs[s] = {'PatientID': subjectIDs[s], 'sub': 'null'}
            
        acquisition_dates = list(set([x['AcquisitionDate'] for x in data_list]))
        for a in range(len(acquisition_dates)):
            acquisition_dates[s] = {'AcquisitionDate': acquisition_dates[s], 'ses': ''}
        
    #Only keep dictionary with unique SeriesDescription key values
    data_list_unique_SD = []
    series_description_list = []
    series_number_list = []
    for SD in data_list:
        if SD['SeriesDescription'] not in series_description_list or SD['SeriesNumber'] not in series_number_list:
            data_list_unique_SD.append(SD)
            series_description_list.append(SD['SeriesDescription'])
            series_number_list.append(SD['SeriesNumber'])
    
    sbref_run = 1
    func_run = 1
    dwi_run = 1
    participants_list = []
    series_list = []
    objects_list = []
    
    
    #if any(x in descriptions[d] for x in ['T1w','tfl3d','mprage','tfl_1084B']):
    #Let's try to auto-populate some of the BIDS fields
    for i in range(len(data_list_unique_SD)):
        
        if not os.path.isfile('{}.png'.format(data_list_unique_SD[i]['path'][0][:-7])):
            img = load_img(data_list_unique_SD[i]['path'][0])
            if img.ndim == 4:
                ref_img = index_img(img, -1)
            else:
                ref_img = img
            plot_img(ref_img, colorbar=False, display_mode='x', cut_coords=1, 
                     draw_cross=False, annotate=False, threshold=None, 
                     output_file='{}.png'.format(data_list_unique_SD[i]['path'][0][:-7]))
            
            # if not os.path.isfile('{}/{}_screenshot.png'.format(data_dir, data_list_unique_SD[i]['paths'][0].split('/')[-1].split('.nii.gz')[0])): 
            #     os.system('fsleyes render --scene ortho --hidey --hidez --hideCursor \
            #             --outfile {}/{}_screenshot.png {}/{}'.format(data_dir, 
            #             [x.split('.nii.gz')[0] for x in data_list_unique_SD[i]['paths'] if 'nii.gz' in x][0], 
            #             data_dir, 
            #             [x for x in data_list_unique_SD[i]['paths'] if '.nii.gz' in x][0]))
            

        participants_info = {data_list_unique_SD[i]['PatientID']:
                             {"session": '',
                              "age": '',
                              "sex": data_list_unique_SD[i]['PatientSex']
                              }
                             }
        participants_list.append(participants_info)
        
        
        SD = data_list_unique_SD[i]['SeriesDescription']
        
        labels = {}
        
        #Check for localizer(s)
        if any(x in SD for x in ['Localizer','localizer','Scout','scout']):
            data_list_unique_SD[i]['include'] = False
            data_list_unique_SD[i]['error'] = 'Acquisition appears to be a localizer; will not be converted to BIDS'
        
        #Check for T1w anatomical
        elif any(x in SD for x in ['T1W','T1w','t1w','tfl3d','mprage','MPRAGE']):
            if 'NORM' in data_list_unique_SD[i]['ImageType']:
                data_list_unique_SD[i]['DataType'] = 'anat'
                data_list_unique_SD[i]['ModalityLabel'] = 'T1w'
            else:
              data_list_unique_SD[i]['include'] = False  
              data_list_unique_SD[i]['error'] = 'Acquisition is a poor resolution T1w; recommended not be converted to BIDS'
        
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
            if any(x in SD for x in ['REST','Rest','rest','RS']):
                data_list_unique_SD[i]['TaskName'] = 'rest'
                data_list_unique_SD[i]['sidecar']['TaskName'] = 'rest' 
            data_list_unique_SD[i]['func_run'] = str(func_run)
            sbref_run +=1
            data_list_unique_SD[i]['sidecar']['TaskName'] = 'rest'
            labels['run'] = str(data_list_unique_SD[i]['func_run'])
            labels['task'] = data_list_unique_SD[i]['TaskName']
            
        #Check for functional
        elif any(x in SD for x in ['REST','Rest','rest','RS']):
            data_list_unique_SD[i]['DataType'] = 'func'
            data_list_unique_SD[i]['ModalityLabel'] = 'bold'
            data_list_unique_SD[i]['TaskName'] = 'rest'
            data_list_unique_SD[i]['func_run'] = str(func_run)
            func_run +=1
            data_list_unique_SD[i]['sidecar']['TaskName'] = 'rest'
            labels['run'] = str(data_list_unique_SD[i]['func_run'])
            labels['task'] = data_list_unique_SD[i]['TaskName']

        elif any(x in SD for x in ['BOLD','Bold','bold','FUNC','Func','func','FMRI','fMRI','fmri','EPI']):
            data_list_unique_SD[i]['DataType'] = 'func'
            data_list_unique_SD[i]['ModalityLabel'] = 'bold'
            data_list_unique_SD[i]['TaskName'] = ''
            data_list_unique_SD[i]['func_run'] = str(func_run)
            func_run +=1
            data_list_unique_SD[i]['sidecar']['TaskName'] = ''
            labels['run'] = str(data_list_unique_SD[i]['func_run'])
            labels['task'] = data_list_unique_SD[i]['TaskName']
        
        #Check for DWI
        elif any(x in SD for x in ['DWI','dwi','DTI','dti']):
            data_list_unique_SD[i]['DataType'] = 'dwi'
            data_list_unique_SD[i]['ModalityLabel'] = 'dwi'
            data_list_unique_SD[i]['dwi_run'] = str(dwi_run)
            dwi_run += 1
            labels['run'] = str(data_list_unique_SD[i]['dwi_run'])
            labels['dir'] = data_list_unique_SD[i]['dir']
        
        #Check for field maps
        elif any(x in SD for x in ['fmap','FieldMap','field_mapping']):
            data_list_unique_SD[i]['DataType'] = 'fmap'
            data_list_unique_SD[i]['ModalityLabel'] = 'epi'
            labels['run'] = str(data_list_unique_SD[i]['dwi_run'])
            labels['dir'] = data_list_unique_SD[i]['dir']
        
        #Can't determine acquisition type. Assume it's not BIDS
        else:
            data_list_unique_SD[i]['include'] = False
            data_list_unique_SD[i]['error'] = 'Cannot determine acquisition type'
        
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
                       "labels": labels,
                       "type": br_type
                       }
        series_list.append(series_info)
        
        
        objects_info = {"include": data_list_unique_SD[i]['include'],
                       "SeriesDescription": SD,
                       "SeriesNumber": data_list_unique_SD[i]['SeriesNumber'],
                       "PatientID": data_list_unique_SD[i]['PatientID'],
                       "AcquisitionDate": data_list_unique_SD[i]['AcquisitionDate'],
                       "hierarchy": {
                           "session": data_list_unique_SD[i]['SessionID']
                        },
                       "labels": labels,
                       "type": br_type,
                       "items": [
                               {
                                   "path": data_list_unique_SD[i]['path'],
                                   "name": data_list_unique_SD[i]['name'],
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

        ezBIDS_file_name = '{}/ezBIDS.json'.format(data_dir)
        with open(ezBIDS_file_name, 'w') as fp: 
            json.dump(ezBIDS, fp, indent=3) 
            
    
    return dir_list, json_list, data_list, data_list_unique_SD

dir_list, json_list, data_list, data_list_unique_SD = extractor(data_dir)
    
    
    
    

