<template>
    <div>
        <div class="app-header" style="display: flex; align-items: center; justify-content: space-between">
            <div style="height: 100%; display: flex; align-items: center; padding: 0 1rem">
                <h1 style="color: white; margin: 0"><span style="letter-spacing: -3px; opacity: 0.6">ez</span>BIDS</h1>
                <DisplayMode />
            </div>
            <div>
                <div class="menu-footer">
                    <a href="https://brainlife.io" target="_blank" style="margin-right: 8px; text-decoration: none">
                        <el-button type="success" style="display: flex; background-color: #20ab5c">
                            Open Brainlife
                        </el-button>
                    </a>
                    <a
                        href="https://github.com/brainlife/ezbids"
                        target="_blank"
                        style="margin-right: 8px; text-decoration: none"
                    >
                        <el-button type="success" style="display: flex; background-color: #20ab5c">
                            Open Github
                        </el-button>
                    </a>
                    <a
                        href="https://brainlife.io/docs/using_ezBIDS/"
                        target="_blank"
                        style="margin-right: 8px; text-decoration: none"
                    >
                        <el-button type="success" style="display: flex; background-color: #20ab5c">
                            Open Documentation
                        </el-button>
                    </a>
                </div>
            </div>
        </div>
        <div style="display: flex">
            <aside>
                <el-steps :active="activeValue" direction="vertical">
                    <el-step
                        v-for="page in pages"
                        :key="page.key"
                        :title="page.title"
                        :description="page.description"
                    />
                </el-steps>
            </aside>
            <div style="flex-grow: 1">
                <section>
                    <Upload v-if="page === 'upload'" ref="upload" />
                    <Description v-if="page === 'description'" ref="description" />
                    <Subject v-if="page === 'subject'" ref="subject" />
                    <SeriesPage v-if="page === 'seriespage'" ref="seriespage" @niivue="openNiivue" />
                    <Events v-if="page === 'event'" ref="event" @mapObjects="mapObjects" />
                    <Objects
                        v-if="page === 'object'"
                        ref="object"
                        @niivue="openNiivue"
                        @mapObjects="mapObjects"
                        @updateObject="updateObject"
                    />
                    <Deface v-if="page === 'deface'" ref="deface" @niivue="openNiivue" />
                    <Participant v-if="page === 'participant'" ref="participant" />
                    <Finalize v-if="page === 'finalize'" ref="finalize" />
                    <Feedback v-if="page === 'feedback'" ref="feedback" />

                    <br />
                    <footer v-if="session" class="page-action">
                        <el-button style="width: 260px" v-if="backLabel" :type="backButtonType" @click="back">
                            <font-awesome-icon :icon="['fas', 'angle-left']" />
                            {{ backLabel }}
                        </el-button>
                        <el-button style="width: 260px" v-if="nextLabel" type="primary" @click="next">
                            {{ nextLabel }}
                            <font-awesome-icon :icon="['fas', 'angle-right']" />
                        </el-button>
                    </footer>
                </section>
                <niivue :path="niivuePath" @close="niivuePath = undefined" />
            </div>
        </div>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState, mapGetters } from 'vuex';

import Upload from './Upload.vue';
import Description from './Description.vue';
import Subject from './Subject.vue';
import Participant from './Participant.vue';
import SeriesPage from './SeriesPage.vue';
import Objects from './Objects.vue';
import Events from './Events.vue';
import Deface from './Deface.vue';
import Finalize from './Finalize.vue';
import Feedback from './Feedback.vue';
import { authRequired, createEventsTSV } from './lib';

//https://github.com/element-plus/element-plus/issues/436#issuecomment-961386582
import { ElNotification } from 'element-plus';
import 'element-plus/es/components/notification/style/css';

import { setSectionIDs, funcQA, fmapQA, dwiQA, petQA, setRun, setVolumeThreshold, setIntendedFor } from './libUnsafe';

import niivue from './components/niivue.vue';
import DisplayMode from './components/DisplayMode.vue';
import { IObject } from './store/store.types';

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
                { title: 'Upload Imaging Data', description: '', key: 'upload' },
                { title: 'Dataset Description', description: '', key: 'description' },
                { title: 'Subjects/Sessions', description: 'Data Mapping (1/3)', key: 'subject' },
                { title: 'Series Mapping', description: 'Data Mapping (2/3)', key: 'seriespage' },
                { title: 'Events', description: 'Data Mapping (3/3)', key: 'event' },
                { title: 'Dataset Review', description: '', key: 'object' },
                { title: 'Deface', description: 'Optional', key: 'deface' },
                { title: 'Participants Info', description: 'Optional', key: 'participant' },
                { title: 'Finalize', description: '', key: 'finalize' },
                { title: 'Feedback', description: '', key: 'feedback' },
            ],

            //item to open in niivue
            //niivueItem: undefined as IObjectItem|undefined,
            niivuePath: undefined as string | undefined,
        };
    },

    computed: {
        ...mapState(['session', 'ezbids', 'events', 'page', 'config']),
        ...mapGetters(['getBIDSEntities', 'getBIDSMetadata', 'findSession', 'findSubject']),

        hasAuth() {
            return authRequired();
        },

        activeValue() {
            const activeIndex = this.pages.findIndex((p) => p.key === this.page);
            if (activeIndex < 0) return 0;
            return activeIndex;
        },

        backLabel(): string | null {
            switch (this.page) {
                case 'upload':
                    if (this.session) return 'Re-Upload'; //TODO - looks like this is broken
                    return null;
                default:
                    return 'Back';
            }
        },

        backButtonType(): string {
            switch (this.page) {
                case 'upload':
                    return 'warning';
                default:
                    return 'info';
            }
        },

        nextLabel(): string | null {
            switch (this.page) {
                case 'upload':
                    return this.session && this.session.pre_finish_date && !this.ezbids.notLoaded ? 'Next' : null;
                case 'feedback':
                    return null;
                default:
                    return 'Next';
            }
        },
    },

    async created() {
        this.$store.commit('reset');
        if (location.hash) {
            await this.$store.dispatch('reload', location.hash.substring(1));
            this.mapObjects();
            this.$store.commit('organizeObjects');
            this.$store.dispatch('loadDefaceStatus');
        }

        window.setInterval(async () => {
            if (this.session) {
                switch (this.session.status) {
                    case 'analyzed':
                    case 'finished':
                        break;
                    case 'defacing':
                        this.$store.dispatch('loadDefaceStatus');
                        this.$store.dispatch('loadSession', this.session._id);
                        break;
                    default:
                        //deface
                        //defaced
                        this.$store.dispatch('loadSession', this.session._id);
                }

                if (this.ezbids.notLoaded) {
                    await this.$store.dispatch('loadEzbids');
                }
            }
        }, 5000);
    },

    methods: {
        next() {
            this.mapObjects();
            this.$store.commit('organizeObjects');

            // @ts-ignore
            this.$refs[this.page].isValid((err: string) => {
                if (err) {
                    console.log('page invalid');
                    console.error(err);
                    ElNotification({ title: 'Failed', message: err });
                } else {
                    const idx = this.pages.findIndex((p) => p.key === this.page);
                    this.$store.commit('setPage', this.pages[idx + 1].key);
                    switch (this.page) {
                        case 'seriespage':
                            petQA(this.ezbids);
                            break;
                        case 'event':
                            setVolumeThreshold(this.ezbids); // Don't move to Objects.Vue, means you can't un-exclude it on the page
                            setSectionIDs(this.ezbids);
                            funcQA(this.ezbids);
                            fmapQA(this.ezbids);
                            dwiQA(this.ezbids);
                            setRun(this.ezbids); //keep here for initial func/events mapping to corresponding func/bold
                            setIntendedFor(this.ezbids);
                            this.mapObjects();
                            break;
                        case 'object':
                            createEventsTSV(this.ezbids, this.ezbids.events);
                            break;
                    }

                    //scroll page to the top
                    window.scrollTo(0, 0);
                }
            });
        },

        back() {
            const idx = this.pages.findIndex((p) => p.key === this.page);
            if (idx == 0) {
                if (confirm('Do you really want to start over?')) {
                    document.location.hash = '';
                    document.location.reload();
                }
            } else {
                this.$store.commit('setPage', this.pages[idx - 1].key);
            }
        },

        updateObject(o: IObject) {
            this.mapObject(o);
            // @ts-ignore
            this.$refs.object.validateAll(); //I need to validate the entire list.. so I can detect collision
            this.$store.commit('organizeObjects');
        },

        openNiivue(path: string) {
            console.log('opening niivue', path);
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
            if (series) {
                //func/events doesn't have any series
                o._SeriesDescription = series.SeriesDescription.replace('_RR', ''); //helps in objects view
                o._type = series.type;
            }
            if (o.type) o._type = o.type; //object level override

            //clone bids entity for this _type to preserve proper key ordering
            const e = Object.assign({}, this.getBIDSEntities(o._type));
            for (let k in e) {
                if (series) e[k] = series.entities[k];
                else e[k] = ''; //no series, no default entity values
            }

            //apply overrides from the object
            for (let k in o.entities) {
                if (o.entities[k]) e[k] = o.entities[k];
            }

            o._exclude = o.exclude;
            if (o._type == 'exclude') o._exclude = true;

            const subject = this.findSubject(o);
            if (subject.exclude) o._exclude = true;

            //if sub is not set, use subject mapping as default
            if (!o.entities.subject) {
                e.subject = subject.subject;
            }

            const session = this.findSession(subject, o);
            if (session.exclude) o._exclude = true;

            //if ses is not set, use session mapping as default
            if (!o.entities.session) {
                e.session = session.session;
            }

            o._entities = e;
        },
        handleSignout() {
            document.location.href = this.config.authSignOut;
        },
    },
});
</script>

<style scoped lang="scss">
.app-header {
    height: 64px;
    max-height: 44px;
    padding: 10px;
    background-color: #3782e5;
}

aside {
    height: calc(100vh - 64px - 4rem);
    width: 196px;
    min-width: 196px;
    max-width: 196px;
    padding: 2rem;

    .step {
        padding: 1rem 0;
    }
}

section {
    max-height: calc(100vh - 64px - 8rem);
    padding: 2rem;
    overflow-y: auto;
}

.menu-footer {
    padding: 14px;
    display: flex;
    justify-content: space-between;

    svg:hover {
        color: lightgray !important;
    }

    img:hover {
        opacity: 0.8 !important;
    }

    .menu-footer-icon {
        font-size: 1.6rem;
        color: white;
        width: 28px;
        height: 28px;
    }
}

.container {
    padding: 0 160px;
    padding-bottom: 100px;
}

footer {
    background-color: #b3c0d1;
    color: #333;
    line-height: 60px;
}

.page-action {
    display: flex;
    justify-content: space-between;
    padding: 1rem 0;
    position: fixed;
    height: 40px;
    bottom: 0;
    width: calc(100vw - 260px - 4rem);
    background-color: white;
    z-index: 3;
}

.list-header {
    opacity: 0.5;
    font-weight: bold;
    background-color: #0001;
}
</style>
