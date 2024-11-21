export interface ContainerObject {
    Type: string;
    Tag: string;
}

export interface GeneratedByObject {
    Name: string;
    Version: string;
    Description: string;
    CodeURL: string;
    Container: ContainerObject;
}

export interface SourceDatasetObject {
    DOI: string;
    URL: string;
    Version: string;
}

export interface DatasetDescription {
    Name: string;
    BIDSVersion: string;
    HEDVersion: string[];
    DatasetLinks: string[];
    DatasetType: string;
    License: string;
    Authors: string[];
    Acknowledgements: string;
    HowToAcknowledge: string;
    Funding: string[];
    EthicsApprovals: string[];
    ReferencesAndLinks: string[];
    DatasetDOI: string;
    GeneratedBy: [GeneratedByObject];
    SourceDatasets: SourceDatasetObject;
}

export interface PatientInfo {
    PatientID: string;
    PatientName: string;
    PatientBirthDate: string;
}

export interface Subject {
    exclude: boolean;

    PatientInfo: PatientInfo[];

    subject: string; //subject name mapped to this subject

    validationErrors: string[];
    validationWarnings: string[];

    sessions: Session[];
}

export interface Series {
    entities: any;

    PED: string;

    validationErrors: string[];
    validationWarnings: string[];

    type: string;

    SeriesDescription: string;
    SeriesNumber: string; //used to sort object by it
    EchoTime: number;
    ImageType: [string];
    RepetitionTime: string;

    B0FieldIdentifier?: string[];
    B0FieldSource?: string[];

    series_idx: number;

    error: string;
    message: string;

    IntendedFor?: number[]; //for storing which object id the object is intended for

    // metadata_requirements: [MetadataChecks]; // Remove?
}

export interface Session {
    exclude: boolean;
    AcquisitionDate: string;
    session: string; //empty string if not session map
}

//https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/05-task-events.html
export interface IBIDSEvent {
    onset: number;
    duration: number;
    sample?: number;
    trial_type?: string;
    response_time?: number;
    value?: string | number;
    HED?: string;
    stim_file?: string;
}

export interface IObjectItem {
    sidecar: any;
    sidecar_json: string;

    path: string;
    name?: string;
    pngPaths?: string[]; //array of png file paths
    headers?: any; //for nifti

    events?: any; //for event (contains object parsed by createEventObjects)
    eventsBIDS?: IBIDSEvent[];
}
export interface IObject {
    idx: number; //set by organizeObjects after re-sorting

    ModifiedSeriesNumber: string;

    exclude: boolean;
    _exclude: boolean; //set if it's excluded on parent level

    entities: any; //entities set for this object only
    _entities: any; //"prototypical"(flattened) entities from parent objects (subject / series).. see mapObject()

    validationErrors: string[]; //right?
    validationWarnings: string[]; //right?

    items: [IObjectItem];

    PED: string;

    series_idx: number;
    subject_idx: number;
    session_idx: number;

    message: string;

    _SeriesDescription: string; //copied from series for quick ref
    type: string; //override
    _type: string;

    //primary key for session - but we want to keep these for sorting purpose
    AcquisitionDate: string;
    //AcquisitionDateTime: string; //ISO - only used to sort objects
    AcquisitionTime: string;
    SeriesNumber: string;

    analysisResults: {
        errors: string[];
        warnings: string[];
        section_id: number;
        NumVolumes?: number;
        filesize?: number;
        orientation?: string;
    };

    IntendedFor?: number[]; //for storing which object id the object is intended for

    B0FieldIdentifier: string[];
    B0FieldSource: string[];

    defaced?: boolean;
    defaceFailed?: boolean;
    defaceSelection: 'original' | 'defaced';
}

export interface BIDSSchemaEntities {
    suffixes: string[];
    extensions: string[];
    entities: any;
}

export interface BIDSEntities {
    [key: string]: {
        //task, subject, session, etc..
        name: string;
        entity: string;
        description: string;
        type: string;
        format: string;
    };
}

export interface BIDSDatatypeOption {
    value: string; //modality/suffix
    label: string; //suffix for now?
    entities: string[];
}

export interface BIDSDatatypes {
    [key: string]: {
        //anat, dwi, etc..
        label: string; //modality label
        options: BIDSDatatypeOption[];
    };
}

export interface OrganizedSession {
    sess: string;
    session_idx: number;
    objects: IObject[]; //all object under this subject/session
    AcquisitionDate: string; //TODO.. should be Date?
}

export interface OrganizedSubject {
    sub: string;
    subject_idx: number;
    sess: OrganizedSession[];
}

export interface ISession {
    _id: string;
    ownerId: number;
    allowedUsers: number[];
    create_date: string; //"2021-08-27T21:24:21.610Z"
    dicomCount: number; //2
    dicomDone: number; //2
    request_headers: any; //{host: "dev1.soichi.us", x-real-ip: "45.16.200.251", x-forwarded-for: "45.16.200.251", x-forwarded-proto: "https", connection: "close", …}
    status: string; //"analyzed"
    status_msg: string; //"successfully run preprocess.sh"

    update_date: string; //"2021-08-27T21:25:25.654Z"

    upload_finish_date?: string; //"2021-08-27T21:24:45.064Z"

    pre_begin_date?: string; //"2021-08-27T21:24:46.914Z"
    pre_finish_date?: string; //"2021-08-27T21:25:25.405Z"

    deface_begin_date?: string;
    deface_finish_date?: string;

    finalize_begin_date?: string;
    finalize_finish_date?: string;
}

export type EzbidsProcessingMode = 'EDGE' | 'SERVER' | null;

export interface IEZBIDS {
    notLoaded: boolean;
    datasetDescription: DatasetDescription;
    readme: string;
    participantsColumn: { [key: string]: any };
    participantsInfo: { [key: string]: any };
    subjects: Subject[];
    series: Series[];
    objects: IObject[];
    BIDSURI: boolean;
    _organized: OrganizedSubject[];
    defacingMethod: string;
    includeExcluded: boolean;
    sideCar: { [key: string]: any };
}
export interface IEvents {
    columns: {
        onsetLogic: string; // eq
        onset: string | null;
        onset2: string | null;
        onsetUnit: string; // sec
        durationLogic: string; // eq
        duration: string | null;
        duration2: string | null;
        durationUnit: string; // sec
        sampleLogic: string; // eq
        sample: string | null;
        sample2: string | null;
        sampleUnit: string; // samples
        trialType: string | null;
        responseTimeLogic: string; // eq
        responseTime: string | null;
        responseTime2: string | null;
        responseTimeUnit: string; // sec
        value: string | null;
        HED: string | number | null;
        stim_file: string | null;
    };
    trialTypes: {
        longName: string;
        desc: string;
        levels: { [key: string]: string };
    };
    columnKeys: string[] | null;
    sampleValues: { [key: string]: string[] };
    loaded: boolean;
}

export interface BIDSDatatypeMetadataOptionConditions {
    metadata: string;
    value: string;
}

export interface BIDSDatatypeMetadataOptionMetadata {
    name: string;
    requirement: string | undefined;
    description: string;
}

export interface BIDSDatatypeMetadataOption {
    value: string;
    label: string;
    conditions: BIDSDatatypeMetadataOptionConditions[];
    metadata: BIDSDatatypeMetadataOptionMetadata[];
}

export interface BIDSDatatypesMetadata {
    [key: string]: {
        label: string;
        options: BIDSDatatypeMetadataOption[];
    };
}

export interface Selector {
    [key: string]: any;
}

export interface Field {
    [key: string]: any;
}

export interface MetadataFields {
    [key: string]: {
        selectors: Selector[];
        fields: {
            [key: string]: Field;
        };
    };
}
