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

import Vuex from 'vuex'
Vue.use(Vuex)

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
            apihost: "https://dev1.soichi.us/api/easybids",

            //data from dan's script
            //site: "", 
            datasetDescription: {
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
                    "Alzheimer A., & Kraepelin, E. (2015). Neural correlates of presenile dementia in humans. Journal of Neuroscientific Data, 2, 234001. http://doi.org/1920.8/jndata.2015.7"
                ],
                "DatasetDOI": "10.0.2.3/dfjj.10"
            },
            readme: "", 
            participants: {},
            participantsColumn: {},
            
            subjects: [],
            sessions: [],
            series: [],
            objects: [],

            page: "upload",

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
    mounted() {
        console.log("mounted main");
        /*
        if(this.$route.hash != "") { 
            let session_id = this.$route.hash.substring(1);
            //TODO reload session ID
        }
        */
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
        loadData(url) {
            console.log("loadData", url);
            return fetch(url).then(res=>res.json()).then(conf=>{
                //this.site = conf.site;
                 
                this.subjects = conf.subjects;
                this.sessions = conf.sessions;
                this.series = conf.series;
                this.objects = conf.objects;

                this.participants = conf.participants;
                this.participantsColumn = conf.participantsColumn;

                //this.loaded = true;
            });
        }
    },
})
