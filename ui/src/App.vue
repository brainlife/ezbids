<script lang="ts">

import { defineComponent, defineAsyncComponent } from 'vue'
import { mapState, mapGetters } from 'vuex'

import Upload from './Upload.vue'
import Description from './Description.vue'
import Subject from './Subject.vue'
import Participant from './Participant.vue'
import SeriesPage from './SeriesPage.vue'
import Objects from './Objects.vue'
import Events from './Events.vue'
import Deface from './Deface.vue'
import Finalize from './Finalize.vue'

import { IObject } from './store'

import { ElNotification } from 'element-plus'

import { setSectionIDs, funcQA, fmapQA, setRun, updateErrors, setIntendedFor } from './libUnsafe'

export default defineComponent({
    components: {
       Upload,
       Description,
       Subject,
       Participant,
       SeriesPage,
       Events,
       Objects,
       Deface,
       Finalize,
    },

    data() {
        return {
            //initial page
            page: "upload", 
            
            //page order
            pages: [
                "upload", 
                "description", 
                "subject", 
                "participant", 
                "seriespage", 
                "event", 
                "object", 
                "deface", 
                "finalize",
            ], 
        }
    },
    async created() {

        this.$store.commit("reset");
        if(location.hash) {     
            await this.$store.dispatch("reload", location.hash.substring(1));
            this.mapObjects();
            this.$store.commit("organizeObjects");
            this.$store.dispatch("loadDefaceStatus");
        }

        console.log("checking session every 5 seconds");
        window.setInterval(async ()=>{
            if(this.session) {
                //console.log(this.session);
                switch(this.session.status) {
                case "analyzed":
                case "finished":
                    //console.log(new Date());
                    //console.log("no need to reload session/ezbids with state:", this.session.status);
                    break;
                case "defacing":
                    console.log("loading deface log")
                    this.$store.dispatch("loadDefaceStatus");
                    this.$store.dispatch("loadSession", this.session._id);
                    break;
                default:
                    //deface
                    //defaced
                    this.$store.dispatch("loadSession", this.session._id);
                }

                if(this.ezbids.notLoaded) {
                    console.log("loading ezbids for the first time"); //on page reload, above if(location.hash) block takes care of loading it
                    await this.$store.dispatch("loadEzbids");
                }
            }
        }, 5000)
    },

    computed: {
        ...mapState(['session', 'ezbids']),
        ...mapGetters(['getBIDSEntities', 'getURL', 'findSession', 'findSubject']),

        backLabel(): string|null {
            switch(this.page) {
            case "upload":
                /*
                    if (this.session.pre_finish_date || this.session.status == "failed") return "Re-Upload";
                    return null;
                */
               if(this.session) return "Re-Upload";
               return null;
            default:
                    return "Back";
            }
        },

        nextLabel() : string|null {
            switch(this.page) {
            case "upload":
                return (this.session && this.session.pre_finish_date?"Next":null);
            case "finalize":
                return null;
            default:
                return "Next";
            }
        },
    },

    methods: {
        next() {
            this.mapObjects();
            this.$store.commit("organizeObjects");
            
            // @ts-ignore
            this.$refs[this.page].isValid((err:string)=>{
                if(err) {
                    console.log("page invalid");
                    console.error(err);
                    ElNotification({ title: 'Failed', message: err});
                } else {
                    const idx = this.pages.indexOf(this.page);
                    this.page = this.pages[idx+1];

                    switch(this.page) {
                    case "event":
                        setSectionIDs(this.ezbids);
                        funcQA(this.ezbids); 
                        fmapQA(this.ezbids); 
                        setRun(this.ezbids); 
                        updateErrors(this.ezbids);
                        setIntendedFor(this.ezbids);
                        this.mapObjects();
                        break;
                    }
                }
            });
              
        },

        back() {
            const idx = this.pages.indexOf(this.page);
            if(idx == 0) {
                //this.$store.commit("reset");
                document.location.hash = "";
                document.location.reload();
            } else {
                this.page = this.pages[idx-1];
            }
        },
        
        updateObject(o: IObject) {
            this.mapObject(o);
            // @ts-ignore
            this.$refs.object.validateAll(); //I need to validate the entire list.. so I can detect collision
            this.$store.commit("organizeObjects"); 
        },

        mapObjects() {
            this.ezbids.objects.forEach(this.mapObject); 
        },

        //apply parent level entities from series / subject on to object.
        //but.. we want to preserve the information set on object itself, so let's stored flatten information on _entities instead of
        //directly applying them to entities.
        mapObject(o: IObject) {    

            const series = this.$store.state.ezbids.series[o.series_idx]; 
            if(series) {   
                //func/events doesn't have any series
                o._SeriesDescription = series.SeriesDescription.replace('_RR', ""); //helps in objects view
                o._type = series.type;                                                                                         
                o._forType = series.forType; 
            }
            if(o.type) o._type = o.type; //object level override                                                           
                                                                                                                           
            //clone bids entity for this _type to preserve proper key ordering                                                               
            const e = Object.assign({}, this.getBIDSEntities(o._type));    
            for(let k in e) {     
                if(series) e[k] = series.entities[k];       
                else e[k] = ""; //no series, no default entity values                                                                          
            }                                                                                                              
                                                                                                                           
            //apply overrides from the object                                                                           
            for(let k in o.entities) {                                                                                  
                if(o.entities[k]) e[k] = o.entities[k];                                                                 
            }                                                                                
                                                   
            o._exclude = o.exclude;
            if(o._type == "exclude") o._exclude = true;     
            
            const subject = this.findSubject(o);                                                              
            if(subject.exclude) o._exclude = true;                                                                     
                                                                          
            //if sub is not set, use subject mapping as default                                                         
            if(!o.entities.subject) {                                                                                   
                e.subject = subject.subject;                                                                            
            }                                                                                                           
                                                                                                                        
            const session = this.findSession(subject, o.AcquisitionDate);                                                       
            if(session.exclude) o._exclude = true;                                                                      
                                                                                                                        
            //if ses is not set, use session mapping as default                                                         
            if(!o.entities.session) {                                                                                   
                e.session = session.session;                                                                            
            }                                                                                                           
                                                                                                                        
            o._entities = e; 
        },
    }
});

</script>

<template>
<div id="here">
    <aside>
        <h1 style="font-size: 25pt"><span style="letter-spacing: -3px; opacity: 0.6;">ez</span>BIDS</h1>
        <ul>
            <li :class="{active: page == 'upload'}">Upload DICOM</li>
            <li :class="{active: page == 'description'}">BIDS Description</li>
            <li :class="{active: page == 'subject'}">Subjects/Sessions</li>
            <li :class="{active: page == 'participant'}">Participants Info</li>
            <li :class="{active: page == 'seriespage'}">Series Mapping</li>
            <li :class="{active: page == 'event'}">Events</li>
            <li :class="{active: page == 'object'}">Object Adjustment</li>
            <li :class="{active: page == 'deface'}">Deface</li>
            <li :class="{active: page == 'finalize'}">Finalize</li>
        </ul>

        <!--
        <div style="padding: 15px;" v-if="$root.session">
            <p style="font-size: 80%; line-height: 150%; opacity: 0.8;">* You can reload page to revert session to the initial state.</p>
        </div>
        -->
        <p class="menu-footer">
            <a href="https://github.com/brainlife/ezbids" target="github">
                <font-awesome-icon :icon="['fab', 'github']" />
            </a>
        </p>
    </aside>
    <section>
        <Upload v-if="page == 'upload'" ref="upload"/>
        <Description v-if="page == 'description'" ref="description"/>
        <Subject v-if="page == 'subject'" ref="subject"/>
        <Participant v-if="page == 'participant'" ref="participant"/>
        <SeriesPage v-if="page == 'seriespage'" ref="seriespage"/>
        <Events v-if="page == 'event'" ref="event"
            @mapObjects="mapObjects"/>
        <Objects v-if="page == 'object'" ref="object" 
            @mapObjects="mapObjects"
            @updateObject="updateObject"/>       
        <Deface v-if="page == 'deface'" ref="deface"/>
        <Finalize v-if="page == 'finalize'" ref="finalize"/>

        <br>
        <div class="page-action" v-if="session">
            <el-button v-if="backLabel" type="info" @click="back">{{backLabel}}</el-button>
            <el-button v-if="nextLabel" type="primary" @click="next" style="float: right;">{{nextLabel}}</el-button>
        </div>
    </section>
</div>
</template>

<style>
html, body, #app, #app-container {
    height: 100%;
}
body {
    margin: 0;
    font-family: Avenir, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    color: #333;
}
p {
    line-height: 175%;
}
a {
    color: inherit;
}

.el-table td.el-table__cell {
    vertical-align: top;
}
.el-textarea__inner {
    font-size: 90% !important;
}
.el-checkbox {
    height: inherit !important;
}
pre {
    font-size: 85%;
    white-space: pre-wrap;
}

</style>

<style scoped>
aside h1 {
    padding: 0;
    margin: 0;
}
aside {
    position: fixed;
    width: 200px;
    top: 0;
    left: 0;
    height: 100%;

    background-color: #eee;
    color: #333;
}
aside h1 {
    padding: 10px;
}
aside ul {
    list-style: none;
    padding-left: 0;
}
aside ul li {
    padding: 10px;
}
/*
aside ul li:hover {
    cursor: pointer;
    background-color: #0001;
}
*/
aside ul li.active {
    background-color: rgb(103, 194, 58);
    color: white;
}
.menu-footer {
    padding: 10px;
}
section {
    margin-left: 200px;
    padding-bottom: 100px;
}
footer {
    background-color: #B3C0D1;
    color: #333;
    line-height: 60px;
}
.page-action {
    padding: 0 20px;
    position: fixed;
    height: 40px;
    bottom: 0;
    right: 0;
    left: 200px;
    padding: 10px;
    background-color: #0003;
    z-index: 3;
}
</style>
