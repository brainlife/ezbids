import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit';
import axios from '../../axios.instance';
import toast from 'react-hot-toast';
import type { RootState } from '../index';
import { setPage } from './pageSlice';

import bidsEntities from '../../assets/schema/objects/entities.json';
import dwiDatatype from '../../assets/schema/rules/datatypes/dwi.json';
import anatDatatype from '../../assets/schema/rules/datatypes/anat.json';
import funcDatatype from '../../assets/schema/rules/datatypes/func.json';
import fmapDatatype from '../../assets/schema/rules/datatypes/fmap.json';
import petDatatype from '../../assets/schema/rules/datatypes/pet.json';
import megDatatype from '../../assets/schema/rules/datatypes/meg.json';
import perfDatatype from '../../assets/schema/rules/datatypes/perf.json';

// ── Types ────────────────────────────────────────────────────────────

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
    GeneratedBy: GeneratedByObject[];
    SourceDatasets: SourceDatasetObject;
}

export interface PatientInfo {
    PatientID: string;
    PatientName: string;
    PatientBirthDate: string;
}
export interface Session {
    exclude: boolean;
    AcquisitionDate: string;
    session: string;
}

export interface Subject {
    exclude: boolean;
    PatientInfo: PatientInfo[];
    subject: string;
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
    SeriesNumber: string;
    EchoTime: number;
    ImageType: string[];
    RepetitionTime: string;
    B0FieldIdentifier?: string[];
    B0FieldSource?: string[];
    series_idx: number;
    error: string;
    message: string;
    IntendedFor?: number[];
}

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
    pngPaths?: string[];
    headers?: any;
    events?: any;
    eventsBIDS?: IBIDSEvent[];
}

export interface IObject {
    idx: number;
    ModifiedSeriesNumber: string;
    exclude: boolean;
    _exclude: boolean;
    entities: any;
    _entities: any;
    validationErrors: string[];
    validationWarnings: string[];
    items: IObjectItem[];
    PED: string;
    series_idx: number;
    subject_idx: number;
    session_idx: number;
    message: string;
    _SeriesDescription: string;
    type: string;
    _type: string;
    AcquisitionDate: string;
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
    IntendedFor?: number[];
    B0FieldIdentifier: string[];
    B0FieldSource: string[];
    defaced?: boolean;
    defaceFailed?: boolean;
    defaceSelection: 'original' | 'defaced';
}

export interface OrganizedSession {
    sess: string;
    session_idx: number;
    objects: IObject[];
    AcquisitionDate: string;
}
export interface OrganizedSubject {
    sub: string;
    subject_idx: number;
    sess: OrganizedSession[];
}

// ── BIDS Schema ──────────────────────────────────────────────────────

interface BIDSSchemaEntities {
    suffixes: string[];
    extensions: string[];
    entities: any;
}
interface BIDSDatatypeOption {
    value: string;
    label: string;
    entities: string[];
}
interface BIDSDatatypes {
    [key: string]: { label: string; options: BIDSDatatypeOption[] };
}

function buildDatatypes(): BIDSDatatypes {
    const datatypes: BIDSDatatypes = {};
    const load = (modality: string, data: { [key: string]: BIDSSchemaEntities }, label: string) => {
        datatypes[modality] = { label, options: [] };
        for (const group of Object.values(data)) {
            group.suffixes.forEach((suffix: string) => {
                datatypes[modality].options.push({
                    value: modality + '/' + suffix,
                    label: suffix,
                    entities: group.entities,
                });
            });
        }
    };
    load('dwi', dwiDatatype as any, 'Diffusion');
    load('anat', anatDatatype as any, 'Anatomical');
    load('func', funcDatatype as any, 'Functional');
    load('fmap', fmapDatatype as any, 'Field Map');
    load('pet', petDatatype as any, 'PET');
    load('meg', megDatatype as any, 'MEG');
    load('perf', perfDatatype as any, 'Perfusion');
    return datatypes;
}

// ── Initial state ────────────────────────────────────────────────────

const defaultDatasetDescription: DatasetDescription = {
    Name: 'Untitled',
    BIDSVersion: '1.9.0',
    HEDVersion: [],
    DatasetLinks: [],
    DatasetType: 'raw',
    License: '',
    Authors: [],
    Acknowledgements: '',
    HowToAcknowledge: '',
    Funding: [],
    EthicsApprovals: [],
    ReferencesAndLinks: [],
    DatasetDOI: '',
    GeneratedBy: [
        {
            Name: 'ezBIDS',
            Version: '1.0.0',
            Description:
                'ezBIDS is a web-based tool for converting neuroimaging datasets to BIDS, requiring neither coding nor knowledge of the BIDS specification',
            CodeURL: 'https://brainlife.io/ezbids/',
            Container: { Type: 'docker', Tag: 'brainlife/ezbids-handler' },
        },
    ],
    SourceDatasets: { DOI: '', URL: '', Version: '' },
};

function createDefaultEzbids() {
    return {
        notLoaded: true,
        datasetDescription: { ...defaultDatasetDescription, GeneratedBy: [...defaultDatasetDescription.GeneratedBy] },
        readme: '',
        participantsColumn: {} as Record<string, any>,
        participantsInfo: {} as Record<string, any>,
        subjects: [] as Subject[],
        series: [] as Series[],
        objects: [] as IObject[],
        BIDSURI: false,
        _organized: [] as OrganizedSubject[],
        defacingMethod: '',
        includeExcluded: true,
        sideCar: {} as Record<string, any>,
    };
}

export type IEzbids = ReturnType<typeof createDefaultEzbids>;

interface EzbidsState {
    data: IEzbids;
    bidsSchema: {
        entities: any;
        datatypes: BIDSDatatypes;
    };
}

const initialState: EzbidsState = {
    data: createDefaultEzbids(),
    bidsSchema: {
        entities: bidsEntities,
        datatypes: buildDatatypes(),
    },
};

// ── Async thunks ─────────────────────────────────────────────────────

export const loadEzbids = createAsyncThunk('ezbids/loadEzbids', async (_, { getState }) => {
    const state = getState() as RootState;
    const session = state.session.data;
    const apihost = state.session.config.apihost;
    if (!session || !session.pre_finish_date) return null;
    try {
        const jwtRes = await axios.get(`${apihost}/download/${session._id}/token`);
        const res = await axios.get(`${apihost}/download/${session._id}/ezBIDS_core.json?token=${jwtRes.data}`);
        if (res.status === 200) {
            return res.data;
        }
    } catch (e) {
        console.error(e);
        toast.error('There was an error loading ezBIDS');
    }
    return null;
});

export const loadEzbidsUpdated = createAsyncThunk('ezbids/loadEzbidsUpdated', async (_, { getState, dispatch }) => {
    const state = getState() as RootState;
    const session = state.session.data;
    const apihost = state.session.config.apihost;
    if (!session || !session.pre_finish_date) return null;
    try {
        const res = await axios.get(`${apihost}/session/${session._id}/updated`);
        if (res.status === 200) {
            dispatch(setPage('finalize'));
            return res.data;
        }
    } catch (e) {
        console.error(e);
    }
    return null;
});

export const loadDefaceStatus = createAsyncThunk('ezbids/loadDefaceStatus', async (_, { getState }) => {
    const state = getState() as RootState;
    const session = state.session.data;
    const apihost = state.session.config.apihost;
    if (!session) return null;
    try {
        let jwtRes = await axios.get(`${apihost}/download/${session._id}/token`);
        const finished = await axios.get(`${apihost}/download/${session._id}/deface.finished?token=${jwtRes.data}`);
        const finishedIdxs: number[] = [];
        if (finished.status === 200) {
            const lines = finished.data
                .toString()
                .trim()
                .split('\n')
                .filter((v: string) => !!v);
            lines.forEach((v: string) => finishedIdxs.push(parseInt(v)));
        }
        jwtRes = await axios.get(`${apihost}/download/${session._id}/token`);
        const failed = await axios.get(`${apihost}/download/${session._id}/deface.failed?token=${jwtRes.data}`);
        const failedIdxs: number[] = [];
        if (failed.status === 200) {
            const lines = failed.data
                .toString()
                .trim()
                .split('\n')
                .filter((v: string) => !!v);
            lines.forEach((v: string) => failedIdxs.push(parseInt(v)));
        }
        return { finishedIdxs, failedIdxs };
    } catch (e) {
        console.error(e);
    }
    return null;
});

// ── Slice ────────────────────────────────────────────────────────────

function processEzbidsData(data: IEzbids, incoming: any) {
    Object.assign(data, incoming);
    data.series.forEach((s: Series) => {
        s.validationErrors = [];
        s.validationWarnings = [];
    });
    data.subjects.forEach((s: Subject) => {
        s.validationErrors = [];
        s.validationWarnings = [];
        s.exclude = !!s.exclude;
    });
    data.objects.forEach((o: IObject) => {
        o.exclude = !!o.exclude;
        o.validationErrors = [];
        o.validationWarnings = [];
        o.items.forEach((item) => {
            if (item.sidecar) {
                const sidecar = { ...item.sidecar };
                delete sidecar.SeriesInstanceUID;
                delete sidecar.StudyInstanceUID;
                delete sidecar.ReferringPhysicianName;
                delete sidecar.StudyID;
                delete sidecar.PatientName;
                delete sidecar.PatientID;
                delete sidecar.AccessionNumber;
                delete sidecar.PatientBirthDate;
                delete sidecar.PatientSex;
                delete sidecar.PatientWeight;
                delete sidecar.AcquisitionDateTime;
                item.sidecar = sidecar;
                item.sidecar_json = JSON.stringify(sidecar, null, 4);
            }
        });
    });
}

const ezbidsSlice = createSlice({
    name: 'ezbids',
    initialState,
    reducers: {
        updateEzbids(state, action: PayloadAction<any>) {
            processEzbidsData(state.data, action.payload);
        },
        setReadme(state, action: PayloadAction<string>) {
            state.data.readme = action.payload;
        },
        updateDDName(state, action: PayloadAction<string>) {
            state.data.datasetDescription.Name = action.payload;
        },
        addObject(state, action: PayloadAction<IObject>) {
            state.data.objects.push(action.payload);
        },
        organizeObjects(state) {
            // Sort objects
            state.data.objects.sort((a, b) => {
                const asub = a._entities?.subject ?? '';
                const bsub = b._entities?.subject ?? '';
                if (asub !== bsub) return asub.localeCompare(bsub);
                const ases = a._entities?.session ?? '';
                const bses = b._entities?.session ?? '';
                if (ases !== bses) return ases.localeCompare(bses);
                if (a.AcquisitionTime && b.AcquisitionTime) {
                    return a.AcquisitionTime.localeCompare(b.AcquisitionTime);
                }
                const apath = a.items[0]?.path ?? '';
                const bpath = b.items[0]?.path ?? '';
                if (apath !== bpath) return apath.localeCompare(bpath);
                return 0;
            });
            // Re-index and organize
            const organized: OrganizedSubject[] = [];
            state.data.objects.forEach((o, idx) => {
                o.idx = idx;
                const sub = o._entities?.subject ?? '';
                const sess = o._entities?.session ?? '';
                let subGroup = organized.find((s) => s.sub === sub);
                if (!subGroup) {
                    subGroup = { sub, subject_idx: o.subject_idx, sess: [] };
                    organized.push(subGroup);
                }
                let sesGroup = subGroup.sess.find((s) => s.sess === sess);
                if (!sesGroup) {
                    sesGroup = { sess, session_idx: o.session_idx, AcquisitionDate: o.AcquisitionDate, objects: [] };
                    subGroup.sess.push(sesGroup);
                }
                sesGroup.objects.push(o);
            });
            state.data._organized = organized;
        },
        resetEzbids(state) {
            state.data = createDefaultEzbids();
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(loadEzbids.fulfilled, (state, action) => {
                if (action.payload) {
                    action.payload.notLoaded = false;
                    processEzbidsData(state.data, action.payload);
                }
            })
            .addCase(loadEzbidsUpdated.fulfilled, (state, action) => {
                if (action.payload) {
                    processEzbidsData(state.data, action.payload);
                }
            })
            .addCase(loadDefaceStatus.fulfilled, (state, action) => {
                if (!action.payload) return;
                const { finishedIdxs, failedIdxs } = action.payload;
                finishedIdxs.forEach((idx) => {
                    const o = state.data.objects.find((o) => o.idx === idx);
                    if (o) o.defaced = true;
                });
                failedIdxs.forEach((idx) => {
                    const o = state.data.objects.find((o) => o.idx === idx);
                    if (o) o.defaceFailed = true;
                });
            });
    },
});

// ── Selectors ────────────────────────────────────────────────────────

export const selectBIDSEntities = (state: RootState) => (type: string) => {
    if (!type) return {};
    const modality = type.split('/')[0];
    const suffix = type.split('/')[1];
    const datatype = state.ezbids.bidsSchema.datatypes[modality];
    if (!datatype) return {};
    const option = datatype.options.find((o) => o.value === type);
    return option?.entities;
};

export const selectFindSubject =
    (state: RootState) =>
    (o: IObject): Subject | undefined => {
        return state.ezbids.data.subjects[o.subject_idx];
    };

export const selectFindSession =
    (state: RootState) =>
    (sub: Subject, o: IObject): Session | undefined => {
        return sub.sessions[o.session_idx];
    };

export const selectFindSubjectFromString =
    (state: RootState) =>
    (sub: string): Subject | undefined => {
        return state.ezbids.data.subjects.find((s) => s.subject === sub);
    };

export const { updateEzbids, setReadme, updateDDName, addObject, organizeObjects, resetEzbids } = ezbidsSlice.actions;
export default ezbidsSlice.reducer;
