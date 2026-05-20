<template>
    <div style="display: flex">
        <div
            style="display: flex; flex-direction: column; box-sizing: border-box; height: 100vh; padding: 1rem 2rem"
            class="brainlife-lite aside-width"
        >
            <div class="brainlife-lite" style="flex: 0 0 auto">
                <div style="display: flex; align-items: center; width: 100%; height: 100%">
                    <h1 style="color: white; margin: 0; margin-right: 10px">
                        <span style="letter-spacing: -3px; opacity: 0.6; margin: 0">ez</span>BIDS
                    </h1>
                    <DisplayMode />
                </div>
            </div>
            <div class="aside-back-dashboard" style="flex: 0 0 auto">
                <router-link :to="{ name: 'dashboard' }">
                    <el-button class="aside-back-dashboard-btn" aria-label="Back to dashboard" size="small">
                        <font-awesome-icon :icon="['fas', 'angle-left']" />
                        Dashboard
                    </el-button>
                </router-link>
            </div>
            <aside style="flex: 1 1 auto; min-height: 0; overflow: auto">
                <el-steps :active="activeValue" direction="vertical">
                    <el-step
                        v-for="page in pages"
                        :key="page.key"
                        :title="page.title"
                        :description="page.description"
                    />
                </el-steps>
            </aside>
            <div class="aside-external-links" role="navigation" aria-label="External resources" style="flex: 0 0 auto">
                <el-tooltip content="Brainlife" placement="top">
                    <a href="https://brainlife.io" target="_blank" rel="noopener noreferrer">
                        <el-button circle class="aside-external-btn">
                            <img src="./assets/bl_logo.png" alt="Brainlife" width="14" />
                        </el-button>
                    </a>
                </el-tooltip>
                <el-tooltip content="Github" placement="top">
                    <a href="https://github.com/brainlife/ezbids" target="_blank" rel="noopener noreferrer">
                        <el-button circle class="aside-external-btn">
                            <font-awesome-icon :icon="['fab', 'github']" />
                        </el-button>
                    </a>
                </el-tooltip>
                <el-tooltip content="Documentation" placement="top">
                    <a href="https://brainlife.io/docs/using_ezBIDS/" target="_blank" rel="noopener noreferrer">
                        <el-button circle class="aside-external-btn">
                            <font-awesome-icon :icon="['fas', 'book']" />
                        </el-button>
                    </a>
                </el-tooltip>
            </div>
        </div>
        <section class="base-convert-main">
            <template v-if="getSessionError">
                <div class="base-convert-scroll">
                    <div class="base-convert-content">
                        <el-alert
                            type="error"
                            :closable="false"
                            show-icon
                            class="base-convert-session-error"
                            role="alert"
                        >
                            Cannot find the session. There may have been an error during session creation, or the
                            uploaded data may have been deleted.
                        </el-alert>

                        <SessionDebugDownloads v-if="session?._id" wrapper-class="base-convert-error-debug" />
                        <p v-else class="base-convert-error-no-id">No session id is available for downloads.</p>
                    </div>
                </div>
            </template>

            <template v-else>
                <div ref="mainScroll" class="base-convert-scroll">
                    <div class="base-convert-content">
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
                    </div>
                </div>
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
                <niivue :path="niivuePath" @close="niivuePath = undefined" />
            </template>
        </section>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState, mapGetters } from 'vuex';

import SessionDebugDownloads from '@/components/SessionDebugDownloads.vue';
import Upload from '@/features/upload/Upload.vue';
import Description from '@/features/description/Description.vue';
import Subject from '@/features/subject/Subject.vue';
import Participant from '@/features/participant/Participant.vue';
import SeriesPage from '@/features/series/SeriesPage.vue';
import Objects from '@/features/objects/Objects.vue';
import Events from '@/features/events/Events.vue';
import Deface from '@/features/deface/Deface.vue';
import Finalize from '@/features/finalize/Finalize.vue';
import Feedback from '@/features/feedback/Feedback.vue';
import { authRequired, hasJWT, createEventsTSV } from './lib';
//https://github.com/element-plus/element-plus/issues/436#issuecomment-961386582
import { ElNotification } from 'element-plus';
import 'element-plus/es/components/notification/style/css';

import { setSectionIDs, funcQA, fmapQA, dwiQA, petQA, setRun, setVolumeThreshold, setIntendedFor } from './libUnsafe';

import niivue from '@/components/niivue.vue';
import { IObject } from '@/store/store.types';
import DisplayMode from '@/components/DisplayMode.vue';
export default defineComponent({
    components: {
        SessionDebugDownloads,
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

            /** Cleared in beforeUnmount so polling stops when leaving convert. */
            sessionPollIntervalId: null as number | null,

            /** Set when loadSession / loadEzbids fail (invalid session or server error). */
            getSessionError: false,
        };
    },

    computed: {
        ...mapState(['session', 'ezbids', 'events', 'page', 'config']),
        ...mapGetters(['getBIDSEntities', 'getBIDSMetadata', 'findSession', 'findSubject']),

        authRequired() {
            return authRequired();
        },

        hasJWT() {
            return hasJWT();
        },

        activeValue() {
            const activeIndex = this.pages.findIndex((p) => p.key === this.page);
            if (activeIndex < 0) return 0;
            return activeIndex;
        },

        backLabel(): string | null {
            switch (this.page) {
                case 'upload':
                    if (this.session) return 'Re-Upload';
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
        const hash = location.hash;

        let sessionId = undefined;
        if (!hash) {
            ElNotification({
                title: 'Could not load session ID',
                message: '',
                type: 'error',
            });
            return;
        } else {
            // For both hash location strategy (ezBIDS) and regular routing, the session ID is the last part of the hash.
            const parts = hash.split('#');
            sessionId = parts[parts.length - 1];
            if (!sessionId) {
                ElNotification({
                    title: 'Could not load session ID',
                    message: '',
                    type: 'error',
                });
                return;
            }
        }

        try {
            await this.$store.dispatch('reload', sessionId);
        } catch (e) {
            console.error(e);
            this.getSessionError = true;
            return;
        }

        this.mapObjects();
        this.$store.commit('organizeObjects');
        this.$store.dispatch('loadDefaceStatus');

        this.sessionPollIntervalId = window.setInterval(async () => {
            if (this.getSessionError) return;
            if (!this.session) return;

            try {
                switch (this.session.status) {
                    case 'analyzed':
                    case 'finished':
                        break;
                    case 'defacing':
                        await this.$store.dispatch('loadDefaceStatus');
                        await this.$store.dispatch('loadSession');
                        break;
                    default:
                        await this.$store.dispatch('loadSession');
                }

                if (this.ezbids.notLoaded) {
                    await this.$store.dispatch('loadEzbids');
                }
            } catch (e) {
                console.error(e);
                this.getSessionError = true;
            }
        }, 5000);
    },

    beforeUnmount() {
        if (this.sessionPollIntervalId != null) {
            clearInterval(this.sessionPollIntervalId);
            this.sessionPollIntervalId = null;
        }
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

                    const scrollEl = this.$refs.mainScroll as HTMLElement | undefined;
                    scrollEl?.scrollTo({ top: 0 });
                }
            });
        },

        back() {
            const idx = this.pages.findIndex((p) => p.key === this.page);
            if (idx == 0) {
                if (confirm('Do you really want to start over?')) {
                    this.$router.push('/dashboard');
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
.brainlife-lite {
    background-color: #2d3748;
}

:deep(.el-step__title) {
    color: #9ca3af;
    font-size: small;

    padding-bottom: 0px !important; // this extra padding is causing a scrollbar to appear
}

:deep(.el-step__title.is-process) {
    color: #fff;
}

:deep(.el-step__description) {
    color: #9ca3af;
    font-size: x-small;
}

:deep(.el-step__description.is-process) {
    color: #fff;
}

:deep(.el-step__head.is-process) {
    .el-step__icon {
        color: black;
        border-color: white;
        background-color: white;
    }
}

:deep(.el-step__icon.is-text) {
    background-color: #9ca3af;
    color: black;
    border-color: #9ca3af;
}

.aside-back-dashboard {
    flex-shrink: 0;
    margin-bottom: 1rem;
    margin-top: 1rem;

    :deep(a) {
        display: block;
        width: 100%;
        text-decoration: none;
    }
}

.aside-back-dashboard-btn {
    width: 100%;
    justify-content: center;
    color: #e2e8f0 !important;
    border-color: #718096 !important;
    background: transparent !important;

    &:hover,
    &:focus {
        color: #fff !important;
        border-color: #cbd5e0 !important;
        background: rgba(255, 255, 255, 0.08) !important;
    }
}

.aside-width {
    width: 260px;
    min-width: 260px;
    max-width: 260px;
}

.aside-external-links {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px solid #4a5568;
}

.aside-external-btn {
    background-color: whitesmoke !important;
    border-color: black !important;

    svg {
        color: black !important;
    }
}

.base-convert-main {
    display: flex;
    flex-direction: column;
    flex-grow: 1;
    max-height: 100vh;
    min-height: 0;
    box-sizing: border-box;
    padding: 1rem;
    overflow: hidden;
}

.base-convert-scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
}

.base-convert-content {
    padding: 1rem;
}

.page-action {
    display: flex;
    flex-shrink: 0;
    justify-content: space-between;
    padding: 1rem;
    padding-bottom: 0;
    background-color: white;
    border-top: 1px solid var(--el-border-color-lighter, #ebeef5);
    color: #333;
}

.base-convert-session-error {
    margin-bottom: 1rem;
}

.base-convert-error-no-id {
    color: #909399;
    margin-top: 1rem;
}
</style>
