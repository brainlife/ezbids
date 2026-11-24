<template>
    <div>
        <aside>
            <a class="brand" href="#" aria-label="ezBIDS home" @click.prevent="$router.push('/')">
                <BrandLockup />
            </a>

            <nav class="steps">
                <template v-for="g in navGroups" :key="g.title || g.items[0].page">
                    <div v-if="g.title" class="group">{{ g.title }}</div>
                    <div
                        v-for="item in g.items"
                        :key="item.page"
                        :class="['step', { active: page === item.page, done: pageIndex(item.page) < pageIndex(page) }]"
                    >
                        <span class="n">{{ pageIndex(item.page) + 1 }}</span>
                        {{ item.label }}
                    </div>
                </template>
            </nav>

            <div class="aside-foot">
                <div class="menu-footer">
                    <el-tooltip content="Open github">
                        <a href="https://github.com/brainlife/ezbids">
                            <font-awesome-icon class="menu-footer-icon" :icon="['fab', 'github']" />
                        </a>
                    </el-tooltip>
                    <el-tooltip content="Open documentation">
                        <a href="https://brainlife.io/docs/using_ezBIDS/">
                            <font-awesome-icon class="menu-footer-icon" :icon="['fa', 'book']" />
                        </a>
                    </el-tooltip>
                </div>

                <ManageUsersDialog v-if="hasAuth"></ManageUsersDialog>

                <el-button class="signout" @click="handleSignout">Sign out</el-button>
            </div>
        </aside>
        <section :class="{ 'page-panel': !fixedPages.includes(page) }">
            <Upload v-if="page === 'upload'" ref="upload" />
            <Description v-if="page === 'description'" ref="description" />
            <Subject v-if="page === 'subject'" ref="subject" />
            <Participant v-if="page === 'participant'" ref="participant" />
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
            <Finalize v-if="page === 'finalize'" ref="finalize" />
            <Feedback v-if="page === 'feedback'" ref="feedback" />

            <br />
            <div v-if="session" class="page-action">
                <el-button v-if="backLabel" :type="backButtonType" @click="back">
                    <font-awesome-icon :icon="['fas', 'angle-left']" />
                    {{ backLabel }}
                </el-button>
                <el-button v-if="nextLabel" type="primary" style="float: right" @click="next">
                    {{ nextLabel }}
                    <font-awesome-icon :icon="['fas', 'angle-right']" />
                </el-button>
            </div>
        </section>
        <niivue :path="niivuePath" @close="niivuePath = undefined" />
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
import ManageUsersDialog from './components/dialogs/ManageUsersDialog.vue';
import { IObject } from './store';
import { hasAuth, createEventsTSV } from './lib';

//https://github.com/element-plus/element-plus/issues/436#issuecomment-961386582
import { ElNotification } from 'element-plus';
import 'element-plus/es/components/notification/style/css';

import { setSectionIDs, funcQA, fmapQA, dwiQA, petQA, setRun, setVolumeThreshold, setIntendedFor } from './libUnsafe';

import niivue from './components/niivue.vue';
import BrandLockup from './components/brand/BrandLockup.vue';

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
        BrandLockup,
        ManageUsersDialog: ManageUsersDialog,

        niivue,
    },

    data() {
        return {
            //page order
            pages: [
                'upload',
                'description',
                'subject',
                'seriespage',
                'event',
                'object',
                'deface',
                'participant',
                'finalize',
                'feedback',
            ],

            // sidebar steps, in page order
            navGroups: [
                {
                    title: '',
                    items: [
                        { page: 'upload', label: 'Upload imaging data' },
                        { page: 'description', label: 'Dataset description' },
                    ],
                },
                {
                    title: 'Dataset mappings',
                    items: [
                        { page: 'subject', label: 'Subjects / sessions' },
                        { page: 'seriespage', label: 'Series mapping' },
                        { page: 'event', label: 'Events' },
                    ],
                },
                { title: '', items: [{ page: 'object', label: 'Dataset review' }] },
                {
                    title: 'Optional',
                    items: [
                        { page: 'deface', label: 'Deface' },
                        { page: 'participant', label: 'Participants info' },
                    ],
                },
                {
                    title: '',
                    items: [
                        { page: 'finalize', label: 'Access BIDS data' },
                        { page: 'feedback', label: 'Feedback' },
                    ],
                },
            ],

            // pages that lay out their own fixed work area; the rest sit in a white panel
            fixedPages: ['seriespage', 'event', 'object', 'deface'],

            //item to open in niivue
            //niivueItem: undefined as IObjectItem|undefined,
            niivuePath: undefined as string | undefined,
        };
    },

    computed: {
        ...mapState(['session', 'ezbids', 'events', 'page', 'config']),
        ...mapGetters(['getBIDSEntities', 'getBIDSMetadata', 'findSession', 'findSubject']),

        hasAuth() {
            return hasAuth();
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
                    // outlined, like brainlife-lite's secondary actions (Element 1.2 paints typed buttons
                    // with an inline background, so a CSS override of the info type doesn't take)
                    return 'default';
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
        pageIndex(page: string): number {
            return this.pages.indexOf(page);
        },

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
                    const idx = this.pages.indexOf(this.page);
                    this.$store.commit('setPage', this.pages[idx + 1]);
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
            const idx = this.pages.indexOf(this.page);
            if (idx == 0) {
                if (confirm('Do you really want to start over?')) {
                    document.location.hash = '';
                    document.location.reload();
                }
            } else {
                this.$store.commit('setPage', this.pages[idx - 1]);
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
aside {
    position: fixed;
    width: var(--aside-w);
    top: 0;
    left: 0;
    height: 100%;
    background: var(--nav-bg);
    border-right: 1px solid var(--line);
    color: var(--ink);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
}

.brand {
    display: block;
    padding: 18px 16px 14px;
    text-decoration: none;
}

.steps {
    padding: 4px 10px;
    flex: 1;

    .group {
        font-size: 0.68rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--ink-2);
        padding: 14px 10px 4px;
    }

    .step {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 10px;
        margin: 2px 0;
        border-radius: var(--panel-radius);
        font-weight: 300;
        color: var(--ink);
    }

    .n {
        width: 20px;
        height: 20px;
        flex: none;
        border-radius: 50%;
        border: 1px solid var(--el-border-color-base);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.7rem;
        color: var(--ink-2);
    }

    .step.done .n {
        background: var(--el-color-primary-light-9);
        border-color: var(--el-color-primary-light-7);
        color: var(--el-color-primary);
    }

    .step.active {
        background: var(--el-color-primary-light-9);
        color: var(--el-color-primary);
        font-weight: 500;

        .n {
            background: var(--el-color-primary);
            border-color: var(--el-color-primary);
            color: #fff;
        }
    }
}

.aside-foot {
    padding: 12px 16px 16px;
    border-top: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    gap: 10px;

    .signout {
        width: 100%;
        font-family: inherit;
    }
}

.menu-footer {
    display: flex;
    gap: 16px;

    .menu-footer-icon {
        font-size: 1.2rem;
        color: var(--ink-2);
        width: 20px;
        height: 20px;
    }

    a:hover .menu-footer-icon {
        color: var(--el-color-primary);
    }
}

section {
    margin-left: var(--aside-w);
    padding-bottom: 100px;
}

section.page-panel {
    margin: 16px 16px 76px calc(var(--aside-w) + 16px);
    padding: 8px 20px 20px;
    background: var(--panel-bg);
    border: 1px solid var(--line);
    border-radius: var(--panel-radius);
    min-height: calc(100vh - 92px);
    box-sizing: border-box;
}

.page-action {
    position: fixed;
    height: 40px;
    bottom: 0;
    right: 0;
    left: var(--aside-w);
    padding: 10px 16px;
    background: var(--panel-bg);
    border-top: 1px solid var(--line);
    z-index: 3;
}
</style>
