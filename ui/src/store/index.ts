import { createStore } from 'vuex';
import bidsEntities from '../assets/schema/objects/entities.json';
import {
    BIDSDatatypes,
    BIDSDatatypesMetadata,
    BIDSSchemaEntities,
    ContainerObject,
    DatasetDescription,
    EzbidsProcessingMode,
    IEvents,
    IEZBIDS,
    IObject,
    ISession,
    OrganizedSubject,
    Series,
    Session,
    SourceDatasetObject,
    Subject,
} from './store.types';
import api from '../api';
import dwiDatatype from '../assets/schema/rules/datatypes/dwi.json';
import anatDatatype from '../assets/schema/rules/datatypes/anat.json';
import funcDatatype from '../assets/schema/rules/datatypes/func.json';
import fmapDatatype from '../assets/schema/rules/datatypes/fmap.json';
import petDatatype from '../assets/schema/rules/datatypes/pet.json';
import megDatatype from '../assets/schema/rules/datatypes/meg.json';
import perfDatatype from '../assets/schema/rules/datatypes/perf.json';
import { ElNotification } from 'element-plus';

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
    ezbidsProcessingMode: null as EzbidsProcessingMode,

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
        BIDSURI: false,

        _organized: [] as OrganizedSubject[], //above things are organized into subs/ses/run/object hierarchy for quick access

        defacingMethod: '',
        includeExcluded: true,
        sideCar: {} as { [key: string]: any },
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
        } as IEvents, // looks like we references events both inside the ezBIDS objects as well as outside in the parent state object... TODO - validate this
    } as IEZBIDS,

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
    } as IEvents,
};

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

loadDatatype('dwi', dwiDatatype, 'Diffusion');
loadDatatype('anat', anatDatatype, 'Anatomical');
loadDatatype('func', funcDatatype, 'Functional');
loadDatatype('fmap', fmapDatatype, 'Field Map');
loadDatatype('pet', petDatatype, 'PET');
loadDatatype('meg', megDatatype, 'MEG');
loadDatatype('perf', perfDatatype, 'Perfusion');

const store = createStore({
    state,

    mutations: {
        setSession(state, session) {
            state.session = session;
            if (session._id) window.location.hash = session._id;
        },

        setEzBidsProcessingMode(state, mode: EzbidsProcessingMode) {
            state.ezbidsProcessingMode = mode;
        },

        setPage(state, page) {
            state.page = page;
        },

        reset(state) {
            state.session = null;
            state.page = 'upload'; //current page
            state.ezbidsProcessingMode = null; // reset processing mode
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
                BIDSURI: false,

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
            const res = await api.getSessionById(context.state.session._id);
            if (!res.session) {
                throw new Error('No session found!');
            }
            context.commit('setSession', res.session);
            if (res.ezbidsProcessingMode) {
                context.commit('setEzBidsProcessingMode', res.ezbidsProcessingMode);
            }
        },

        async loadEzbids(context) {
            if (!context.state.session || !context.state.session.pre_finish_date) return;
            const res = await api.getEZBIDSCoreJSONFile(context.state.session._id);
            if (res !== null) {
                context.commit('updateEzbids', {
                    ...res,
                    notLoaded: false,
                } as IEZBIDS);
            }
        },

        // ANIBAL-TODO: Please confirm, but I don't think that this functionality is used, or it's currently broken...
        // I don't think that this is ever used anywhere. I don't see anywhere in the codebase where "updated"
        // is set in the backend models.ezBIDS mongoDB object. We may be able to remove this. IF SO,
        // then also remove the "getEZBIDSUpdated" function in api/index.ts.
        async loadEzbidsUpdated(context) {
            if (!context.state.session || !context.state.session.pre_finish_date) return;

            const res = await api.getEZBIDSUpdated(context.state.session._id);
            if (res !== null) {
                context.commit('updateEzbids', { ...res });
                context.commit('updateEvents', res.events);
                context.commit('setPage', 'finalize');
            }
        },

        async loadDefaceStatus(context) {
            if (!context.state.session) return;
            try {
                const res = await api.getDefaceStatus(context.state.session._id);
                if (res === null) return; // likely still processing

                if (res.status === 'FINISHED') {
                    const finishedText = res.defaceContents;
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
                } else {
                    const failedText = res.defaceContents;
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
                ElNotification({
                    title: 'Could not get deface status',
                    message: '',
                    type: 'error',
                });
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
