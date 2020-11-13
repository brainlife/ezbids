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

import jsyaml from 'js-yaml';

//import Vuex from 'vuex'
//Vue.use(Vuex)

if(process.env.NODE_ENV == "development") {
    Vue.config.debug = true;
}

Vue.config.productionTip = false

import App from './App.vue'

async function loadYaml(url) {
    let json = await fetch(url).then(res=>res.text());
    return jsyaml.load(json);
}

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
            
            subjects: [],
            sessions: [],
            series: [],

            objects: [],
            subs: {}, //objects organized into subs/ses/run for objects page

            //page: "upload",
            currentPage: null,

            reload_t: null,

            pages: [
                {id: "upload", title: "Upload DICOM"},
                {id: "description", title: "BIDS Description"},
                {id: "subject", title: "Subject Mapping"},
                {id: "session", title: "Session Mapping"},
                {id: "series", title: "Series Mapping"},
                {id: "participant", title: "Participants Info"},
                {id: "object", title: "Finalize"},
                {id: "finalize", title: "Download BIDS"},
            ],

            //TODO - deprecated - use bids_datatypes (datatype selector should be componentized)
            datatypes: [], //datatype catalog from bids-specification (suffixes only)

            bids_datatypes: {},  //keyed by modality (dwi, anat, then the content of the yaml)
            bids_entities: {},  //keybed by entities, and info for each entities

            uploadFailed: false,

            session: null, //created when upload begins
            //session.status... 
            //      created
            //      uploaded
            //      preprocessing
            //      analyzed
            //      failed
            //      finalized
            //      bidsing
            //      finished

            /*
            descErrors: 0,
            subjectErrors: 0,
            sessionErrors: 0,
            seriesErrors: 0,
            participantErrors: 0,
            objectErrors: 0,
            */

            analyzed: false,
            finalized: false,
            //finalized: false,
            //finished: false,
        }
    },

    async mounted() {
        if(location.hash) {
            this.session = {
                _id: location.hash.substring(1),
            }
            this.pollSession();
        }

        let _dwi = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/datatypes/dwi.yaml");
        this.bids_datatypes["dwi"] = _dwi;

        let dwi = {label: "Diffusion", options: []}
        _dwi.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                dwi.options.push({value: "dwi/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(dwi);
        
        let _anat = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/datatypes/anat.yaml");
        this.bids_datatypes["anat"] = _anat;

        let anat = {label: "Anatomical", options: []}
        _anat.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                anat.options.push({value: "anat/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(anat);

        let _func = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/datatypes/func.yaml");
        this.bids_datatypes["func"] = _func;

        let func = {label: "Functional", options: []}
        _func.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                func.options.push({value: "func/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(func);

        let _fmap = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/datatypes/fmap.yaml");
        this.bids_datatypes["fmap"] = _fmap;

        let fmap = {label: "Field Map", options: []}
        _fmap.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                fmap.options.push({value: "fmap/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(fmap);

        let _bids_entities = await loadYaml("https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/entities.yaml");
        for(let key in _bids_entities) {
            let ent = _bids_entities[key];
            this.bids_entities[ent.entity] = ent;
        }

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

        getType(o) {
            if(o.type) return o.type;
            const series = this.findSeries(o);
            return series.type;
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

        findSession(o) {
            let session = this.sessions.find(s=>s.AcquisitionDate == o.AcquisitionDate);
            return session;
        },

        findSeries(o) {
            let series = this.series.find(s=>s.series_id == o.series_id);
            return series;
        },

        //apply all mappings and store them under _entities
        mapObject(o) {
            const series = this.$root.findSeries(o);
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

            //if sub is not set, use subject mapping as default
            if(!o.entities.sub) {
                const subject = this.$root.findSubject(o);
                e.sub = subject.sub;
            } 

            //if ses is not set, use session mapping as default
            if(!o.entities.ses) {
                const session = this.$root.findSession(o);
                e.ses = session.ses;
            }

            o._entities = e;
        },

        organizeObjects() {
            this.subs = {}; 

            this.objects.forEach((o, idx)=>{
                o.idx = idx; //reindex

                let sub = o._entities.sub;
                let ses = o._entities.ses;

                if(!this.subs[sub]) this.subs[sub] = {sess: {}, objects: []}; 
                this.subs[sub].objects.push(o);

                if(!this.subs[sub].sess[ses]) this.subs[sub].sess[ses] = { AcquisitionDate: o.AcquisitionDate, /*runs: {},*/ objects: [] };
                this.subs[sub].sess[ses].objects.push(o);
            });
        },

        loadData(url) {

            return fetch(url).then(res=>res.json()).then(conf=>{   
                this.subjects = conf.subjects;
                this.sessions = conf.sessions;
                this.series = conf.series;
                this.objects = conf.objects;

                this.participantsColumn = conf.participantsColumn||{};

                this.series.forEach(series=>{
                    delete series.entities.sub;
                    delete series.entities.ses;

                    //we shouldn't have to do this soon
                    if(series.png_objects_indices) Vue.set(series, 'object_indices', series.png_objects_indices);
                });

                //this should be deprecated soon
                this.subjects.forEach(subject=>{
                    if(!subject.phenotype) Vue.set(subject, 'phenotype', {});
                });

                this.objects.forEach(object=>{
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
            this.session = await res.json();
            console.log(this.session.update_date, this.session.status);
            switch(this.session.status) {
            case "created":
            case "uploaded":
            case "preprocessing":
            case "finalized":
            case "bidsing":
                this.reload_t = setTimeout(()=>{
                    //console.log("will reload");
                    this.pollSession();
                }, 1000*5);
                break;

            case "finished":
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

        finalize() {
            //clearTimeout(this.reload_t);

            fetch(this.apihost+'/session/'+this.session._id+'/finalize', {
                method: "POST", 
                headers: {'Content-Type': 'application/json; charset=UTF-8'},
                body: JSON.stringify({
                    datasetDescription: this.datasetDescription,
                    readme: this.readme,
                    participantsColumn: this.participantsColumn,
                    subjects: this.subjects, //for phenotype
                    objects: this.objects,
                }),
            }).then(res=>res.text()).then(status=>{
                if(status == "ok") {
                    this.finalized = true;
                    this.pollSession();
                } else {
                    this.$notify({ title: 'Failed', message: 'Failed to finalize:'+status});
                }
            }); 
        },

    },
})



