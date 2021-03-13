import Vue from 'vue'

var numeral = require("numeral");
Vue.filter("formatNumber", value=>{
    return numeral(value).format("0,0"); // displaying other groupings/separators is possible, look at the docs
});

//https://gist.github.com/james2doyle/4aba55c22f084800c199
Vue.filter('prettyBytes', function (num) {
  // jacked from: https://github.com/sindresorhus/pretty-bytes
  if (typeof num !== 'number' || isNaN(num)) {
    throw new TypeError('Expected a number');
  }

  var exponent;
  var unit;
  var neg = num < 0;
  var units = ['B', 'kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

  if (neg) {
    num = -num;
  }

  if (num < 1) {
    return (neg ? '-' : '') + num + ' B';
  }

  exponent = Math.min(Math.floor(Math.log(num) / Math.log(1000)), units.length - 1);
  num = (num / Math.pow(1000, exponent)).toFixed(2) * 1;
  unit = units[exponent];

  return (neg ? '-' : '') + num + ' ' + unit;
});

import ElementUI from 'element-ui';
import 'element-ui/lib/theme-chalk/index.css';
import locale from 'element-ui/lib/locale/lang/en'
Vue.use(ElementUI, { locale } );

//import Vuex from 'vuex'
//Vue.use(Vuex)

if(process.env.NODE_ENV == "development") {
    Vue.config.debug = true;
}

Vue.config.productionTip = false

import App from './App.vue'

import bidsEntities from './assets/schema/entities.yaml'

import anatDatatype from './assets/schema/datatypes/anat.yaml'
import dwiDatatype from './assets/schema/datatypes/dwi.yaml'
import funcDatatype from './assets/schema/datatypes/func.yaml'
import fmapDatatype from './assets/schema/datatypes/fmap.yaml'

/*
import jsyaml from 'js-yaml';
async function loadYaml(url) {
    let yaml = await fetch(url).then(res=>res.text());
    return jsyaml.load(yaml);
}
*/

new Vue({
    el: '#app',
    components: {
        App,
    },
    render(createElement) {
        return createElement('App');
    },
    
    //router,
    data() {

        //
        //$root scope............................................
        //
        return {
            config: Vue.config,

            apihost: (process.env.NODE_ENV == "development") ? "https://dev1.soichi.us/api/easybids" : "/api/ezbids",

            //data from dan's script
            //site: "", 
            datasetDescription: {
                "Name": "Untitled",
                "BIDSVersion": "1.4.0",
                "DatasetType": "raw",
                "License": "CC0",
                "Authors": [
                    "Soichi Hayashi",
                    "Dan Levitas"
                ],
                "Acknowledgements": "", //"Special thanks to Korbinian Brodmann for help in formatting this dataset in BIDS. We thank Alan Lloyd Hodgkin and Andrew Huxley for helpful comments and discussions about the experiment and manuscript; Hermann Ludwig Helmholtz for administrative support; and Claudius Galenus for providing data for the medial-to-lateral index analysis.",
                "HowToAcknowledge": "", //"Please cite this paper: https://www.ncbi.nlm.nih.gov/pubmed/001012092119281",
                "Funding": [
                    //"National Institute of Neuroscience Grant F378236MFH1",
                    //"National Institute of Neuroscience Grant 5RMZ0023106"
                ],
                "EthicsApprovals": [
                    //"Army Human Research Protections Office (Protocol ARL-20098-10051, ARL 12-040, and ARL 12-041)"
                ],
                "ReferencesAndLinks": [
                    //"https://www.ncbi.nlm.nih.gov/pubmed/001012092119281",
                    //"http://doi.org/1920.8/jndata.2015.7"
                ],
                "DatasetDOI": "", //"10.0.2.3/dfjj.10"
            },
            readme: "edit me", 
            participantsColumn: {},

            //deface: true,
            
            subjects: [],
            series: [],
            objects: [],

            subs: {}, //objects organized into subs/ses/run/object for objects page

            currentPage: null,

            reload_t: null,

            pages: [
                {id: "upload", title: "Upload DICOM"},
                {id: "description", title: "BIDS Description"},
                {id: "subject", title: "Subjects/Sessions"},
                {id: "participant", title: "Participants Info"},
                {id: "series", title: "Series Mapping"},
                {id: "object", title: "Overrides"},
                {id: "deface", title: "Deface"},
                {id: "finalize", title: "Finalize"},
            ],

            //TODO - deprecated - use bids_datatypes (datatype selector should be componentized)
            datatypes: [], //datatype catalog from bids-specification (suffixes only)

            bids_datatypes: {},  //keyed by modality (dwi, anat, then the content of the yaml)
            bids_entities: {},  //keybed by entities, and info for each entities

            uploadFailed: false,

            session: null, //created when upload begins

            defacingMethod: "",

            analyzed: false,
            finalized: false,
        }
    },

    async mounted() {
        if(location.hash) {
            this.session = {
                _id: location.hash.substring(1),
            }
            this.pollSession();
        }

        //let _dwi = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/datatypes/dwi.yaml");
        this.bids_datatypes["dwi"] = dwiDatatype;
        let dwi = {label: "Diffusion", options: []}
        dwiDatatype.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                dwi.options.push({value: "dwi/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(dwi);
        
        //let _anat = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/datatypes/anat.yaml");
        this.bids_datatypes["anat"] = anatDatatype;
        let anat = {label: "Anatomical", options: []}
        anatDatatype.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                anat.options.push({value: "anat/"+suffix, label: suffix});
            });
        });

        this.datatypes.push(anat);

        //let _func = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/datatypes/func.yaml");
        this.bids_datatypes["func"] = funcDatatype;

        let func = {label: "Functional", options: []}
        funcDatatype.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                func.options.push({value: "func/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(func);

        //let _fmap = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/datatypes/fmap.yaml");
        this.bids_datatypes["fmap"] = fmapDatatype;

        let fmap = {label: "Field Map", options: []}
        fmapDatatype.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                fmap.options.push({value: "fmap/"+suffix, label: suffix});
            });
        })
        this.datatypes.push(fmap);

        //let _bids_entities = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/entities.yaml");
        for(let key in bidsEntities) {
            let ent = bidsEntities[key];
            //this.bids_entities[ent.entity] = ent;
            this.bids_entities[key] = ent;
        }

        /*
        //Inject MP2RAGE under anat
        let _anatSupplement = jsyaml.load(`---
- suffixes:
    - MP2RAGE
  extensions:
    - .nii.gz
    - .json
  entities:
    sub: required
    ses: optional
    run: optional
    acq: optional
    inv: optional
`);
        _anatSupplement.forEach(group=>{
            this.bids_datatypes["anat"].push(group);
            group.suffixes.forEach(suffix=>{
                anat.options.push({value: "anat/"+suffix, label: suffix});
            });
        });
        */

        /*
        this.bids_entities.inv = jsyaml.load(`---
invert:
  name: invert
  entities: inv
  description: |
    Please enter some description here.
    You can use multiple lines like this.
  format: label
`).invert;
        */

        this.currentPage = this.pages[0];
        this.pages.forEach((p, idx)=>{
            p.idx = idx;
        });
    },

    computed: { },

    methods: {
        reset() {
            location.hash = "";
            location.reload();
        },

        getURL(path) {
            return this.apihost+"/download/"+this.session._id+'/'+path;
        },
  
        //TODO - I should rename this to getDatatypeEntities()
        //same code in series / methods
        getEntities(type) {
            if(!type) return {};
            const modality = type.split("/")[0];
            const suffix = type.split("/")[1];
            let datatype = this.bids_datatypes[modality];
            if(!datatype) return {};

            let entities = {};
            datatype.forEach(b=>{
                if(b.suffixes.includes(suffix)) Object.assign(entities, b.entities);
            });
            return entities;
        },

        findSubject(o) {
            let subject = this.subjects.find(s=>{
                if(o.PatientName) {
                    if(s.PatientName == o.PatientName) return true;
                    return false;
                }
                if(o.PatientID) {
                    if(s.PatientID == o.PatientID) return true;
                    return false;
                }
                if(o.PatientBirthDate) {
                    if(s.PatientBirthDate == o.PatientBirthDate) return true;
                    return false;
                }
                return false;
            });
            return subject;
        },

        findSession(sub, o) {
            let session = sub.sessions.find(s=>s.AcquisitionDate == o.AcquisitionDate);
            return session;
        },

        findSeries(o) {
            let series = this.series.find(s=>s.series_id == o.series_id);
            return series;
        },

        //apply all parent entity mappings and store them under _entities
        mapObject(o) {
            o._exclude = o.exclude;

            const series = this.$root.findSeries(o);
            o._SeriesDescription = series.SeriesDescription;
            o._type = series.type;
            if(o.type) o._type = o.type; //object level override
            
            //initialize with the proper object key ordering
            const e = this.getEntities(o._type);
            for(let k in e) {
                e[k] = series.entities[k];
            }

            //apply overrides from the object
            for(let k in o.entities) {
                if(o.entities[k]) e[k] = o.entities[k];
            }

            const subject = this.$root.findSubject(o);
            if(subject.exclude) o._exclude = true;
            //
            //if sub is not set, use subject mapping as default
            if(!o.entities.subject) {
                e.subject = subject.subject;
            } 

            const session = this.$root.findSession(subject, o);
            if(session.exclude) o._exclude = true;
            
            //if ses is not set, use session mapping as default
            if(!o.entities.session) {
                e.session = session.session;
            }

            o._entities = e;
        },

        organizeObjects() {
            this.subs = {}; 

            this.objects.forEach((o, idx)=>{
                o.idx = idx; //reindex

                let sub = o._entities.subject;
                let ses = o._entities.session||"";
                if(!this.subs[sub]) this.subs[sub] = {
                    sess: {}, 
                    objects: []
                }; 
                this.subs[sub].objects.push(o);

                if(!this.subs[sub].sess[ses]) this.subs[sub].sess[ses] = { 
                    AcquisitionDate: o.AcquisitionDate, 
                    objects: [] 
                };
                this.subs[sub].sess[ses].objects.push(o);
            });
        },

        loadData(url) {
            return fetch(url).then(res=>res.json()).then(conf=>{   
                this.subjects = conf.subjects;
                this.series = conf.series;
                this.objects = conf.objects;
                this.participantsColumn = conf.participantsColumn||{};

                this.series.forEach(series=>{

                    //for legacy reason.
                    delete series.entities.sub;
                    delete series.entities.ses;

                    delete series.entities.subject;
                    delete series.entities.session;

                    //we shouldn't have to do this soon
                    if(series.png_objects_indices) Vue.set(series, 'object_indices', series.png_objects_indices);
                });

                this.subjects.forEach(subject=>{
                    Vue.set(subject, 'exclude', !!(subject.exclude));

                    //migrate from old structure (just stick the whole thing in for now)
                    if(conf.sessions) {
                        //this.sessions.push({AcquisitionDate: "2020-01-22", ses: "test"});
                        Vue.set(subject, 'sessions', conf.sessions);
                    }
                    
                    //migrate from old entity name to new
                    /*
                    if(subject.sub !== undefined) {
                        console.log("ezBIDS.json using 'sub'.. renmaing to subject");
                        Vue.set(subject, 'subject', subject.sub);
                        delete subject.sub;
                    }
                    */

                    subject.sessions.forEach(session=>{
                        Vue.set(session, 'exclude', !!(session.exclude));

                        //migrate from old entity name to new
                        /*
                        if(session.ses !== undefined) {
                            console.log("ezBIDS.json using 'ses'.. renmaing to session");
                            Vue.set(session, 'session', session.ses);
                            delete session.ses;
                        }
                        */
                    });
                });

                this.objects.forEach(object=>{
                    Vue.set(object, 'exclude', !!(object.exclude));

                    object.items.forEach(item=>{
                        if(item.sidecar) {

                            //anonymize..
                            let sidecar = Object.assign({}, item.sidecar);
                            delete sidecar.PatientName;
                            delete sidecar.PatientID;

                            Vue.set(item, 'sidecar_json', JSON.stringify(sidecar, null, 4));
                        }
                    });
                });

                this.series.sort((a,b)=>a.SeriesNumber - b.SeriesNumber);
            }).catch(err=>{
                console.error("failed to load", url);
                console.error(err);
            });
        },

        async pollSession() {
            const res = await fetch(this.apihost+'/session/'+this.session._id, {
                method: "GET",
                headers: { 'Content-Type': 'application/json' },
            });
            this.session = Object.assign({}, await res.json());
            switch(this.session.status) {
            case "created":
            case "uploaded":
            case "preprocessing":
            case "deface":
            case "defacing":
            case "finalized":
            case "bidsing":
                this.reload_t = setTimeout(()=>{
                    this.pollSession();
                }, 1000*5);
                break;

            case "finished":
            case "defaced":
            case "analyzed":
                if(!this.analyzed) {
                    await this.loadData(this.apihost+'/download/'+this.session._id+'/ezBIDS.json');
                    this.analyzed = true;
                }
                break;

            case "failed":
                break;
            }
        },

        changePage(id) {
            window.scrollTo(0, 0);
            this.currentPage = this.pages.find(p=>p.id == id);
        },

        //TODO - should I move to finalize.vue?
        finalize(cb) {
            //mapping between things like like "subject" to "sub"
            const entityMappings = {};
            for(const key in this.bids_entities) {
                entityMappings[key] = this.bids_entities[key].entity;
            }

            fetch(this.apihost+'/session/'+this.session._id+'/finalize', {
                method: "POST", 
                headers: {'Content-Type': 'application/json; charset=UTF-8'},
                body: JSON.stringify({
                    datasetDescription: this.datasetDescription,
                    readme: this.readme,
                    participantsColumn: this.participantsColumn,
                    subjects: this.subjects, //for phenotype
                    objects: this.objects,
                    //deface: this.deface, //deface anatomical
                    entityMappings,
                }),
            }).then(res=>res.text()).then(status=>{
                if(status == "ok") {
                    this.finalized = true;
                    this.pollSession();
                    if(cb) cb();
                } else {
                    if(cb) cb(status);
                }
            }); 
        },

    },
})



