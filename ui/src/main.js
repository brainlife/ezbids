import Vue from 'vue'

var numeral = require("numeral");
Vue.filter("formatNumber", value=>{
    return numeral(value).format("0,0"); // displaying other groupings/separators is possible, look at the docs
});

/*
import {
  Select,
  Button
} from 'element-ui'
Vue.component(Select.name, Select)
Vue.component(Button.name, Button)
*/

import ElementUI from 'element-ui';
import 'element-ui/lib/theme-chalk/index.css';
import locale from 'element-ui/lib/locale/lang/en'
Vue.use(ElementUI, { locale } );

//import testdata from '/home/hayashis/syncthing/git/ezbids/handler/analyzer/ezbids_reference.json';

import jsyaml from 'js-yaml';

import Vuex from 'vuex'
Vue.use(Vuex)

if(process.env.NODE_ENV == "development") {
    Vue.config.debug = true;
}

Vue.config.productionTip = false

import App from './App.vue'

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
                "Name": "",
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
            readme: "", 
            //participants: {},
            participantsColumn: {},
            
            subjects: [],
            sessions: [],
            series: [],

            objects: [],
            subs: {}, //objects organized into subs/ses/run for objects page

            page: "upload",

            datatypes: [], //datatype catalog from bids-specification

            uploadFailed: false,
            session: null, //created when upload begins
            //status... created / uploaded / preprocessing / analyzed / failed / finalized / bidsing / finished
            analyzed: false,
            //loaded: false, //loaded ezBIDS from analyzer
            validated: false,
            finalized: false,
            finished: false,
        }
    },

    watch: {
        page(v) {
            //apply mappings
            if(v == "objects") {
                this.objects.forEach(object=>{

                    //apply subject mapping
                    let subject = this.subjects.find(s=>s.PatientID == object.PatientID);
                    if(!subject) {
                        console.log("unknown PatientID in object", object.PatientID);
                    } else {
                        object.hierarchy.subject = subject.sub; //TODO - hierarchy.subject to sub?
                    }
                    
                    //apply session mapping
                    let session = this.sessions.find(s=>s.AcquisitionDate == object.AcquisitionDate);
                    if(!session) {
                        console.log("unknown AcquisitionDate in object", object.AcquisitionDate);
                    } else {
                        object.hierarchy.session = session.ses; //TODO - hierarchy.subject to sub?
                    }

                    //apply series info
                    let series = this.series.find(s=>s.SeriesNumber == object.SeriesNumber);
                    if(!series) {
                        console.log("unknown seriesnumber in object", object.SeriesNumber);
                    } else {
                        object.SeriesDescription = series.SeriesDescription;

                        //apply series info
                        object.type = series.type;
                        object.include = series.include;

                        //apply entities
                        Object.assign(object.labels, series.labels);
                    }

                    this.validateObject(object);
                });
                this.organizeObjects();
            }
        },
    },

    async mounted() {
        console.log("mounted main");
        /*
        if(this.$route.hash != "") { 
            let session_id = this.$route.hash.substring(1);
            //TODO reload session ID
        }
        */

        //dwi
        //https://github.com/tsalo/bids-specification/blob/ref/json-entity/src/schema/datatypes/dwi.yaml
        let _dwi = jsyaml.load(`
- suffixes:
    - dwi
  extensions:
    - .nii.gz
    - .nii
    - .json
    - .bvec
    - .bval
  entities:
    sub: required
    ses: optional
    acq: optional
    dir: optional
    run: optional
- suffixes:
    - sbref
  extensions:
    - .nii.gz
    - .nii
    - .json
  entities:
    sub: required
    ses: optional
    acq: optional
    dir: optional
    run: optional
`);
        let dwi = {label: "Diffusion", options: []}
        _dwi.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                dwi.options.push({value: "dwi/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(dwi);
        
        //anat
        //https://github.com/tsalo/bids-specification/blob/ref/json-entity/src/schema/datatypes/anat.yaml
        let _anat = jsyaml.load(`
# First group
- suffixes:
    - T1w
    - T2w
    - T1rho
    - T1map
    - T2map
    - T2star
    - FLAIR
    - FLASH
    - PD
    - PDmap
    - PDT2
    - inplaneT1
    - inplaneT2
    - angio
  extensions:
    - .nii.gz
    - .nii
    - .json
  entities:
    sub: required
    ses: optional
    run: optional
    acq: optional
    ce: optional
    rec: optional
# Second group
- suffixes:
    - defacemask
  extensions:
    - .nii.gz
    - .nii
    - .json
  entities:
    sub: required
    ses: optional
    run: optional
    acq: optional
    ce: optional
    rec: optional
    mod: optional
`);
        let anat = {label: "Anatomical", options: []}
        _anat.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                anat.options.push({value: "anat/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(anat);

        //https://github.com/tsalo/bids-specification/blob/ref/json-entity/src/schema/datatypes/func.yaml
        let _func = jsyaml.load(`
- suffixes:
    - bold
    - cbv
    - phase
    - sbref
  extensions:
    - .nii.gz
    - .nii
    - .json
  entities:
    sub: required
    ses: optional
    task: required
    acq: optional
    ce: optional
    rec: optional
    dir: optional
    run: optional
    echo: optional
- suffixes:
    - events
  extensions:
    - .tsv
    - .json
  entities:
    sub: required
    ses: optional
    task: required
    acq: optional
    ce: optional
    rec: optional
    dir: optional
    run: optional
    echo: optional
- suffixes:
    - physio
    - stim
  extensions:
    - .tsv.gz
    - .json
  entities:
    sub: required
    ses: optional
    task: required
    acq: optional
    rec: optional
    run: optional
    recording: optional
    proc: optional
`);
        let func = {label: "Functional", options: []}
        _func.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                func.options.push({value: "func/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(func);

        //https://github.com/tsalo/bids-specification/blob/ref/json-entity/src/schema/datatypes/fmap.yaml
        let _fmap = jsyaml.load(`
- suffixes:
    - phasediff
    - phase1
    - phase2
    - magnitude1
    - magnitude2
    - magnitude
    - fieldmap
  extensions:
    - .nii.gz
    - .nii
    - .json
  entities:
    sub: required
    ses: optional
    acq: optional
    run: optional
- suffixes:
    - epi
  extensions:
    - .nii.gz
    - .nii
    - .json
  entities:
    sub: required
    ses: optional
    acq: optional
    ce: optional
    dir: required
    run: optional
`);
        let fmap = {label: "Field Map", options: []}
        _fmap.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                fmap.options.push({value: "fmap/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(fmap);

        ///////////////////////////////////////////////////////////////////////////////////////////
        //
        //
        //load debug data
        //await this.loadData('ezbids_reference.json');
        //this.analyzed = true;
        //
        //
        ///////////////////////////////////////////////////////////////////////////////////////////
    },

    computed: {
        /*
        validated() {
            console.log("testing validation");
            if(this.objects.length == 0) return false; //empty!
            for(let object in this.objects) {
                if(!object.validationErrors) return false; //not validated yet?
                if(object.validationErrors.length > 0) return false;
            }
            console.log("objects are valid");
            return true; //all good
        }
        */
    },

    methods: {
        reset() {
            /*
            this.datasetDescription = {
                "Name": "The mother of all experiments",
                "BIDSVersion": "1.4.0",
                "DatasetType": "raw",
                "License": "CC0",
                "Authors": [
                    "Paul Broca",
                    "Carl Wernicke"
                ],
                "Acknowledgements": "Special thanks to Korbinian Brodmann for help in formatting this dataset in BIDS. We thank Alan Lloyd Hodgkin and Andrew Huxley for helpful comments and discussions about the experiment and manuscript; Hermann Ludwig Helmholtz for administrative support; and Claudius Galenus for providing data for the medial-to-lateral index analysis.",
                "HowToAcknowledge": "Please cite this paper: https://www.ncbi.nlm.nih.gov/pubmed/001012092119281",
                "Funding": [
                    "National Institute of Neuroscience Grant F378236MFH1",
                    "National Institute of Neuroscience Grant 5RMZ0023106"
                ],
                "EthicsApprovals": [
                    "Army Human Research Protections Office (Protocol ARL-20098-10051, ARL 12-040, and ARL 12-041)"
                ],
                "ReferencesAndLinks": [
                    "https://www.ncbi.nlm.nih.gov/pubmed/001012092119281",
                    "http://doi.org/1920.8/jndata.2015.7"
                ],
                "DatasetDOI": "10.0.2.3/dfjj.10"
            };

            this.readme = "";
            this.participantsColumn = {};
            
            this.subjects = [];
            this.sessions = [];
            this.series = [];

            this.objects = [];
            this.subs = {};

            this.page = "upload";
            this.uploadFailed = false;
            this.session = null;
            this.analyzed = false;
            this.validated = false;
            this.finalized = false;
            this.finished = false;
            */
            location.reload();
        },

        validateObject(o) {
            Vue.set(o, 'validationErrors', []);
            switch(o.type) {
            case "func/bold":
                if(!o.hierarchy.task) o.validationErrors.push("Task Name is required for func/bold");
            }

            //try parsing items
            o.items.forEach(item=>{
                try {
                    o.sidecar = JSON.parse(item.sidecar_json);
                } catch (err) {
                    o.validationErrors.push(err);
                }
            });
        },

        organizeObjects() {
            this.subs = {}; 

            this.$root.objects.forEach(o=>{
                let sub = o.hierarchy.subject||"";
                let ses = o.hierarchy.session||"";
                let run = o.hierarchy.run||"";

                if(!this.subs[sub]) this.subs[sub] = { sess: {}, objects: []}; 
                this.subs[sub].objects.push(o);

                if(!this.subs[sub].sess[ses]) this.subs[sub].sess[ses] = { runs: {}, objects: [] };
                this.subs[sub].sess[ses].objects.push(o);

                if(!this.subs[sub].sess[ses].runs[run]) this.subs[sub].sess[ses].runs[run] = { objects: [] };
                this.subs[sub].sess[ses].runs[run].objects.push(o);
            });

            this.$root.objects.sort((a,b)=>{
                if(a.hierarchy.subject > b.hierarchy.subject) return 1;
                if(a.hierarchy.subject < b.hierarchy.subject) return -1;
                if(a.hierarchy.session > b.hierarchy.session) return 1;
                if(a.hierarchy.session < b.hierarchy.session) return -1;
                if(a.hierarchy.run > b.hierarchy.run) return 1;
                if(a.hierarchy.run < b.hierarchy.run) return -1;
                return 0;
            });
        },
        loadData(url) {
            console.log("loadData", url);
            return fetch(url).then(res=>res.json()).then(conf=>{
                //this.site = conf.site;
                 
                this.subjects = conf.subjects;
                this.sessions = conf.sessions;
                this.series = conf.series;
                this.objects = conf.objects;

                this.participantsColumn = conf.participantsColumn||{};

                this.subjects.forEach(subject=>{
                    Vue.set(subject, 'phenotype', {});
                });
                this.objects.forEach(object=>{
                    object.items.forEach(item=>{
                        Vue.set(item, 'sidecar_json', JSON.stringify(item.sidecar, null, 4));
                    });
                });

                this.series.sort((a,b)=>a.id - b.id);
            }).catch(err=>{
                console.error("failed to load", url);
                console.error(err);
            });
        }
    },
})
