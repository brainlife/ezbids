import Vue from 'vue'
import App from './App.vue'

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

import router from './router'
//import VueRouter from 'vue-router'
//Vue.use(VueRouter)

import Vuex from 'vuex'
Vue.use(Vuex)

Vue.config.productionTip = false

new Vue({
    el: '#app',
    render: h => h(App),
    data() {
        return {
            apihost: "https://dev1.soichi.us/api/easybids",

            //data from dan's script
            site: "", 
            datasetDescription: {},
            readme: "", 
            objects: [],
            participants: {},
            participantsColumn: {},

            session: null,
            analyzed: false,
            validated: false,
        }
    },
    mounted() {
        if(this.$route.hash != "") this.session = this.$route.hash.substring(1);
    },
    methods: {

        //test scafolding
        loadData(url) {
            return fetch(url).then(res=>res.json()).then(conf=>{
                this.site = conf.site;
                this.datasetDescription = conf.datasetDescription;
                this.readme = conf.readme;
                this.objects = conf.objects;
                this.participants = conf.participants;
                this.participantsColumn = conf.participantsColumn;

                this.analyzed = true;
            });
        }
    },
    router,
})
