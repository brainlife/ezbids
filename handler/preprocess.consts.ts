export const BIDSIGNORE_ENTRIES = [
    '*finalized.json',
    '*template.json',
    '*dcm2niix*',
    '*preprocess*',
    '*pet2bids*',
    '*list',
    '*nii_files',
    '*ezBIDS_core.json',
    '*bids_compliant.log',
    '*validator.log',
    '*.png',
    '*unprocessed_list*',
];

export const MAX_PARALLEL = 6;
export const CMD_TIMEOUT_MS = 3600 * 1000;
