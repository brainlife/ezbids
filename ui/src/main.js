import Vue from 'vue'

var numeral = require("numeral");
Vue.filter("formatNumber", value=>{
    return numeral(value).format("0,0"); // displaying other groupings/separators is possible, look at the docs
});

import ElementUI from 'element-ui';
import 'element-ui/lib/theme-chalk/index.css';
import locale from 'element-ui/lib/locale/lang/en'
Vue.use(ElementUI, { locale } );

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

            //TODO - deprecated - use bids_datatypes (datatype selector should be componentized)
            datatypes: [], //datatype catalog from bids-specification (suffixes only)

            bids_datatypes: {},  //keyed by modality (dwi, anat, then the content of the yaml)
            bids_entities: null,  //keybed by entities, and info for each entities

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

            analyzed: false,
            validated: false,
            finalized: false,
            finished: false,

        }
    },

    watch: {
        page(v) {
            if(v == "objects") {
                console.log("apply object mappings");
                this.objects.forEach(object=>{

                    //apply subject mapping
                    let subject = this.subjects.find(s=>s.PatientID == object.PatientID);
                    if(!subject) {
                        console.log("unknown PatientID in object", object.PatientID);
                    } else {
                        object.entities.sub = subject.sub; 
                    }
                    
                    //apply session mapping
                    let session = this.sessions.find(s=>s.AcquisitionDate == object.AcquisitionDate);
                    if(!session) {
                        console.log("unknown AcquisitionDate in object", object.AcquisitionDate);
                    } else {
                        object.entities.ses = session.ses; 
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

                        /*
                        //initialize entities (otherwise UI will glitch)
                        const modality = object.type.split("/")[0];
                        const suffix = object.type.split("/")[1];
                        this.$root.bids_datatypes[modality].forEach(b=>{
                            if(b.suffixes.includes(suffix)) {
                                console.log("setting entities");
                                console.dir(b.entities);
                                for(let key in b.entities) Vue.set(object.entities, key, "");
                            }
                        });
                        */

                        //apply entities
                        Object.assign(object.entities, series.entities);
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
        this.bids_datatypes["dwi"] = _dwi;

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
        this.bids_datatypes["anat"] = _anat;

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
        this.bids_datatypes["func"] = _func;

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
        this.bids_datatypes["fmap"] = _fmap;

        let fmap = {label: "Field Map", options: []}
        _fmap.forEach(group=>{
            group.suffixes.forEach(suffix=>{
                fmap.options.push({value: "fmap/"+suffix, label: suffix});
            });
        });
        this.datatypes.push(fmap);

        this.bids_entities = jsyaml.load(`
sub:
  name: Subject
  description: "A person or animal participating in the study."
  format: label
ses:
  name: Session
  description: |
    A logical grouping of neuroimaging and behavioral data consistent across subjects.
    Session can (but doesn't have to) be synonymous to a visit in a longitudinal study.
    In general, subjects will stay in the scanner during one session.
    However, for example, if a subject has to leave the scanner room and then be
    re-positioned on the scanner bed, the set of MRI acquisitions will still be considered
    as a session and match sessions acquired in other subjects.
    Similarly, in situations where different data types are obtained over several visits
    (for example fMRI on one day followed by DWI the day after) those can be grouped in one
    session.
    Defining multiple sessions is appropriate when several identical or similar data
    acquisitions are planned and performed on all -or most- subjects, often in the case of
    some intervention between sessions (e.g., training).
  format: label
task:
  name: Task
  format: label
  description: "Each task has a unique label that MUST only consist of letters
                and/or numbers (other characters, including spaces and
                underscores, are not allowed).
                Those labels MUST be consistent across subjects and sessions."
acq:
  name: Acquisition
  description: "The OPTIONAL acq-<label> key/value pair corresponds to a custom
                label the user MAY use to distinguish a different set of
                parameters used for acquiring the same modality.
                For example this should be used when a study includes two T1w
                images - one full brain low resolution and and one restricted
                field of view but high resolution. In such case two files could
                have the following names: sub-01_acq-highres_T1w.nii.gz and
                sub-01_acq-lowres_T1w.nii.gz, however the user is free to choose
                any other label than highres and lowres as long as they are
                consistent across subjects and sessions. In case different
                sequences are used to record the same modality (e.g. RARE and
                FLASH for T1w) this field can also be used to make that distinction.
                At what level of detail to make the distinction (e.g. just between
                RARE and FLASH, or between RARE, FLASH, and FLASHsubsampled)
                remains at the discretion of the researcher."
  format: label
ce:
  name: Contrast Enhancing Agent
  description: "Similarly the OPTIONAL ce-<label> key/value can be used to
                distinguish sequences using different contrast enhanced images.
                The label is the name of the contrast agent.
                The key ContrastBolusIngredient MAY be also be added in the JSON
                file, with the same label."
  format: label
rec:
  name: Reconstruction
  description: "Similarly the OPTIONAL rec-<label> key/value can be used to
                distinguish different reconstruction algorithms (for example
                ones using motion correction)."
  format: label
dir:
  name: Phase-Encoding Direction
  description: "Similarly the OPTIONAL dir-<label> key/value can be used to
                distinguish different phase-encoding directions."
  format: label
run:
  name: Run
  description: "If several scans of the same modality are acquired they MUST be
                indexed with a key-value pair: _run-1, _run-2, _run-3 etc.
                (only integers are allowed as run labels).
                When there is only one scan of a given type the run key MAY be
                omitted.
                Please note that diffusion imaging data is stored elsewhere
                (see below)."
  format: index
mod:
  name: Corresponding Modality
  description: "In such cases the OPTIONAL mod-<label> key/value pair corresponds
                to modality label for eg: T1w, inplaneT1, referenced by a
                defacemask image. E.g., sub-01_mod-T1w_defacemask.nii.gz."
  format: label
echo:
  name: Echo
  description: "Multi-echo data MUST be split into one file per echo.
                Each file shares the same name with the exception of the
                _echo-<index> key/value."
  format: index
recording:
  name: Recording
  description: "More than one continuous recording file can be included (with
                different sampling frequencies).
                In such case use different labels.
                For example: _recording-contrast, _recording-saturation."
  format: label
proc:
  name: Processed (on device)
  description: "The proc label is analogous to rec for MR and denotes a variant
                of a file that was a result of particular processing performed
                on the device.
                This is useful for files produced in particular by Elekta’s
                MaxFilter (e.g. sss, tsss, trans, quat, mc, etc.), which some
                installations impose to be run on raw data because of active
                shielding software corrections before the MEG data can actually
                be exploited."
  format: label
space:
  name: Space
  description: "The optional space label (*[_space-<label>]_electrodes.tsv) can
                be used to indicate the way in which electrode positions are interpreted.
                The space label needs to be taken from the list in Appendix VIII"
  format: label
split:
  name: Split
  description: "In the case of long data recordings that exceed a file size of
                2Gb, the .fif files are conventionally split into multiple parts.
                Each of these files has an internal pointer to the next file.
                This is important when renaming these split recordings to the BIDS
                convention.
                Instead of a simple renaming, files should be read in and saved
                under their new names with dedicated tools like MNE, which will
                ensure that not only the file names, but also the internal file
                pointers will be updated.
                It is RECOMMENDED that .fif files with multiple parts use the
                split-<index> entity to indicate each part."
  format: index
`);

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
                if(!o.entities.task) o.validationErrors.push("Task Name is required for func/bold");
            }

            //try parsing items
            o.items.forEach(item=>{
                if(item.sidecar) {
                    try {
                        item.sidecar = JSON.parse(item.sidecar_json);
                    } catch (err) {
                        o.validationErrors.push(err);
                    }
                }
            });
        },

        organizeObjects() {
            console.log("reorging");
            this.subs = {}; 

            this.$root.objects.forEach(o=>{
                let sub = o.entities.sub||"";
                let ses = o.entities.ses||"";
                let run = o.entities.run||"";

                if(!this.subs[sub]) this.subs[sub] = { sess: {}, objects: []}; 
                this.subs[sub].objects.push(o);

                if(!this.subs[sub].sess[ses]) this.subs[sub].sess[ses] = { runs: {}, objects: [] };
                this.subs[sub].sess[ses].objects.push(o);

                if(!this.subs[sub].sess[ses].runs[run]) this.subs[sub].sess[ses].runs[run] = { objects: [] };
                this.subs[sub].sess[ses].runs[run].objects.push(o);
            });

            this.$root.objects.sort((a,b)=>{
                if(a.entities.sub > b.entities.sub) return 1;
                if(a.entities.sub < b.entities.sub) return -1;
                if(a.entities.ses > b.entities.ses) return 1;
                if(a.entities.ses < b.entities.ses) return -1;
                if(a.entities.run > b.entities.run) return 1;
                if(a.entities.run < b.entities.run) return -1;
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

                //debug migration
                /*
                this.objects.forEach(object=>{
                    object.entities = object.labels||{};
                    delete object.labels;
                    if(object.hierarchy) {
                        if(object.hierarchy.subject) object.entities.sub = object.hierarchy.subject;
                        if(object.hierarchy.session) object.entities.ses = object.hierarchy.session;
                        if(object.hierarchy.run) object.entities.run = object.hierarchy.run;
                        delete object.hierarchy;
                    }
                });
                this.series.forEach(series=>{
                    series.entities = series.labels||{};
                    delete series.labels;
                    if(s.hierarchy) {
                        if(s.hierarchy.subject) s.entities.sub = s.hierarchy.subject;
                        if(s.hierarchy.session) s.entities.ses = s.hierarchy.session;
                        if(s.hierarchy.run) s.entities.run = s.hierarchy.run;
                        delete s.hierarchy;
                    }
                });
                */

                this.subjects.forEach(subject=>{
                    Vue.set(subject, 'phenotype', {});
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
        }
    },
})



