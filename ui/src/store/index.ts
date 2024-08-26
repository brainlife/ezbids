import { createStore } from 'vuex';

import bidsEntities from '../assets/schema/objects/entities.json';
import axios from '../axios.instance';

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

interface BIDSSchemaEntities {
    suffixes: string[];
    extensions: string[];
    entities: any;
}

interface BIDSEntities {
    [key: string]: {
        //task, subject, session, etc..
        name: string;
        entity: string;
        description: string;
        type: string;
        format: string;
    };
}

interface BIDSDatatypeOption {
    value: string; //modality/suffix
    label: string; //suffix for now?
    entities: string[];
}

interface BIDSDatatypes {
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

const state = {
    bidsSchema: {
        entities: bidsEntities,
        datatypes: {} as BIDSDatatypes,
        metadata: {} as BIDSDatatypesMetadata,
    },

    config: {
        apihost: import.meta.env.VITE_APIHOST || '/api/ezbids',
        authhost: process.env.NODE_ENV === 'development' ? 'http://localhost:8080/api/auth' : '/api/auth',
        authSignIn: '/auth/#!/signin',
        authSignOut: '/auth/#!/signout',
        debug: process.env.NODE_ENV == 'development' ? true : false,
    },

    session: null as ISession | null,
    page: 'upload',

    //current state of the session
    //TODO: WATCH OUT - this gets wiped out when we load ezBIDS_core.json from analyzer
    ezbids: {
        notLoaded: true,

        //pretty much straight out of bids/dataset_description.json
        datasetDescription: {
            Name: 'Untitled',
            BIDSVersion: '1.9.0',
            HEDVersion: [],
            DatasetLinks: [],
            DatasetType: 'raw',
            License: '',
            Authors: [],
            Acknowledgements: '', //"Special thanks to Korbinian Brodmann for help in formatting this dataset in BIDS. We thank Alan Lloyd Hodgkin and Andrew Huxley for helpful comments and discussions about the experiment and manuscript; Hermann Ludwig He  lmholtz for administrative support; and Claudius Galenus for providing data for the medial-to-lateral index analysis.",
            HowToAcknowledge: '', //"Please cite this paper: https://www.ncbi.nlm.nih.gov/pubmed/001012092119281",
            Funding: [
                //"National Institute of Neuroscience Grant F378236MFH1",
                //"National Institute of Neuroscience Grant 5RMZ0023106"
            ],
            EthicsApprovals: [
                //"Army Human Research Protections Office (Protocol ARL-20098-10051, ARL 12-040, and ARL 12-041)"
            ],
            ReferencesAndLinks: [
                //"https://www.ncbi.nlm.nih.gov/pubmed/001012092119281",items
                //"http://doi.org/1920.8/jndata.2015.7"
            ],
            DatasetDOI: '', //"10.0.2.3/dfjj.10"
            GeneratedBy: [
                {
                    Name: 'ezBIDS',
                    Version: '1.0.0',
                    Description:
                        'ezBIDS is a web-based tool for converting neuroimaging datasets to BIDS, requiring neither coding nor knowledge of the BIDS specification',
                    CodeURL: 'https://brainlife.io/ezbids/',
                    Container: {
                        Type: 'docker',
                        Tag: 'brainlife/ezbids-handler',
                    } as ContainerObject,
                },
            ],
            SourceDatasets: {
                DOI: '',
                URL: '',
                Version: '',
            } as SourceDatasetObject,
        } as DatasetDescription,

        readme: '',
        participantsColumn: {},
        participantsInfo: {},

        //here lives various things
        subjects: [] as Subject[],
        series: [] as Series[],
        objects: [] as IObject[],

        _organized: [] as OrganizedSubject[], //above things are organized into subs/ses/run/object hierarchy for quick access

        defacingMethod: '',
        includeExcluded: true,
        sideCar: {} as { [key: string]: any },
    },

    events: {
        columns: {
            //these are just for typescript definitions.
            //real initial values should come from mapEventColumns()

            onsetLogic: 'eq',
            onset: null, //will be set to column name in event
            onset2: null, //will be set to column name in event
            onsetUnit: 'sec',

            durationLogic: 'eq',
            duration: null,
            duration2: null, //used in case durationLogic is "subtract" or "add"
            durationUnit: 'sec',

            sampleLogic: 'eq',
            sample: null,
            sample2: null,
            sampleUnit: 'samples',

            trialType: null,

            responseTimeLogic: 'eq',
            responseTime: null,
            responseTime2: null,
            responseTimeUnit: 'sec',

            value: null,

            HED: null,

            stim_file: null,
        },

        trialTypes: {
            longName: 'Event category',
            desc: 'Indicator of type of action that is expected',
            levels: {} as { [key: string]: string }, //description for each trialType values
        },

        columnKeys: null as string[] | null,
        sampleValues: {} as { [key: string]: string[] },
        loaded: false,
    },
};
export type IEzbids = typeof state.ezbids;
export type IEvents = typeof state.events;

interface BIDSDatatypeMetadataOptionConditions {
    metadata: string;
    value: string;
}

interface BIDSDatatypeMetadataOptionMetadata {
    name: string;
    requirement: string | undefined;
    description: string;
}

interface BIDSDatatypeMetadataOption {
    value: string;
    label: string;
    conditions: BIDSDatatypeMetadataOptionConditions[];
    metadata: BIDSDatatypeMetadataOptionMetadata[];
}

interface BIDSDatatypesMetadata {
    [key: string]: {
        label: string;
        options: BIDSDatatypeMetadataOption[];
    };
}

interface Selector {
    [key: string]: any;
}

interface Field {
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

function loadDatatype(modality: string, datatypes: { [key: string]: BIDSSchemaEntities }, label: string) {
    state.bidsSchema.datatypes[modality] = { label, options: [] };
    for (const group of Object.values(datatypes)) {
        //datatype.forEach(group=>{
        group.suffixes.forEach((suffix: string) => {
            state.bidsSchema.datatypes[modality].options.push({
                value: modality + '/' + suffix,
                label: suffix, //bold, cbv, sbref, events, etc..
                entities: group.entities, //["subject", "session", etc..]
            });
        });
    }
}

import dwiDatatype from '../assets/schema/rules/datatypes/dwi.json';
loadDatatype('dwi', dwiDatatype, 'Diffusion');

import anatDatatype from '../assets/schema/rules/datatypes/anat.json';
loadDatatype('anat', anatDatatype, 'Anatomical');

import funcDatatype from '../assets/schema/rules/datatypes/func.json';
loadDatatype('func', funcDatatype, 'Functional');

import fmapDatatype from '../assets/schema/rules/datatypes/fmap.json';
loadDatatype('fmap', fmapDatatype, 'Field Map');

import petDatatype from '../assets/schema/rules/datatypes/pet.json';
loadDatatype('pet', petDatatype, 'PET');

import megDatatype from '../assets/schema/rules/datatypes/meg.json';
loadDatatype('meg', megDatatype, 'MEG');

import behDatatype from '../assets/schema/rules/datatypes/beh.json';
loadDatatype('beh', behDatatype, 'Behavioral');

import perfDatatype from '../assets/schema/rules/datatypes/perf.json';

import { ElNotification } from 'element-plus';
loadDatatype('perf', perfDatatype, 'Perfusion');

const store = createStore({
    state,

    mutations: {
        setSession(state, session) {
            state.session = session;
            if (session._id) window.location.hash = session._id;
        },

        setPage(state, page) {
            state.page = page;
        },

        reset(state) {
            state.session = null;
            state.page = 'upload'; //current page
            state.ezbids = {
                notLoaded: true,

                datasetDescription: {
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
                            Container: {
                                Type: 'docker',
                                Tag: 'brainlife/ezbids-handler',
                            },
                        },
                    ],
                    SourceDatasets: {
                        DOI: '',
                        URL: '',
                        Version: '',
                    },
                },

                readme: '',
                participantsColumn: {},
                participantsInfo: {},

                //here lives various things
                subjects: [],
                series: [],
                objects: [],

                _organized: [], //above things are organized into subs/ses/run/object hierarchy for quick access

                defacingMethod: '',
                includeExcluded: true,
                sideCar: {},
            };

            Object.assign(state.events, {
                columnKeys: null,
                sampleValues: {},
                loaded: false,
            });
        },

        updateEzbids(state, ezbids) {
            Object.assign(state.ezbids, ezbids);
            state.ezbids.series.forEach((s: Series) => {
                s.validationErrors = [];
                s.validationWarnings = [];
                /* can't remove directly on entities - which is stored in schema (maybe clone it?)
                delete s.entities.subject;
                delete s.entities.session;
                */
            });

            state.ezbids.subjects.forEach((s) => {
                s.validationErrors = [];
                s.validationWarnings = [];
                s.exclude = !!s.exclude;
            });

            state.ezbids.objects.forEach((o: IObject) => {
                o.exclude = !!o.exclude;
                o.validationErrors = [];
                o.validationWarnings = [];
                o.items.forEach((item) => {
                    if (item.sidecar) {
                        //anonymize..
                        let sidecar = Object.assign({}, item.sidecar);

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

                        // Don't need this (I think) if we're relying on MNE-BIDS
                        // if (sidecar.Modality === 'MEG') {
                        //     delete sidecar.AcquisitionDate;
                        //     delete sidecar.AcquisitionTime;
                        //     delete sidecar.Modality;
                        //     delete sidecar.ConversionSoftware;
                        //     delete sidecar.SeriesDescription;
                        // }

                        item.sidecar = sidecar;
                        item['sidecar_json'] = JSON.stringify(sidecar, null, 4);
                    }
                });
            });
        },

        updateEvents(state, events) {
            Object.assign(state.events, events);
        },

        setEzbidsReadme(state, v) {
            state.ezbids.readme = v;
        },

        updateDDName(state, v) {
            state.ezbids.datasetDescription.Name = v;
        },

        updateSessionAllowedUsers(state, updatedUsers) {
            if (!state.session) return;
            state.session.allowedUsers = updatedUsers;
        },

        organizeObjects(state) {
            //mapObjects() must be called before calling this action (for _entities)

            //sort object by subject / session / series # / json path
            state.ezbids.objects.sort((a, b) => {
                const asub_id = a._entities.subject;
                const bsub_id = b._entities.subject;
                if (asub_id !== bsub_id) return asub_id.localeCompare(bsub_id);

                const ases_id = a._entities.session;
                const bses_id = b._entities.session;
                if (ases_id !== bses_id) return ases_id.localeCompare(bses_id);

                // NOTE: Shouldn't use this anymore, use AcquisitionTime instead (more thorough)
                // const amodseriesnum = a.ModifiedSeriesNumber;
                // const bmodseriesnum = b.ModifiedSeriesNumber;
                // if (amodseriesnum && bmodseriesnum && amodseriesnum != bmodseriesnum)
                //     return amodseriesnum.localeCompare(bmodseriesnum);

                const aAcqTime = a.AcquisitionTime;
                const bAcqTime = b.AcquisitionTime;
                if (aAcqTime && bAcqTime) {
                    return aAcqTime.localeCompare(bAcqTime);
                }

                const apath = a.items[0].path;
                const bpath = b.items[0].path;
                if (apath && bpath && apath != bpath) return apath.localeCompare(bpath);

                return 0;
            });

            //re-index and organize
            state.ezbids._organized = [];
            state.ezbids.objects.forEach((o, idx) => {
                o.idx = idx; //reindex

                let sub = o._entities.subject;
                let sess = o._entities.session;

                let subGroup = state.ezbids._organized.find((s) => s.sub == sub);
                if (!subGroup) {
                    subGroup = {
                        sub,
                        subject_idx: o.subject_idx,
                        sess: [],
                    };
                    state.ezbids._organized.push(subGroup);
                }

                let sesGroup = subGroup.sess.find((s) => s.sess == sess);
                if (!sesGroup) {
                    sesGroup = {
                        sess,
                        session_idx: o.session_idx,
                        AcquisitionDate: o.AcquisitionDate,
                        objects: [],
                    };
                    subGroup.sess.push(sesGroup);
                }
                sesGroup.objects.push(o);
            });
        },

        addObject(state, o) {
            state.ezbids.objects.push(o);
        },
    },

    actions: {
        async reload(context, id) {
            context.commit('reset');
            context.commit('setSession', {
                _id: id,
            });
            await context.dispatch('loadSession');
            await context.dispatch('loadEzbids'); //might not yet exist
            await context.dispatch('loadEzbidsUpdated'); //might not yet exist
        },

        async loadSession(context) {
            if (!context.state.session) return;
            const res = await axios.get(`${context.state.config.apihost}/session/${context.state.session._id}`);
            context.commit('setSession', res.data);
        },

        async loadEzbids(context) {
            if (!context.state.session || !context.state.session.pre_finish_date) return;
            try {
                const jwtRes = await axios.get(
                    `${context.state.config.apihost}/download/${context.state.session._id}/token`
                );
                const res = await axios.get(
                    `${context.state.config.apihost}/download/${context.state.session._id}/ezBIDS_core.json?token=${jwtRes.data}`
                );
                if (res.status === 200) {
                    const conf = await res.data;
                    conf.notLoaded = false;
                    context.commit('updateEzbids', conf);
                }
            } catch (e) {
                console.error(e);
                ElNotification({
                    message: 'There was an error loading ezBIDS',
                    type: 'error',
                });
            }
        },

        async loadEzbidsUpdated(context) {
            if (!context.state.session || !context.state.session.pre_finish_date) return;
            try {
                const res = await axios.get(
                    `${context.state.config.apihost}/session/${context.state.session._id}/updated`
                );
                if (res.status == 200) {
                    const updated = await res.data;
                    context.commit('updateEzbids', updated);
                    context.commit('updateEvents', updated.events);
                    context.commit('setPage', 'finalize');
                }
            } catch (e) {
                console.error(e);
            }
        },

        async loadDefaceStatus(context) {
            if (!context.state.session) return;

            try {
                let jwtRes = await axios.get(
                    `${context.state.config.apihost}/download/${context.state.session._id}/token`
                );
                const finished = await axios.get(
                    `${context.state.config.apihost}/download/${context.state.session._id}/deface.finished?token=${jwtRes.data}`
                );
                if (finished.status == 200) {
                    const finishedText = await finished.data;
                    const idxs = finishedText
                        .toString()
                        .trim()
                        .split('\n')
                        .filter((v: any) => !!v)
                        .map((v: string) => parseInt(v));
                    idxs.forEach((idx: number) => {
                        let o = context.state.ezbids.objects.find((o) => o.idx == idx);
                        if (!o) console.error("can't find", idx);
                        else o.defaced = true;
                    });
                }

                jwtRes = await axios.get(`${context.state.config.apihost}/download/${context.state.session._id}/token`);
                const failed = await axios.get(
                    `${context.state.config.apihost}/download/${context.state.session._id}/deface.failed?token=${jwtRes.data}`
                );
                if (failed.status == 200) {
                    const failedText = await failed.data;
                    const idxs = failedText
                        .trim()
                        .split('\n')
                        .filter((v: any) => !!v)
                        .map((v: string) => parseInt(v));
                    idxs.forEach((idx: number) => {
                        let o = context.state.ezbids.objects.find((o) => o.idx === idx);
                        if (!o) console.error("can't find", idx);
                        else o.defaceFailed = true;
                    });
                }
            } catch (e) {
                console.error(e);
            }
        },
    },

    getters: {
        //from "anat/t1w", return entities object {subject: required, session: optional, etc..}
        getBIDSEntities: (state) => (type: string) => {
            if (!type) return {};
            const modality = type.split('/')[0];
            const suffix = type.split('/')[1];
            let datatype = state.bidsSchema.datatypes[modality];
            if (!datatype) return {};

            //find the option that contains our suffix
            const option = datatype.options.find((option) => option.value == type);

            return option?.entities;
        },

        //find a session inside sub hierarchy
        findSession:
            (state) =>
            (sub: Subject, o: IObject): Session | undefined => {
                return sub.sessions[o.session_idx];
            },

        findSubject:
            (state) =>
            (o: IObject): Subject | undefined => {
                return state.ezbids.subjects[o.subject_idx];
            },

        findSubjectFromString:
            (state) =>
            (sub: string): Subject | undefined => {
                return state.ezbids.subjects.find((s: Subject) => s.subject == sub);
            },
    },
});

export default store;
