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
import Feedback from './Feedback.vue'

import { IObject } from './store'

//https://github.com/element-plus/element-plus/issues/436#issuecomment-961386582
import { ElNotification } from 'element-plus'
//import 'element-plus/es/components/notification/style/css'

import { setSectionIDs, funcQA, fmapQA, dwiQA, setRun, setVolumeThreshold } from './libUnsafe'

//import { IObjectItem } from './store'
import { createEventsTSV } from './lib'

import niivue from './components/niivue.vue'

export default defineComponent({
    components: {
       Upload,
       Description,
       Subject,
       SeriesPage,
       Events,
       Objects,
       Deface,
       Participant,
       Finalize,
       Feedback,

       niivue,
    },

    data() {
        return {
            //page order
            pages: [
                "upload",
                "description",
                "subject",
                "seriespage",
                "event",
                "object",
                "deface",
                "participant",
                "finalize",
                "feedback",
            ],

            //item to open in niivue
            //niivueItem: undefined as IObjectItem|undefined,
            niivuePath: undefined as string|undefined,
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

        window.setInterval(async ()=>{
            if(this.session) {
                switch(this.session.status) {
                case "analyzed":
                case "finished":
                    break;
                case "defacing":
                    this.$store.dispatch("loadDefaceStatus");
                    this.$store.dispatch("loadSession", this.session._id);
                    break;
                default:
                    //deface
                    //defaced
                    this.$store.dispatch("loadSession", this.session._id);
                }

                if(this.ezbids.notLoaded) {
                    await this.$store.dispatch("loadEzbids");
                }
            }
        }, 5000)
    },

    computed: {
        ...mapState(['session', 'ezbids', 'events', 'page']),
        ...mapGetters(['getBIDSEntities', 'getBIDSMetadata', 'findSession', 'findSubject']),

        backLabel(): string|null {
            switch(this.page) {
            case "upload":
               if(this.session) return "Re-Upload"; //TODO - looks like this is broken
               return null;
            default:
                    return "Back";
            }
        },

        backButtonType() : string {
            switch(this.page) {
            case "upload":
                return "warning";
            default:
                return "info";
            }
        },

        nextLabel() : string|null {
            switch(this.page) {
            case "upload":
                return (this.session && this.session.pre_finish_date && !this.ezbids.notLoaded)?"Next":null;
            case "feedback":
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
                    this.$store.commit("setPage", this.pages[idx+1]);
                    switch(this.page) {
                    case "event":
                        setVolumeThreshold(this.ezbids);
                        setSectionIDs(this.ezbids);
                        funcQA(this.ezbids);
                        fmapQA(this.ezbids);
                        dwiQA(this.ezbids);
                        setRun(this.ezbids);
                        this.mapObjects();
                        break;
                    case "object":
                        // createEventsTSV(this.ezbids, this.events); // functionality replace by next line
                        createEventsTSV(this.ezbids, this.ezbids.events);
                        // setIntendedFor(this.ezbids); // Moving this into Objects.vue directly
                        break;
                    }

                    //scroll page to the top
                    window.scrollTo(0,0);
                }
            });
        },

        back() {
            const idx = this.pages.indexOf(this.page);
            if(idx == 0) {
                if(confirm("Do you really want to start over?")) {
                    document.location.hash = "";
                    document.location.reload();
                }
            } else {
                this.$store.commit("setPage", this.pages[idx-1]);
            }
        },

        updateObject(o: IObject) {
            this.mapObject(o);
            // @ts-ignore
            this.$refs.object.validateAll(); //I need to validate the entire list.. so I can detect collision
            this.$store.commit("organizeObjects");
        },

        openNiivue(path: string) {
            console.log("opening niivue", path);
            this.niivuePath = path;
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

            const session = this.findSession(subject, o);
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
<div>
    <aside>
        <h1 style="font-size: 25pt"><span style="letter-spacing: -3px; opacity: 0.6;">ez</span>BIDS</h1>

        <ul>
            <li :class="{active: page == 'upload'}">Upload Imaging Data</li>
            <li :class="{active: page == 'description'}">Dataset Description</li>
        </ul>

        <div class="section">
            <h2 class="list-header">Dataset Mappings</h2>
            <ul>
                <li :class="{active: page == 'subject'}">Subjects/Sessions</li>
                <li :class="{active: page == 'seriespage'}">Series Mapping</li>
                <li :class="{active: page == 'event'}">Events</li>
            </ul>
        </div>

        <ul>
            <li :class="{active: page == 'object'}">Dataset Review</li>
        </ul>

        <div class="section">
            <h2 class="list-header">Optional</h2>
            <ul>
                <li :class="{active: page == 'deface'}">Deface</li>
                <li :class="{active: page == 'participant'}">Participants Info</li>
            </ul>
        </div>

        <ul>
            <li :class="{active: page == 'finalize'}">Get BIDS</li>
            <li :class="{active: page == 'feedback'}">Feedback</li>
        </ul>

        <p class="menu-footer" style="font-size: 150%">
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
        <SeriesPage v-if="page == 'seriespage'" ref="seriespage"
            @niivue="openNiivue"/>
        <Events v-if="page == 'event'" ref="event"
            @mapObjects="mapObjects"/>
        <Objects v-if="page == 'object'" ref="object"
            @niivue="openNiivue"
            @mapObjects="mapObjects"
            @updateObject="updateObject"/>
        <Deface v-if="page == 'deface'" ref="deface"
            @niivue="openNiivue"/>
        <Finalize v-if="page == 'finalize'" ref="finalize"/>
        <Feedback v-if="page == 'feedback'" ref="feedback"/>

        <br>
        <div class="page-action" v-if="session">
            <el-button v-if="backLabel" :type="backButtonType" @click="back">
                <font-awesome-icon :icon="['fas', 'angle-left']"/>
                {{backLabel}}
            </el-button>
            <el-button v-if="nextLabel" type="primary" @click="next" style="float: right;">
                {{nextLabel}}
                <font-awesome-icon :icon="['fas', 'angle-right']"/>
            </el-button>
        </div>
    </section>
    <niivue :path="niivuePath" @close="niivuePath = undefined"/>
</div>
</template>

<style lang="scss">
@import url('https://fonts.googleapis.com/css2?family=Merriweather+Sans:wght@400;700&family=Merriweather:wght@400;700');

html, body, #app, #app-container {
    height: 100%;
}
body {
    margin: 0;
    font-family: 'Merriweather Sans',Georgia,sans-serif;
    font-size: 14px;
    color: #333;
}
p {
    line-height: 175%;
    margin: 0 0 10px 0;
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
.el-popover.el-popper {
    word-break: break-word !important;
}
.hint {
    box-shadow: 1px 1px 3px #666;
    padding: 20px;
    margin: 10px 0;
    border-radius: 5px;
    h2 {
        margin-top: 0;
        color: #ccc;
    }
}
</style>

<style scoped lang="scss">
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
    h1 {
        padding: 10px;
    }
    h2 {
        margin-bottom: 0px;
        padding: 10px;
        font-size: 110%;
    }
    ul {
        list-style: none;
        padding-left: 0;
        margin: 0;

        li {
            padding: 10px;
        }
        li.active {
            background-color: rgb(103, 194, 58);
            color: white;
        }
    }
    .section {
        margin-bottom: 10px;
        ul {
            list-style: inside;
        }
    }

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
.list-header {
    opacity: 0.5;
    font-weight: bold;
    background-color: #0001;
}
</style>
