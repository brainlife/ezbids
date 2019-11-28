#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep 24 13:41:53 2019

@author: dlevitas

This script is primarily focused on determing which protocol items are going to be converted to BIDS or not
Once this is done, a dictionary will be created (and then converted to json file) for user interface system (hosted by brainlife team)
    
"""

from __future__ import division
import os, re, glob, json, shutil, argparse
import pandas as pd
import numpy as np

try:
    import nibabel as nib
except:
    os.system('pip install nibabel --user')
    import nibabel as nib


#User inputs:
prisma_dir = '/N/dcwan/projects/irf/Prisma'
bids_root_dir = '/N/dc2/scratch/dlevitas/fMRI_data/std/BIDS_conversion_testing'
config_file_dir = '{}/configuration_files'.format(bids_root_dir)
protocol_desc_dir = '{}/protocol_descriptions'.format(bids_root_dir)
conversion_log_dir = '{}/conversion_logs'.format(bids_root_dir)
study_name = 'Video'

subjID = ['A00083']
sesID = ['01']
task = ['video','rest']



scans = ['20180406.Video_A00083_01.9535@dpk_Video']

scans.sort()

#subjID = [subjID]
#sesID = [sesID]
#study_name = [study_name]
#tasks = [tasks]
#scans = [scans]


#Set up directories
if not os.path.isdir(config_file_dir):
    os.mkdir('{}'.format(config_file_dir))
    
if not os.path.isdir(protocol_desc_dir):
    os.mkdir('{}'.format(protocol_desc_dir))
    
if not os.path.isdir(conversion_log_dir):
    os.mkdir(conversion_log_dir)

#Set up study and subject directories
if not os.path.isdir('{}/{}'.format(bids_root_dir, study_name)):
    os.mkdir('{}/{}'.format(bids_root_dir, study_name))
    os.system('dcm2bids_scaffold -o {}/{}'.format(bids_root_dir, study_name))
    os.system('echo "{} imaging data" > {}/{}/README'.format(study_name, bids_root_dir, study_name))
    
    
output_dir = '{}/{}'.format(bids_root_dir, study_name)
#
##Adjust participants.tsv file
participants_file = pd.read_csv('{}/{}/participants.tsv'.format(bids_root_dir, study_name), sep='\t')
if 'bmi' in participants_file.columns:
    participants_file.dropna(axis=0)
    del participants_file['education']
    del participants_file['bmi']
    participants_file = participants_file.drop(0)
    
    
for i in range(len(scans)):
    
    #Set up conversion log file
    if sesID[i] == 'N/A':
        if not os.path.isfile('{}/{}_sub-{}.txt'.format(conversion_log_dir, study_name, subjID[i])):
            os.system('touch {}/{}_sub-{}.txt'.format(conversion_log_dir, study_name, subjID[i]))
        log = open('{}/{}_sub-{}.txt'.format(conversion_log_dir, study_name, subjID[i]), "w")
            
    else:
        if not os.path.isfile('{}/{}_sub-{}_ses-{}.txt'.format(conversion_log_dir, study_name, subjID[i], sesID[i])):
            os.system('touch {}/{}_sub-{}_ses-{}.txt'.format(conversion_log_dir, study_name, subjID[i], sesID[i]))
        log = open('{}/{}_sub-{}_ses-{}.txt'.format(conversion_log_dir, study_name, subjID[i], sesID[i]), "w")
        
    log.write('#################################\n')
    log.write('Warnings/Errors\n')
    log.write('#################################\n')
    log_num = 1
    
    #Make sure there are actually dicoms in the dicom directory. Sometimes empty, in which case can't convert
    if not len([x for x in os.listdir('{}/{}'.format(prisma_dir, scans[i])) if '.dcm' in x]):
        log.write('{}. There are no dicoms in this directory. Cannot convert to BIDS\n'.format(log_num))
        log_num += 1
    else:
        #Add subject ID to participants.tsv file
        if 'sub-{}'.format(subjID[i]) not in participants_file['participant_id'].tolist():
            participants_file = participants_file.append(pd.Series(['sub-{}'.format(subjID[i])], index=participants_file.columns), ignore_index=True)
            
        
        #Studies with sessions require an additional directory layer
        if sesID[i] != 'N/A':
            path = '{}/sub-{}/ses-{}'.format(study_name, subjID[i], sesID[i])
        else:
            path = '{}/sub-{}'.format(study_name, subjID[i])
            
        if not os.path.isdir('{}/{}'.format(bids_root_dir, path)):            
                
#            #Run dcm2niix first to get idea of the data
#            if not os.path.isdir('{}/{}/tmp_dcm2niix'.format(bids_root_dir, study_name)):
#                os.mkdir('{}/{}/tmp_dcm2niix'.format(bids_root_dir, study_name))
#    
#            if sesID[i] == 'N/A':
#                if not os.path.isdir('{}/{}/tmp_dcm2niix/sub-{}'.format(bids_root_dir, study_name, subjID[i])):
#                    os.mkdir('{}/{}/tmp_dcm2niix/sub-{}'.format(bids_root_dir, study_name, subjID[i]))
#            if sesID[i] != 'N/A':
#                if not os.path.isdir('{}/{}/tmp_dcm2niix/sub-{}_ses-{}'.format(bids_root_dir, study_name, subjID[i], sesID[i])):
#                    os.mkdir('{}/{}/tmp_dcm2niix/sub-{}_ses-{}'.format(bids_root_dir, study_name, subjID[i], sesID[i]))
#                
#            if sesID[i] == 'N/A':
#                if len(os.listdir("{}/{}/tmp_dcm2niix/sub-{}".format(bids_root_dir, study_name, subjID[i]))) == 0:
#                    print('Running dcm2niix (first time) on subject {}'.format(subjID[i]))
#                    os.system("dcm2niix -z n -o {}/{}/tmp_dcm2niix/sub-{} {}/{}".format(bids_root_dir, study_name, subjID[i], prisma_dir, scans[i]))
#            else:
#                if len(os.listdir("{}/{}/tmp_dcm2niix/sub-{}_ses-{}".format(bids_root_dir, study_name, subjID[i], sesID[i]))) == 0:
#                    print('Running dcm2niix (first time) on subject {} session {}'.format(subjID[i], sesID[i]))
#                    os.system("dcm2niix -z n -o {}/{}/tmp_dcm2niix/sub-{}_ses-{} {}/{}".format(bids_root_dir, study_name, subjID[i], sesID[i], prisma_dir, scans[i]))
#    
            #Organize json and nifti files based on their SeriesNumber and remove files with same SeriesNumber (e.g localizers)
            json_list_final = []
            json_list_series_num = []
            
            if sesID[i] == 'N/A':
                json_list = [x for x in os.listdir('{}/{}/tmp_dcm2niix/sub-{}'.format(bids_root_dir, study_name, subjID[i])) if '.json' in x]
                for js in range(len(json_list)):
                    json_file = open("{}/{}/tmp_dcm2niix/sub-{}/{}".format(bids_root_dir, study_name, subjID[i], json_list[js]))
                    json_file = json.load(json_file)
                    json_list_final.append((json_list[js], json_file['SeriesNumber']))
                json_list_final.sort(key=lambda x: x[1])
            else:
                json_list = [x for x in os.listdir('{}/{}/tmp_dcm2niix/sub-{}_ses-{}'.format(bids_root_dir, study_name, subjID[i], sesID[i])) if '.json' in x]
                for js in range(len(json_list)):
                    json_file = open("{}/{}/tmp_dcm2niix/sub-{}_ses-{}/{}".format(bids_root_dir, study_name, subjID[i], sesID[i], json_list[js]))
                    json_file = json.load(json_file)
                    json_list_final.append((json_list[js], json_file['SeriesNumber']))
                json_list_final.sort(key=lambda x: x[1])
            
            
            json_list_final = [json_list_final[x] for x in range(len(json_list_final)) if x == 0 or '_e2.' not in json_list_final[x][0]]
            json_list_final = [json_list_final[x][0] for x in range(len(json_list_final)) if json_list_final[x][1] != json_list_final[x-1][1]]
            
            nii_list_final = [x[:-4] + 'nii' for x in json_list_final]
            
            #Extract important dicom data (comes from the json files generated by dcm2niix)
            image_types = []
            series_num = []
            descriptions = []
            sequence_names = []
            phase_encoding_directions = []
            
            T1w_run_num = 1
            T2w_run_num = 1
            flair_run_num = 1
            dwi_run_num = 1
            se_fmap_ped = []
            se_fmap_indices = []
            
            task_list = []
            func_list = []
            run_index = 0
            
            
            #Information needed for dcm2bids configuration file
            sequences = []
            data_types = []
            modality_labels = []
            custom_labels = []
            intended_for = []
            echo_time = []
                
            
            for j in range(len(json_list_final)):
                if sesID[i] == 'N/A':
                    input_file = open("{}/{}/tmp_dcm2niix/sub-{}/{}".format(bids_root_dir, study_name, subjID[i], json_list_final[j]))
                else:
                    input_file = open("{}/{}/tmp_dcm2niix/sub-{}_ses-{}/{}".format(bids_root_dir, study_name, subjID[i], sesID[i], json_list_final[j]))
                    
                json_file = json.load(input_file)
                
                image_types.append(json_file['ImageType'])
                series_num.append(json_file['SeriesNumber'])
                sequence_names.append(json_file['SequenceName'])
                descriptions.append(json_file['SeriesDescription'])
                echo_time.append(json_file['EchoTime'])
                try:
                    phase_encoding_directions.append(json_file['PhaseEncodingDirection'])
                except:
                    phase_encoding_directions.append('')
                
            #Begin:
            #Need to determine the "sections" of a protocol, where a subject may have stopped and restarted a scan
            #This can be intentional (i.e. subjects get a break in middle of scan), or unintentional (i.e. subjects needs to use restroom, anxious, etc)
            #If subject stays in scanner for entire scan, it's counted as just 1 "section"
            #Section(s) determined by number and location of localizers, since they need to re re-run every time subject enters
            
            
            localizer = descriptions[0] #assumption being that localizer is first in protocol
            dicom_convert_dir = '{}/{}'.format(prisma_dir, scans[i])
            
            #Cases where localizer not run at beginning, for whatever unfathomable reason
            if localizer not in ['Localizer', 'localizer', 'Scout', 'scout']:
                if len([s for s in descriptions if 'Localizer' in s or 'localizer' in s or 'Scout' in s or 'scout' in s]) == 0:
                    localizer = 'localizer'
                else:
                    localizer = [s for s in descriptions if 'Localizer' in s or 'localizer' in s or 'Scout' in s or 'scout' in s][0]
                
    
            #Begin getting information for dcm2bids configuration file    
            for d in range(len(descriptions)):
                #T1w
                if any(x in descriptions[d] for x in ['T1w','tfl3d','mprage']):
                    data_types.append("anat")
                    modality_labels.append("T1w")
                    custom_labels.append('')
                
                #Multi-echo T1w
                elif 'RMS' in descriptions[d]:
                    #Make sure we have pydicom, which is used to read dicom files
                    try:
                        import pydicom
                    except ImportError:
                        os.system('pip install -U pydicom --user')
                        import pydicom
                        
                    if series_num[d] >=10:
                        dicom_num = '0000' + str(series_num[d])
                    else:
                        dicom_num = '00000' + str(series_num[d])
                        
                    first_dicom = pydicom.dcmread(sorted(glob.glob('{}/{}/*_{}_*.dcm'.format(prisma_dir, scans[i], dicom_num)))[0])
                    second_dicom = pydicom.dcmread(sorted(glob.glob('{}/{}/*_{}_*.dcm'.format(prisma_dir, scans[i], dicom_num)))[1])
                    
                    if first_dicom.InstanceNumber == second_dicom.InstanceNumber:
                        os.system('echo multiecho T1w has duplicate dicoms; removing duplicates (protocol #{}) >> {}'.format(d+1, log))
                        log.write('{}. multiecho T1w has duplicate dicoms; removing duplicates (protocol #{})\n'.format(log_num, d+1))
                        log_num += 1
                        #Issue with multiecho RMS scan: https://github.com/rordenlab/dcm2niix/issues/300
                        #The solution is to delete some redundant dicoms, so copy dicom dir to new place where we can remove them without touching the originals
                        #Copy raw dicom directory to output directory, since we need to delete some redundant dicoms
                        if len(glob.glob('{}/{}'.format(output_dir, scans[i]))) == 0:
                            print('copying dicom directory for subject {}, session {}'.format(subjID[i], sesID[i]))
                            os.system('cp -r {}/{} {}'.format(prisma_dir, scans[i], output_dir))
                            
                        for x in glob.glob('{}/{}/*_{}_*.dcm'.format(output_dir, scans[i], dicom_num)):
                            if int(re.compile(r'\d+').findall(x)[-1]) % 2 == 0: #even numbered dicoms; remove
                                os.remove(x)
                        
                        dicom_convert_dir = '{}/{}'.format(output_dir, scans[i])
                                
                    data_types.append("anat")
                    modality_labels.append("T1w")
                    custom_labels.append('') 
                            
                #T2w
                elif any(x in descriptions[d] for x in ['T2w']):
                    data_types.append("anat")
                    modality_labels.append("T2w")
                    custom_labels.append('')
                        
                #FLAIR
                elif any(x in descriptions[d] for x in ['t2_space_da-fl', 'FLAIR', 'flair']):
                    data_types.append("anat")
                    modality_labels.append("FLAIR")
                    custom_labels.append('')
                
                #Localizers and other non-BIDS items
                elif any(x in descriptions[d] for x in ['Localizer', 'localizer', 'Scout', 'scout', 'Audiotest', 'tfl', 'multiecho', 'MicTest']):
                    data_types.append("non-BIDS")
                    modality_labels.append("non-BIDS")
                    custom_labels.append("non-BIDS")
                    
                #Functional       
                elif any(x in sequence_names[d] for x in ['epfid2d1']):
                    data_types.append("func")
                    if 'SBRef' in descriptions[d] or 'sbref' in descriptions[d]:
                        modality_labels.append("sbref")
                    else:
                        modality_labels.append("bold")
                    custom_labels.append("task-")
                
                #Field Maps
                elif any(x in descriptions[d] for x in ['fmap','FieldMap','field_mapping', 'B0_only']):
                    if 'B0_only' in  descriptions[d]:
                        data_types.append("fmap")
                        modality_labels.append("epi-dwi")
                        custom_labels.append("dir-")
                    
                    elif 'fm2d2r' in sequence_names[d]: 
                        if echo_time[d] == echo_time[d-1]: #Instance where magnitude and phasediff has the same echo time; not good, so don't convert
                            log.write('{}. magnitude/phasediff fmap pair has same echo time: {} (protocol #{} and #{})\n'.format(log_num, echo_time[d], d, d+1))
                            log_num += 1
                            data_types.append("non-BIDS")
                            modality_labels.append("non-BIDS")
                            custom_labels.append("non-BIDS")
                            
                            data_types[d-1] = "non-BIDS"
                            modality_labels[d-1] = "non-BIDS"
                            custom_labels[d-1] = "non-BIDS"
                        
                        elif 'fm2d2r' in sequence_names[d-1] and modality_labels[d-1] == 'magnitude1':
                            data_types.append("fmap")
                            modality_labels.append("phasediff")
                            custom_labels.append('')
                        
                        else:
                            data_types.append("fmap")
                            modality_labels.append("magnitude1")
                            custom_labels.append('')
    
                    else:
                        data_types.append("fmap")
                        modality_labels.append("epi")
                        custom_labels.append("dir-")
                    
                #DWI        
                elif any(x in descriptions[d] for x in ['DWI','dwi']):
                    data_types.append("dwi")
                    modality_labels.append("dwi")
                    custom_labels.append('')
                    
                #Miscellaneous, can't determine what it is. So probably not BIDS compatible anyway
                else:
                    #series_num[d] = -1
                    data_types.append("non-BIDS")
                    modality_labels.append("non-BIDS")
                    custom_labels.append("non-BIDS")
                    
                
            #Time to refine things (e.g. remove duplicates, check field maps, etc) except for the field maps; do those later
            for t in range(len(data_types)):
                #Remove localizers and other non-BIDS items
                if data_types[t] == 'non-BIDS':
                    series_num[t] = -1
                #Remove non-normalized T1w scans, unless there isn't a non-normalized T1w
                if modality_labels[t] == 'T1w' and 'NORM' not in image_types[t]:
                    if any(x in modality_labels for x in 'T1w'):
                        series_num[t] = -1
                        modality_labels[t] = 'non-BIDS'
                    else:
                        pass
                        
                #Add run numbers to anatomical data if there are multiple runs (not including non-normalized T1w); users will decide whether to remove duplicates anatomical data or not
                if modality_labels[t] == 'T1w' and len([modality_labels[x] for x in range(len(modality_labels)) if 'T1w' in modality_labels[x] and 'NORM' in image_types[x]]) > 1:
                    custom_labels[t] = 'run-0{}'.format(T1w_run_num)
                    T1w_run_num += 1
                if modality_labels[t] == 'T2w' and len([modality_labels[x] for x in range(len(modality_labels)) if 'T2w' in modality_labels[x] and 'NORM' in image_types[x]]) > 1:
                    custom_labels[t] = 'run-0{}'.format(T2w_run_num)
                    T2w_run_num += 1
                if modality_labels[t] == 'FLAIR' and len([modality_labels[x] for x in range(len(modality_labels)) if 'FLAIR' in modality_labels[x]]) > 1:
                    custom_labels[t] = 'run-0{}'.format(flair_run_num)
                    flair_run_num += 1
                #Get functional data organized
                if modality_labels[t] == 'bold':
                    if sesID[i] =='N/A':
                        mri = nib.load('{}/{}/tmp_dcm2niix/sub-{}/{}'.format(bids_root_dir, study_name, subjID[i], nii_list_final[t]))
                    else:
                        mri = nib.load('{}/{}/tmp_dcm2niix/sub-{}_ses-{}/{}'.format(bids_root_dir, study_name, subjID[i], sesID[i], nii_list_final[t]))
                        
                    #Remove functional data (and corresponding sbref if included) with 10 volumes or less; probably something weird happened and won't be used anyhow
                    if mri.shape[3] <= 20:
                        log.write('{}. {} only contains {} volumes; will not convert to BIDS (protocol #{})\n'. format(log_num, descriptions[t], mri.shape[3], t+1))
                        log_num += 1
                        series_num[t] = -1
                        if modality_labels[t-1] == 'sbref':
                            series_num[t-1] = -1
                    else:
                        #Determine task name (some protocols have an explicit task and a "rest" task)
                        if 'REST' in descriptions[t] or 'rest' in descriptions[t]:
                            task_name = 'rest'
                        else:
                            task_name = [x for x in task if 'rest' not in x][0]
                        task_list.append(task_name)
                        
                        #Assign run numbers by task
                        run_num = len([x for x in task_list if task_name in x and 'bold' in modality_labels[t]])
                        if run_num < 10:
                            custom_labels[t] = 'task-{}_run-0{}'.format(task_name, run_num)
                            if modality_labels[t-1] == 'sbref':
                                custom_labels[t-1] = 'task-{}_run-0{}'.format(task_name, run_num)
                        else:
                            custom_labels[t] = 'task-{}_run-{}'.format(task_name, run_num)
                            if modality_labels[t-1] == 'sbref':
                                custom_labels[t-1] = 'task-{}_run-{}'.format(task_name, run_num)
                        
                        run_index += 1
                #DWI
                if modality_labels[t] == 'dwi':
                    if len([x for x in modality_labels if 'dwi' in x]) > 1: #assuming two
                        if dwi_run_num == 1:
                            pass
                        else:
                            if phase_encoding_directions[t-1] == phase_encoding_directions[t-1]: #BAD. Means they don't have opposing phase directions; don't convert to BIDS
                                series_num[t-1] = -1
                                series_num[t] = -1
                            else:
                                custom_labels[t-1] = 'run-0{}'.format(dwi_run_num)
                                dwi_run_num += 1
                                custom_labels[t] = 'run-0{}'.format(dwi_run_num)
    
            
            
            #Deal with field maps separately, since they're so difficult to properly account for
            #Determine section indices
            section_indices = [x for x, value in enumerate(descriptions) if value == localizer]
            
            if len(section_indices) == 0:
                section_indices = [0]
            
            if 0 not in section_indices:
                section_indices.insert(0,0)
                
            
            intended_for = []
            for j in range(len(section_indices)):
                section_start = section_indices[j]
                
                try:
                    section_end = section_indices[j+1]
                except:
                    section_end = len(descriptions)
            
                section = descriptions[section_start:section_end]
                
                
                #SE EPI fmaps
                if 'epi' in modality_labels[section_start:section_end]:
                    #Remove duplicate SE fmaps. Only the last two in each section will be kept
                    fmap_se_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'epi']
                    if len(fmap_se_indices) > 2:
                        for fm in fmap_se_indices[:-2]:
                            series_num[fm] = -1
                            
                    #Remove SE fmaps where phase encoding directions aren't opposite
                    if list(np.array(phase_encoding_directions)[fmap_se_indices[-2:]])[0] == list(np.array(phase_encoding_directions)[fmap_se_indices[-2:]])[1]:
                        for fm in fmap_se_indices[-2:]:
                            log.write('{}. Spin echo fmap pair does not have opposite phase encoding direction (Protocol #{} and #{})\n'.format(log_num, d, d+1))
                            log_num += 1
                            series_num[fm] = -1
                    
                    #Specify the phase encoding direction in the custom_labels list
                    fmap_se_indices_final = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'epi' and series_num[section_indices[j]+x] != -1]
                    for f in fmap_se_indices_final:
                        if phase_encoding_directions[f] == 'j':
                            custom_labels[f] = 'dir-PA'
                        elif phase_encoding_directions[f] == 'j-':
                            custom_labels[f] = 'dir-AP'
                        elif phase_encoding_directions[f] == 'i':
                            custom_labels[f] = 'dir-LR'
                        elif phase_encoding_directions[f] == 'i-':
                            custom_labels[f] = 'dir-RL'
                            
                #DWI fmaps
                if 'epi-dwi' in modality_labels[section_start:section_end]:
                    #Remove duplicate dwi fmaps. Only the last one in each section will be kept
                    fmap_dwi_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'epi-dwi']
                    if len(fmap_dwi_indices) > 1:
                        for fm in fmap_dwi_indices[:-1]:
                            series_num[fm] = -1
                            
                    #Remove dwi fmaps where phase encoding direction isn't opposite from the DWI data phase encoding direction (assumption is that there's only one dwi scan)
                    dwi_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'dwi']
                    if list(np.array(phase_encoding_directions)[fmap_dwi_indices[-1:]])[0] == list(np.array(phase_encoding_directions)[dwi_indices[-1:]])[0]:
                        for fm in fmap_dwi_indices[-1:]:
                            series_num[fm] = -1
                    
                    #Instances where dwi fmaps and dwi data are on different encoding planes (e.g. i- j, or i- j-, etc)
                    if list(np.array(phase_encoding_directions)[fmap_dwi_indices[-1:]])[0][0] != list(np.array(phase_encoding_directions)[dwi_indices[-1:]])[0][0]:
                        log.write('{}. DWI data does not have opposite phase encoding direction (Protocol #{} and #{})\n'.format(log_num, d, d+1))
                        log_num += 1
                        for fm in fmap_dwi_indices[-1:]:
                            series_num[fm] = -1
                     
                    #Specify the phase encoding direction in the custom_labels list
                    fmap_dwi_indices_final = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'epi-dwi' and series_num[section_indices[j]+x] != -1]
                    for f in fmap_dwi_indices_final:
                        if phase_encoding_directions[f] == 'j':
                            custom_labels[f] = 'dir-PA'
                        elif phase_encoding_directions[f] == 'j-':
                            custom_labels[f] = 'dir-AP'
                        elif phase_encoding_directions[f] == 'i':
                            custom_labels[f] = 'dir-LR'
                        elif phase_encoding_directions[f] == 'i-':
                            custom_labels[f] = 'dir-RL'
                
                            
                #Magnitude/Phasediff fmaps
                if 'magnitude1' in modality_labels[section_start:section_end]:
                    #Remove duplicate magnitude/phasediff fmaps. Only the last two in each section will be kept
                    fmap_mag_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'magnitude1' or value == 'phasediff']
                    if len(fmap_mag_indices) > 2:
                        for fm in fmap_mag_indices[:-2]:
                            series_num[fm] = -1
                                            
                    
                            
                #Determine which functional/dwi data the field maps will act on
                bold_indices = [section_indices[j]+x for x, value in enumerate(modality_labels[section_start:section_end]) if value == 'bold' and series_num[section_indices[j]+x] != -1]
                
                try:
                    if fmap_se_indices_final:
                        
                        if not len(bold_indices) and len(fmap_se_indices):
                            for fm in fmap_se_indices:
                                series_num[fm] = -1
                        
                        fmap_intended_for = [section_indices[j] + x for x in range(len(section)) if modality_labels[section_start:section_end][x] == 'bold' and series_num[section_indices[j] + x] != -1 and series_num[fmap_se_indices_final[-1]] != -1]
                        #bad_series += len([k for k in series_num[section_start:section_end][0:series_num[section_start:section_end].index(fmap_se_indices_final[-1])] if k == -1])
                        bad_series = len([k for k in series_num[section_start:section_end][0:bold_indices[0]] if k == -1])
                        fmap_intended_for = [x - bad_series for x in fmap_intended_for]
                        if fmap_intended_for:
                            intended_for.append(fmap_intended_for)
                except:
                    pass
                
                try:
                    if fmap_mag_indices:
                        
                        if not len(bold_indices) and len(fmap_mag_indices):
                            for fm in fmap_mag_indices:
                                series_num[fm] = -1
                        
                        
                        fmap_intended_for = [section_indices[j] + x for x in range(len(section)) if modality_labels[section_start:section_end][x] == 'bold' and series_num[section_indices[j] + x] != -1 and series_num[fmap_mag_indices[-1]] != -1]
                        #bad_series += len([k for k in series_num[section_start:section_end][0:series_num[section_start:section_end].index(fmap_mag_indices[-1])] if k == -1])
                        #bad_series += len([k for k in series_num[section_start:section_end][0:bold_indices[0]] if k == -1])
                        bad_series = len([k for k in series_num[0:bold_indices[0]] if k == -1])
                        fmap_intended_for = [x - bad_series for x in fmap_intended_for]
                        if fmap_intended_for:
                            intended_for.append(fmap_intended_for)
                except:
                    pass
                                    
            #Make participants_file variable the new participants.tsv
            participants_file.to_csv('{}/{}/participants.tsv'.format(bids_root_dir, study_name), sep='\t', index=False)
    
            
            #Delete warning/error log file if nothing odd occured
            if sesID[i] == 'N/A':
                if len(open('{}/{}_sub-{}.txt'.format(conversion_log_dir, study_name, subjID[i])).readlines()) == 3:
                    os.system('rm -rf {}/{}_sub-{}.txt'.format(conversion_log_dir, study_name, subjID[i]))
            else:
                if len(open('{}/{}_sub-{}_ses-{}.txt'.format(conversion_log_dir, study_name, subjID[i], sesID[i])).readlines()) == 3:
                    os.system('rm -rf {}/{}_sub-{}.txt'.format(conversion_log_dir, study_name, subjID[i], sesID[i]))
                    
            #Remove parts of protocol that won't be converted to BIDS
            indices_to_remove = [x for x, value in enumerate(series_num) if value == -1]
            series_num = [x for x in series_num if x != -1]
            data_types = [data_types[x] for x in range(len(data_types)) if x not in indices_to_remove]
            modality_labels = [modality_labels[x] for x in range(len(modality_labels)) if x not in indices_to_remove]
            custom_labels = [custom_labels[x] for x in range(len(custom_labels)) if x not in indices_to_remove]
            echo_time = [echo_time[x] for x in range(len(echo_time)) if x not in indices_to_remove]
            image_types = [image_types[x] for x in range(len(image_types)) if x not in indices_to_remove]
            
            if 'T1w' not in modality_labels:
                if sesID[i] == 'N/A':
                    log.write('{}. No good anatomical found in protocol! Will not be able to pre-process data\n'.format(log_num))
                    log_num += 1
                else:
                    log.write('{}. No good anatomical found in protocol! If anatomical not found in other session(s), cannot pre-process data\n'.format(log_num))
                    log_num += 1
                    
            log.close()
        
            #Add "IntendedFor" field for DWI fieldmaps (i.e. B0). Indicates which DWI runs the fieldmaps will perform distortion correction on
            #Assumption is that only one DWI fieldmap exists
            dwi_index = [x[0] for x in enumerate(modality_labels) if x[1] == 'dwi']
            
            
            #Reformat series_num values      
            for k in range(len(series_num)):
                if series_num[k] > 9:
                    series_num[k] = '0' + str(series_num[k]) + '*'
                else:
                    series_num[k] = '00' + str(series_num[k]) + '*'
                    
            #Set up dictionary, which will become the configuration file for dcm2bids
            dic = {"descriptions": []}
            intended_for_index = 0
            intended_for_move = 0
            fmap_echo_index = 0
            fmap_package = 2
            for d in range(len(data_types)):
                if data_types[d] == "func":
                    dic['descriptions'].append({"dataType": data_types[d], "modalityLabel": modality_labels[d], "customLabels": custom_labels[d], "criteria":{"SidecarFilename": series_num[d]}, "sidecarChanges":{"TaskName":custom_labels[d][:-7][5:]}})
                elif data_types[d] == 'fmap':
                    if modality_labels[d] == 'epi-dwi':
                        dic['descriptions'].append({"dataType": data_types[d], "modalityLabel": "epi", "IntendedFor": dwi_index, "criteria":{"SidecarFilename": series_num[d]}})
                    else:
                        if 'magnitude1' in modality_labels[d]:
                            dic['descriptions'].append({"dataType": data_types[d], "modalityLabel": modality_labels[d], "IntendedFor": intended_for[intended_for_index], "criteria":{"SidecarFilename": series_num[d], "EchoTime": echo_time[fmap_echo_index]}})
                            fmap_echo_index += 1
                            intended_for_move += 1
                        elif 'phasediff' in modality_labels[d]:
                            dic['descriptions'].append({"dataType": data_types[d], "modalityLabel": modality_labels[d], "IntendedFor": intended_for[intended_for_index], "criteria":{"SidecarFilename": series_num[d]}, "sidecarChanges":{"EchoTime1": echo_time[0], "EchoTime2": echo_time[1]}})
                            intended_for_move += 1
                            intended_for_index += 1
                        else:
                            dic['descriptions'].append({"dataType": data_types[d], "modalityLabel": modality_labels[d], "customLabels": custom_labels[d], "IntendedFor": intended_for[intended_for_index], "criteria":{"SidecarFilename": series_num[d]}})
                            intended_for_move += 1
                            if intended_for_move % fmap_package == 0:
                                intended_for_index += 1
                else:
                    dic['descriptions'].append({"dataType": data_types[d], "modalityLabel": modality_labels[d], "criteria":{"SidecarFilename": series_num[d]}})
                    
            
            #Convert dictionary to .json file, which is now the configuration file to be used by dcm2bids
            if sesID[i] == 'N/A':
                config_name = '{}/config_{}_{}.json'.format(config_file_dir, study_name, subjID[i])
            else:
                config_name = '{}/config_{}_{}_{}.json'.format(config_file_dir, study_name, subjID[i], sesID[i])
            with open('{}'.format(config_name), 'w') as fp:
                json.dump(dic, fp, indent=3)
                
            #Write protocol output to text file. Can be used to double check that BIDS conversion worked properly
            desc = pd.DataFrame(descriptions)
            if sesID[i] != 'N/A':
                desc.to_csv('{}/{}-{}-{}.txt'.format(protocol_desc_dir, study_name, subjID[i], sesID[i]), header=None, index=False)
            else:
                desc.to_csv('{}/{}-{}.txt'.format(protocol_desc_dir, study_name, subjID[i]), header=None, index=False)
                    
            #Run dcm2bids (i.e. dicom conversion to BIDS formar)
            if sesID[i] != 'N/A':
                print('running dcm2bids/pydeface on {} subject {}, session {}'.format(study_name, subjID[i], sesID[i]))
                os.system("dcm2bids -d {} -p {} -s {} -c {}/config_{}_{}_{}.json -o {} --forceDcm2niix".format(dicom_convert_dir, subjID[i], sesID[i], config_file_dir, study_name, subjID[i], sesID[i], output_dir))
            else:
                print('running dcm2bids/pydeface on {} subject {}'.format(study_name, subjID[i]))
                os.system("dcm2bids -d {} -p {} -c {}/config_{}_{}.json -o {} --forceDcm2niix".format(dicom_convert_dir, subjID[i], config_file_dir, study_name, subjID[i], output_dir))
             
            #Add .bvec and .bval file paths to .bidsignore file if they're in fmap directory
            if not os.path.isfile('{}/.bidsignore'.format(output_dir)):
                os.system('touch {}/.bidsignore'.format(output_dir))
            
            if sesID[i] == 'N/A':
                if len(glob.glob('{}/sub-{}/fmap/*.bvec'.format(output_dir,subjID[i]))) > 0:
                    os.system('echo {}/sub-{}/fmap/*.bvec >> {}/.bidsignore'.format(output_dir, subjID[i], output_dir))
                    os.system('echo {}/sub-{}/fmap/*.bval >> {}/.bidsignore'.format(output_dir, subjID[i], output_dir))
            else:
                if len(glob.glob('{}/sub-{}/ses-{}/fmap/*.bvec'.format(output_dir, subjID[i], sesID[i]))) > 0:
                    os.system('echo {}/sub-{}/ses-{}/fmap/*.bvec >> {}/.bidsignore'.format(output_dir, subjID[i], sesID[i], output_dir))
                    os.system('echo {}/sub-{}/ses-{}/fmap/*.bval >> {}/.bidsignore'.format(output_dir, subjID[i], sesID[i], output_dir))
           
            #Deface anatomical data
            try:
                if sesID[i] != 'N/A':
                    anat_path = '{}/{}/sub-{}/ses-{}/anat'.format(bids_root_dir, study_name, subjID[i], sesID[i])
                else:
                    anat_path = '{}/{}/sub-{}/anat'.format(bids_root_dir, study_name, subjID[i])
                    
                for a in glob.glob('{}/*.nii.gz'.format(anat_path)):
                    os.system('pydeface {} --outfile {} --force'.format(a,a))
            except:
                pass
            
            #Remove copied dicom directory if it exists in output directory (only applies to studies with weird multi-echo data)
            #if len(glob.glob('{}'.format(dicom_convert_dir))) > 0:
            if os.path.isdir('{}/{}'.format(output_dir, scans[i])):
                os.system('rm -rf {}/{}'.format(output_dir, scans[i]))

##Remove tmp files
#try:
#    shutil.rmtree('{}/tmp_dcm2bids'.format(output_dir))
#    shutil.rmtree('{}/tmp_dcmniix'.format(output_dir))
#except:
#    pass
                
