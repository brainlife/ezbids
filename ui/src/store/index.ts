
import { createStore } from 'vuex'

import bidsEntities from '../assets/schema/entities.json'

/*
interface Session {
    _id: string;
}
*/

export interface DatasetDescription {
    Name: string;    
    BIDSVersion: string;    
    DatasetType: string;                                                                                   
    License: string;      
    Authors: string[]; 
    Acknowledgements: string;
    HowToAcknowledge: string;
    Funding: string[];               
    EthicsApprovals: string[];                     
    ReferencesAndLinks: string[];
    DatasetDOI: string;                                                                                       
}

export interface PatientInfo {
    PatientID: string;
    PatientName: string;
    PatientBirthDate: string;
}
export interface Subject {
    exclude: boolean;

    PatientInfo: PatientInfo[];

    phenotype: any;

    subject: string; //subject name mapped to this subject
    validationErrors: string[];

    sessions: Session[];
}

export interface Series {
    entities: any;
    validationErrors: string[];
    type: string; 
    forType: string;

    SeriesDescription: string;
    EchoTime: number;
    ImageType: [string];
    RepetitionTime: string;
    
    error: string;
    message: string;
    object_indices: [ number ];
}

export interface Session {
    exclude: boolean;
    AcquisitionDate: string;
    session: string; //empty string if not session map
}

export interface IObject {
    idx: number; //set by organizeObjects after re-sorting

    exclude: boolean;
    _exclude: boolean; //set if it's excluded on parent level
    
    entities: any; //entities set for this object only
    _entities: any; //"prototypical"(flattened) entities from parent objects (subject / series).. see mapObject()

    validationErrors: string[]; //right?
    items: [{
        sidecar: any;
        sidecar_json: string;

        path?: string;
        name?: string;
        headers?: any; //for nifti
    }];

    series_idx: number;
    _SeriesDescription: string; //copied from series for quick ref 
    type: string; //override
    _type: string; 
    _forType: string;

    //primary keys
    PatientName: string;
    PatientID: string;
    PatientBirthDate: string;

    AcquisitionDate: string;
    pngPath: string;
    analysisResults: {
        NumVolumes: number;
        errors: string[];
        filesize: number;
        section_ID: number;
    };

    paths: [string];

    IntendedFor?: number[]; //for fmap/ to store which object id the object is intended for

    defaced?: boolean;
    defaceFailed?: boolean;
    defaceSelection: "original" | "defaced" 
}

interface BIDSSchemaEntities {
    suffixes: string[];
    extensions: string[];
    entities: any;
}

interface BIDSEntities {
    [key: string]: { //task, subject, session, etc..
        name: string;
        entity: string;
        format: string;
        description: string;      
    }
}

interface BIDSDatatypeOption {
    value: string; //modality/suffix
    label: string; //suffix for now?
    entities: string[];
}

interface BIDSDatatypes {
    [key: string]: { //anat, dwi, etc..
        label: string; //modality label
        options: BIDSDatatypeOption[];
    }
}

export interface OrganizedSession {
    objects: IObject[], //all object under this subject/session
    AcquisitionDate: string, //TODO.. should be Date?
}

export interface OrganizedSubject {
    objects: IObject[], //all objects under this subject
    sess: {
        [key: string]: OrganizedSession;
    } 
}

export interface OrganizedSubjects {
    [key: string]: OrganizedSubject;
}

export interface ISession {
    _id: string;

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
    //counter: 0,
    bidsSchema: {
        entities: bidsEntities as BIDSEntities, //await import('../assets/schema/entities.json'), //aka "bids_entities"
        datatypes: {} as BIDSDatatypes,
    },

    config: {
        apihost: (process.env.NODE_ENV == "development") ? "https://dev1.soichi.us/api/easybids" : "/api/ezbids",
        debug: (process.env.NODE_ENV == "development")?true:false,
    },

    session: null as ISession|null,

    //current state of the session
    ezbids: {
        notLoaded: true,

        //pretty much straight out of bids/dataset_description.json
        datasetDescription: {                                                                                       
            Name: "",                                                                                     
            BIDSVersion: "",                                                                                 
            DatasetType: "",                                                                                   
            License: "",                                                                                       
            Authors: [                                                                                            
                "Soichi Hayashi",                                                                                   
                "Dan Levitas"                                                                                       
            ],                                                                                                      
            Acknowledgements: "", //"Special thanks to Korbinian Brodmann for help in formatting this dataset in BIDS. We tha  nk Alan Lloyd Hodgkin and Andrew Huxley for helpful comments and discussions about the experiment and manuscript; Hermann Ludwig He  lmholtz for administrative support; and Claudius Galenus for providing data for the medial-to-lateral index analysis.",
            HowToAcknowledge: "", //"Please cite this paper: https://www.ncbi.nlm.nih.gov/pubmed/001012092119281",
            Funding: [                                                                                            
                //"National Institute of Neuroscience Grant F378236MFH1",                                           
                //"National Institute of Neuroscience Grant 5RMZ0023106"                                            
            ],                                                                                                      
            EthicsApprovals: [                                                                                    
                //"Army Human Research Protections Office (Protocol ARL-20098-10051, ARL 12-040, and ARL 12-041)"   
            ],                                                                                                      
            ReferencesAndLinks: [                                                                                 
                //"https://www.ncbi.nlm.nih.gov/pubmed/001012092119281",                                            
                //"http://doi.org/1920.8/jndata.2015.7"                                                             
            ],                                                                                                      
            DatasetDOI: "", //"10.0.2.3/dfjj.10"                                                                  
        } as DatasetDescription,                                                                                                          

        readme: "edit me",                                                                                          
        participantsColumn: {}, 

        //here lives various things
        subjects: [] as Subject[],                                                                                               
        series: [] as Series[],                                                                                                 
        objects: [] as IObject[],                                                                                                

        _organized: {} as OrganizedSubjects, //above things are organized into subs/ses/run/object hierarchy for quick access

        defacingMethod: "",
    },

    //currentPage: null,                                                                                          
    //reload_t: null, 

    //page: "upload", //currently opened page (see App.vue for list of pages)
}

function loadDatatype(modality: string, datatype: BIDSSchemaEntities[], label: string) {
    state.bidsSchema.datatypes[modality] = { label, options: [] };
    datatype.forEach(group=>{
        group.suffixes.forEach((suffix:string)=>{
            state.bidsSchema.datatypes[modality].options.push({
                value: modality+"/"+suffix, 
                label: suffix,
                entities: group.entities,   //["subject", "session", etc..]
            });
        });
    });
}

import dwiDatatype from '../assets/schema/datatypes/dwi.json'
loadDatatype("dwi", dwiDatatype, "Diffusion");

import anatDatatype from '../assets/schema/datatypes/anat.json'
loadDatatype("anat", anatDatatype, "Anatomical");

import funcDatatype from '../assets/schema/datatypes/func.json'
loadDatatype("func", funcDatatype, "Functional");

import fmapDatatype from '../assets/schema/datatypes/fmap.json'
import { DEFAULT_ECDH_CURVE } from 'tls';
import { TRAP_FOCUS_HANDLER } from 'element-plus/lib/directives/trap-focus';
loadDatatype("fmap", fmapDatatype, "Field Map");

const store = createStore({
    state,

    mutations: {
        /*
        setPage(state, page: string) {
            state.page = page;
        },
        */

        setSession(state, session) {
            console.log("setting session", session);
            state.session = session;
	        if(session._id) window.location.hash = session._id;                                                                     
        },

        reset(state) {
            console.log("resetting");
            state.session = null;
            state.ezbids = {
                notLoaded: true,
                 
                datasetDescription: {
                    Name: "Untitled",                                                                                     
                    BIDSVersion: "1.4.0",                                                                                 
                    DatasetType: "raw",                                                                                   
                    License: "",                                                                                       
                    Authors: [],                                                                                                      
                    Acknowledgements: "", 
                    HowToAcknowledge: "", 
                    Funding: [],                                                                                                      
                    EthicsApprovals: [],                                                                                                      
                    ReferencesAndLinks: [],                                                                                                      
                    DatasetDOI: "",  
                },
                readme: "edit me",                                                                                          
                participantsColumn: {}, 
        
                //here lives various things
                subjects: [],                                                                                               
                series: [],                                                                                                 
                objects: [],                                                                                                
        
                _organized: {}, //above things are organized into subs/ses/run/object hierarchy for quick access
                defacingMethod: "",
                
            };
        },

        updateEzbids(state, ezbids) {
            //console.log("setting ezbids", ezbids);
            Object.assign(state.ezbids, ezbids);

            state.ezbids.series.forEach((s:Series)=>{
                s.validationErrors = [];

		/*
                //for legacy reason.                                                                                
                delete s.entities.sub;                                                                         
                delete s.entities.ses;                                                                         
	        */
                                                                                                                    
                delete s.entities.subject;                                                                     
                delete s.entities.session;                                                                     
                                                                                                                    
                //we shouldn't have to do this soon                                                                 
                //if(s.png_objects_indices) s['object_indices'] = s.png_objects_indices;
            });

            state.ezbids.subjects.forEach((s:Subject)=>{
                s.validationErrors = [];
                s.exclude = !!(s.exclude);
                /*
                //migrate from old structure (just stick the whole thing in for now)                                
                if(conf.sessions) {                                                                                 
                    Vue.set(subject, 'sessions', conf.sessions);                                                    
                }                                                                                                   
                */           
                /*
                s.sessions.forEach(session=>{                                                                 
                    s.exclude = !!(session.exclude);                                           
                });
                */   
            });
            state.ezbids.objects.forEach((o:IObject)=>{
                o.exclude == !!(o.exclude);
                o.validationErrors = [];

                o.items.forEach(item=>{                                                                        
                    if(item.sidecar) {                                                                                                                                                                            
                        //anonymize..                                                                               
                        let sidecar = Object.assign({}, item.sidecar);                                              
                        delete sidecar.PatientName;                                                                 
                        delete sidecar.PatientID;                                                                                                                                                     
                        item['sidecar_json'] = JSON.stringify(sidecar, null, 4);                            
                    }                                                                                               
                });                                                                                                 
                                                                                     
                /*
                if(o.series_id !== undefined) {                                                                
                    o.series_idx = o.series_id;                                                           
                    delete o.series_id;                                                                        
                }    
                delete object.SeriesNumber; //should be removed from analyzer soon   
                */
            });
        },

        setEzbidsReadme(state, v) {
            state.ezbids.readme = v;
        },

        updateDDName(state, v) {
            state.ezbids.datasetDescription.Name = v;
        },

        organizeObjects(state) {   
            console.log("organizing objects");
            //mapObjects() must be called before calling this action (for _entities)
            
            //sort object by subject/session                                                                               
            state.ezbids.objects.sort((a,b)=>{                                                                                     
                const asub = a._entities.subject;                                                                            
                const bsub = b._entities.subject;                                                                            
                const ases = a._entities.session||"";                                                                        
                const bses = b._entities.session||"";                                                                        
                const adate = a.AcquisitionDate;                                                                             
                const bdate = b.AcquisitionDate;                                                                             
                                                                                                                            
                //sort by sub / ses / acq date                                                                             
                if(asub == bsub) {                                                                                         
                    if(ases == bses)     
                        return adate < bdate;                                                                              
                    else                                                                                                   
                        return ases.localeCompare(bses);                                                                   
                } else                                                                                                     
                    return asub.localeCompare(bsub);                                                                       
            });                                                                                                            
                    
            //re-index and organize 
            state.ezbids._organized = {};      
            state.ezbids.objects.forEach((o, idx)=>{                                                                               
                o.idx = idx; //reindex                                                                                     
                                                                                                                            
                let sub = /*"sub-"+*/o._entities.subject;                                                                             
                let ses = o._entities.session;//?("ses-"+o._entities.session):"";                                                                         
                if(!state.ezbids._organized[sub]) state.ezbids._organized[sub] = {                                                                     
                    sess: {},                                                                                              
                    objects: []                                                                                            
                };                                                                                                         
                //this.subs[sub].objects.push(o);                                                                          
                                                                                                                            
                if(!state.ezbids._organized[sub].sess[ses]) state.ezbids._organized[sub].sess[ses] = {                                                 
                    AcquisitionDate: o.AcquisitionDate,                                                                    
                    objects: []                                                                                            
                };                                                                                                         
                state.ezbids._organized[sub].sess[ses].objects.push(o);
            });                                                                                                            
        },
    },
    
    actions: {
        /*
        resetSession({commit}) {
            commit('setSession', null)
        }
        */
        async reload(context, id) {
            context.commit("reset");
            context.commit("setSession", {
                _id: id,
            });  
            await context.dispatch("loadSession");
            await context.dispatch("loadEzbids"); //might not yet exist
        },

        async loadSession(context) {
            if(!context.state.session) return;
            const res = await fetch(context.state.config.apihost+'/session/'+context.state.session._id, {     
                method: "GET",    
                headers: { 'Content-Type': 'application/json' },    
            });    
            context.commit("setSession", await res.json());  
        },

        async loadEzbids(context) {
            if(!context.state.session || !context.state.session.pre_finish_date) return;

            console.log("loading ezbids json");
            const res = await fetch(context.state.config.apihost+'/download/'+context.state.session._id+'/ezBIDS.json')
            if(res.status == 200) {
                const conf = await res.json();
                conf.notLoaded = false;
                context.commit("updateEzbids", conf);
                //context.dispatch("mapObjects");
            } else {
                console.log("no ezbids.json yet");
            }
        },
        /*
        mapObjects(context) {
            context.state.ezbids.objects.forEach((o:IObject)=>{
                this.commit("mapObject", o);
            });
        },
        */

        loadDefaceStatus(context) {
            if(!context.state.session) return;

            fetch(context.state.config.apihost+'/download/'+context.state.session._id+'/deface.finished').then(res=>res.text()).then(data=>{
                if(!data) return;
                let idxs = data.trim().split("\n").map(v=>parseInt(v));
                idxs.forEach(idx=>{
                    let o = context.state.ezbids.objects.find(o=>o.idx == idx);
                    if(!o) console.error("can't find", idx);
                    else o.defaced = true;
                });
            }).catch(console.error);

            fetch(context.state.config.apihost+'/download/'+context.state.session._id+'/deface.failed').then(res=>res.text()).then(data=>{
                if(!data) return;
                let idxs = data.trim().split("\n").map(v=>parseInt(v));
                idxs.forEach(idx=>{
                    let o = context.state.ezbids.objects.find(o=>o.idx === idx);
                    if(!o) console.error("can't find", idx);
                    else o.defaceFailed = true;
                });
            }).catch(console.error);   
        }
    },

    getters: {
        //from "anat/t1w", return entities object {subject: required, session: optional, etc..}
        getBIDSEntities: (state)=>(type: string) =>{
            if(!type) return {};                                                                                        
            const modality = type.split("/")[0];                                                                        
            const suffix = type.split("/")[1];                                                                          
            let datatype = state.bidsSchema.datatypes[modality];                                                               
            if(!datatype) return {};                                                                                    
            
            //find the option that contains our suffix      
            const option = datatype.options.find(option=>option.value == type);
            return option?.entities;
        },
        
        //find a session inside sub hierarchy
        findSession: (state)=>(sub: Subject, acquisitionDate: string) : (Session|undefined)=>{                                                                                              
            return sub.sessions.find(s=>s.AcquisitionDate == acquisitionDate);                                                                                                                                 
        },   
        
        findSubject: (state)=>(o: IObject): (Subject|undefined) =>{           
            //does this still happen?
            if(!o.PatientName && o.PatientID && o.PatientBirthDate) {
                console.error("none of the patient identifying fields are set.. can't find this object");      
                console.dir(o);  
                return undefined;
            }                    

            return state.ezbids.subjects.find(s=>{     
                //see if any of the PatientInfo matches this object's
                let match = s.PatientInfo.find(info=>{
                    if(o.PatientName && info.PatientName != o.PatientName) return false;
                    if(o.PatientID && info.PatientID != o.PatientID) return false;
                    if(o.PatientBirthDate && info.PatientBirthDate != o.PatientBirthDate) return false;
                    return true;
                });     
                return !!match;                                                                                           
            });                                                                                                                                                                                       
        },  

        getURL: (state)=>(path: string)=>{
            if(!state.session) return null;
            return state.config.apihost+"/download/"+state.session._id+"/"+path;
        },

        getAnatObjects(state) {
            return state.ezbids.objects.filter(o=>o._type.startsWith('anat') && !o._exclude)
        },
    },
})

export default store;
