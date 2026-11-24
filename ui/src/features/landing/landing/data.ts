// Numbers shown on the landing page. Counts come from the BIDS v1.11.2 schema
// (bidsschematools, schema 2.0.0) and from aimport's bids_brainlife_map.yaml; the
// scale ranges are typical acquisition values, order of magnitude only.

export const BIDS_VERSION = '1.11.2';

export const STATS = [
    { value: '16', label: 'BIDS datatypes', note: `v${BIDS_VERSION}` },
    { value: '118', label: 'file suffixes', note: '174 datatype/suffix pairs' },
    { value: '451', label: 'metadata fields', note: 'sidecars, tables' },
    { value: '160', label: 'brainlife mappings', note: '14 live · 7 planned · 139 drafts' },
];

// status: 'now' = ezBIDS on the web today (and aimport for anat/func/dwi/fmap);
// 'next' = aimport phases 2–4, in progress
export type Status = 'now' | 'next';

export interface Datatype {
    id: string;
    name: string;
    modality: string;
    suffixes: number; // BIDS v1.11.2 suffixes for this datatype
    mapped: number; // rows in bids_brainlife_map.yaml
    status: Status;
    where: string;
}

export const DATATYPES: Datatype[] = [
    {
        id: 'anat',
        name: 'Anatomical MRI',
        modality: 'MRI',
        suffixes: 40,
        mapped: 40,
        status: 'now',
        where: 'ezBIDS · aimport',
    },
    {
        id: 'func',
        name: 'Functional MRI',
        modality: 'MRI',
        suffixes: 9,
        mapped: 9,
        status: 'now',
        where: 'ezBIDS · aimport',
    },
    {
        id: 'dwi',
        name: 'Diffusion MRI',
        modality: 'MRI',
        suffixes: 11,
        mapped: 11,
        status: 'now',
        where: 'ezBIDS · aimport',
    },
    {
        id: 'fmap',
        name: 'Field maps',
        modality: 'MRI',
        suffixes: 18,
        mapped: 18,
        status: 'now',
        where: 'ezBIDS · aimport',
    },
    { id: 'perf', name: 'Perfusion (ASL)', modality: 'MRI', suffixes: 8, mapped: 8, status: 'now', where: 'ezBIDS' },
    { id: 'pet', name: 'PET', modality: 'PET', suffixes: 6, mapped: 6, status: 'now', where: 'ezBIDS' },
    { id: 'meg', name: 'MEG', modality: 'MEG', suffixes: 11, mapped: 12, status: 'now', where: 'ezBIDS' },
    {
        id: 'micr',
        name: 'Microscopy · OME-Zarr · PS-OCT',
        modality: 'Microscopy',
        suffixes: 19,
        mapped: 1,
        status: 'next',
        where: 'aimport phase 2',
    },
    { id: 'eeg', name: 'EEG', modality: 'EEG', suffixes: 9, mapped: 12, status: 'next', where: 'aimport phase 3' },
    {
        id: 'ieeg',
        name: 'Intracranial EEG',
        modality: 'iEEG',
        suffixes: 9,
        mapped: 9,
        status: 'next',
        where: 'aimport phase 3',
    },
    {
        id: 'nirs',
        name: 'Near-infrared spectroscopy',
        modality: 'NIRS',
        suffixes: 9,
        mapped: 9,
        status: 'next',
        where: 'aimport phase 3',
    },
    {
        id: 'emg',
        name: 'Electromyography',
        modality: 'EMG',
        suffixes: 9,
        mapped: 9,
        status: 'next',
        where: 'aimport phase 3',
    },
    {
        id: 'mrs',
        name: 'MR spectroscopy',
        modality: 'MRS',
        suffixes: 5,
        mapped: 5,
        status: 'next',
        where: 'aimport phase 4',
    },
    {
        id: 'motion',
        name: 'Motion capture',
        modality: 'Motion',
        suffixes: 6,
        mapped: 6,
        status: 'next',
        where: 'aimport phase 4',
    },
    {
        id: 'beh',
        name: 'Behavior',
        modality: 'Behavior',
        suffixes: 5,
        mapped: 5,
        status: 'next',
        where: 'aimport phase 4',
    },
    {
        id: 'phenotype',
        name: 'Phenotype & participants',
        modality: 'Tables',
        suffixes: 0,
        mapped: 0,
        status: 'now',
        where: 'ezBIDS · aimport',
    },
];

// a range on a log10 axis: [low, high] in base units (metres, seconds, bytes)
export interface Range {
    label: string;
    lo: number;
    hi: number;
    status: Status;
    note: string;
}

// smallest resolvable element, typical acquisitions
export const SPACE: Range[] = [
    {
        label: 'Microscopy',
        lo: 1e-9,
        hi: 1e-5,
        status: 'next',
        note: 'electron to light-sheet and PS-OCT: 1 nm – 10 µm',
    },
    {
        label: 'Anatomical MRI',
        lo: 1e-4,
        hi: 1.5e-3,
        status: 'now',
        note: 'ex vivo / 7 T to clinical: 0.1 – 1.5 mm voxels',
    },
    {
        label: 'Functional MRI',
        lo: 5e-4,
        hi: 3.5e-3,
        status: 'now',
        note: 'laminar 7 T to whole-brain 3 T: 0.5 – 3.5 mm',
    },
    { label: 'Diffusion MRI', lo: 1e-3, hi: 2.5e-3, status: 'now', note: '1 – 2.5 mm voxels' },
    { label: 'PET', lo: 1.5e-3, hi: 5e-3, status: 'now', note: 'scanner resolution 1.5 – 5 mm' },
    { label: 'iEEG', lo: 1e-3, hi: 1e-2, status: 'next', note: 'contact spacing 1 mm – 1 cm' },
    { label: 'MEG', lo: 5e-3, hi: 2e-2, status: 'now', note: 'source localisation 5 mm – 2 cm' },
    { label: 'MRS', lo: 5e-3, hi: 3e-2, status: 'next', note: 'spectroscopic voxels 5 mm – 3 cm' },
    { label: 'EEG', lo: 1e-2, hi: 5e-2, status: 'next', note: 'scalp sources 1 – 5 cm' },
    { label: 'NIRS', lo: 1e-2, hi: 3e-2, status: 'next', note: 'optode channels 1 – 3 cm' },
];

// sampling interval of a time series
export const TIME: Range[] = [
    { label: 'iEEG', lo: 3e-5, hi: 2e-3, status: 'next', note: '500 Hz – 30 kHz' },
    { label: 'EMG', lo: 5e-5, hi: 1e-3, status: 'next', note: '1 – 20 kHz' },
    { label: 'EEG', lo: 1e-4, hi: 4e-3, status: 'next', note: '250 Hz – 10 kHz' },
    { label: 'MEG', lo: 2e-4, hi: 2e-3, status: 'now', note: '500 Hz – 5 kHz' },
    { label: 'Motion', lo: 1e-3, hi: 1e-2, status: 'next', note: '100 Hz – 1 kHz' },
    { label: 'NIRS', lo: 1e-2, hi: 2e-1, status: 'next', note: '5 – 100 Hz' },
    { label: 'Functional MRI', lo: 4e-1, hi: 3, status: 'now', note: 'repetition time 0.4 – 3 s' },
    { label: 'Perfusion (ASL)', lo: 3, hi: 8, status: 'now', note: 'label/control pair 3 – 8 s' },
    { label: 'PET', lo: 10, hi: 600, status: 'now', note: 'dynamic frames 10 s – 10 min' },
    { label: 'Sessions', lo: 8.64e4, hi: 3.15e8, status: 'now', note: 'longitudinal: days to 10 years (ses- entity)' },
];

// size of one acquisition on disk
export const SIZE: Range[] = [
    { label: 'Behavior / events', lo: 1e3, hi: 1e6, status: 'next', note: 'tables: kB – MB' },
    { label: 'Anatomical MRI', lo: 5e6, hi: 2e8, status: 'now', note: '5 – 200 MB per image' },
    { label: 'PET', lo: 2e7, hi: 2e9, status: 'now', note: 'static to dynamic: 20 MB – 2 GB' },
    { label: 'Functional MRI', lo: 5e7, hi: 3e9, status: 'now', note: '50 MB – 3 GB per run' },
    { label: 'Diffusion MRI', lo: 1e8, hi: 5e9, status: 'now', note: '100 MB – 5 GB per scan' },
    { label: 'MEG', lo: 1e8, hi: 5e9, status: 'now', note: '100 MB – 5 GB per hour of recording' },
    { label: 'iEEG', lo: 1e9, hi: 5e10, status: 'next', note: '1 – 50 GB per session' },
    {
        label: 'Microscopy',
        lo: 1e10,
        hi: 1e14,
        status: 'next',
        note: 'whole-brain light-sheet: 10 GB – 100 TB (OME-Zarr)',
    },
];
