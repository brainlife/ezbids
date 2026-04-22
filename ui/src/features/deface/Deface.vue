<template>
    <div class="deface-page">
        <header class="deface-intro">
            <h2 class="deface-intro__title">Deface</h2>
            <p class="deface-intro__text">
                Defacing removes facial features from anatomical images to improve participant privacy.
            </p>
            <p class="deface-intro__text">
                ezBIDS uses the <b>allineate</b> method. Anatomical images are rewritten in closest canonical
                orientation (<i>as_closest_canonical</i>) before skull stripping.
            </p>
        </header>

        <section class="deface-card">
            <div class="deface-actions">
                <div class="deface-actions__meta">
                    <el-tag size="mini" type="info" effect="plain" class="deface-method-tag">Method: allineate</el-tag>
                    <p class="deface-actions__hint">Run defacing on all anatomical images in this dataset.</p>
                </div>
                <div class="deface-actions__buttons">
                    <el-button
                        v-if="showRunDefaceButton"
                        type="primary"
                        class="deface-cta"
                        :disabled="defaceButtonIsDisabled"
                        @click="runDeface"
                    >
                        Run Deface
                    </el-button>
                    <el-button v-if="isDefacing" type="warning" @click="cancel">Cancel Defacing</el-button>
                    <el-button v-if="session.deface_begin_date && session.deface_finish_date" @click="reset">
                        Reset Deface
                    </el-button>
                </div>
            </div>

            <el-alert v-if="anatObjects.length == 0" type="warning" class="deface-actions__alert">
                No anatomy files to deface. Please skip this step.
            </el-alert>
        </section>

        <section v-if="anatObjects.length" class="deface-card">
            <div v-if="session.status == 'deface' || session.status == 'defacing'">
                <h3>
                    Running <b>{{ ezbids.defacingMethod }}</b> ...
                </h3>
                <pre class="status">{{ session.status_msg }}</pre>
            </div>
            <div v-if="session.deface_finish_date">
                <el-alert type="success" show-icon>
                    Defacing completed! Please check the defacing results and proceed to the next page.
                </el-alert>
            </div>
            <div v-if="session.status == 'failed'">
                Failed!
                <pre class="status">{{ session.status_msg }}</pre>
            </div>
        </section>

        <section v-if="session.deface_begin_date" class="deface-card">
            <table class="table">
                <thead>
                    <tr>
                        <th></th>
                        <th>Original</th>
                        <th>Defaced</th>
                    </tr>
                </thead>
                <tr v-for="anat in anatObjects" :key="anat.idx">
                    <td>
                        <div style="margin-bottom: 0; font-size: 85%; line-height: 200%">
                            <span><small>sub</small> {{ anat._entities.subject }} </span>
                            <span v-if="anat._entities.session">
                                / <small>ses</small> {{ anat._entities.session }}
                            </span>
                        </div>
                        <el-tag type="info" size="mini">#{{ anat.series_idx }}</el-tag>
                        &nbsp;
                        <datatype :type="anat._type" :series_idx="anat.series_idx" :entities="anat.entities" />
                    </td>
                    <td width="40%" style="position: relative">
                        <el-radio v-model="anat.defaceSelection" label="original">Use Original</el-radio>
                        <div v-for="(item, itemIdx) in anat.items" :key="itemIdx">
                            <div v-if="item.pngPaths && item.pngPaths.length > 0 && item.pngPaths[0]">
                                <AsyncImageLink :path="item.pngPaths[0]" />
                                <el-button
                                    type="info"
                                    style="position: relative; top: 50px; left: 8px"
                                    size="small"
                                    @click="$emit('niivue', item.path)"
                                >
                                    <font-awesome-icon :icon="['fas', 'eye']" />
                                    NiiVue
                                </el-button>
                            </div>
                        </div>
                    </td>
                    <td width="40%" style="position: relative">
                        <el-radio v-model="anat.defaceSelection" label="defaced"
                            >Use Defaced (when finish defacing)</el-radio
                        >
                        <div v-if="anat.defaced">
                            <AsyncImageLink :path="`${getDefacedURL(anat)}.png`" />
                            <el-button
                                type="info"
                                style="position: absolute; top: 50px; left: 8px"
                                size="small"
                                @click="$emit('niivue', getDefacedURL(anat))"
                            >
                                <font-awesome-icon :icon="['fas', 'eye']" />
                                NiiVue
                            </el-button>
                        </div>
                        <p v-if="session.status == 'defacing' && !anat.defaced" class="missingThumb">
                            <small>
                                Defacing
                                <font-awesome-icon icon="spinner" pulse />
                            </small>
                        </p>
                        <p v-if="anat.defaceFailed" class="missingThumb fail"><small>Defacing Failed</small></p>
                    </td>
                </tr>
            </table>
        </section>
    </div>
</template>

<script lang="ts">
import { mapState, mapGetters } from 'vuex';
import { defineComponent } from 'vue';
import datatype from '@/components/datatype.vue';
import { ElNotification } from 'element-plus';
import AsyncImageLink from '@/components/AsyncImageLink.vue';
import { IObject } from '@/store/store.types';
import axios from 'axios';

export default defineComponent({
    components: {
        datatype,
        AsyncImageLink,
    },
    emits: ['niivue'],

    /*
    data() {
        return {
        }
    },
    */
    computed: {
        ...mapState(['ezbids', 'config', 'session', 'bidsSchema']),
        ...mapGetters(['getBIDSEntities']),

        isDefacing() {
            if (!this.$store.state.session) return false;
            return ['deface', 'defacing'].includes(this.$store.state.session.status);
        },
        isDesktopMode() {
            return window.env.IS_ELECTRON === 'true';
        },
        showRunDefaceButton() {
            return !this.isDefacing && !this.session.deface_finish_date;
        },
        defaceButtonIsDisabled() {
            return this.anatObjects.length === 0;
        },

        anatObjects() {
            return this.$store.state.ezbids.objects.filter((o: IObject) => o._type.startsWith('anat') && !o._exclude);
        },
    },

    mounted() {
        //initialize all anat to use defaced image by default
        this.anatObjects.forEach((o: IObject) => {
            if (!o.defaceSelection) o.defaceSelection = 'defaced';
        });
    },

    methods: {
        getDefacedURL(anat: IObject) {
            //find the image path first
            let item = anat.items.find((i) => i.path.endsWith('.nii.gz'));
            if (!item) return null;

            //guess the image path
            return item.path + '.defaced.nii.gz';
        },

        async cancel() {
            axios.post(`${this.config.apihost}/session/${this.session._id}/canceldeface`).then((res) => {
                if (res.data !== 'ok') {
                    ElNotification({ title: 'Failed', message: 'Failed to cancel defacing' });
                } else {
                    ElNotification({ title: 'Success', message: 'Requested to cancel defacing..' });
                }
                this.$store.dispatch('loadSession', this.session._id);
            });
        },

        async reset() {
            axios.post(`${this.config.apihost}/session/${this.session._id}/resetdeface`).then((res) => {
                if (res.data !== 'ok') {
                    ElNotification({ title: 'Failed', message: 'Failed to reset defacing' });
                }
                this.anatObjects.forEach((anat: IObject) => {
                    delete anat.defaced;
                    delete anat.defaceFailed;
                    anat.defaceSelection = 'defaced';
                });
                this.$store.dispatch('loadSession', this.session._id);
            });
        },

        async runDeface() {
            this.ezbids.defacingMethod = 'allineate';
            const list = this.anatObjects.map((o: IObject) => {
                return { idx: o.idx, path: o.items.find((i) => i.path?.endsWith('.nii.gz'))?.path };
            });

            //reset current status for all stats (in case it's ran previously)
            this.anatObjects.forEach((o: IObject) => {
                delete o.defaced;
            });

            axios
                .post(`${this.config.apihost}/session/${this.session._id}/deface`, {
                    list,
                    method: this.ezbids.defacingMethod,
                })
                .then((res) => {
                    if (res.data !== 'ok') {
                        ElNotification({ title: 'Failed', message: 'Failed to submit deface request' });
                    }
                    this.$store.dispatch('loadSession', this.session._id);
                });
        },

        isValid(cb: (v?: string) => void) {
            if (!this.ezbids.defacingMethod) return cb();
            if (!this.session.deface_begin_date) {
                return cb('Please run deface');
            }
            if (this.session.deface_begin_date && this.session.status == 'failed') {
                //let's assume it's the defacing that failed
                let err = undefined;
                this.anatObjects.forEach((o: IObject) => {
                    if (o.defaceSelection == 'defaced' && !o.defaced)
                        err = 'Please set to use original image for deface-failed images';
                });
                return cb(err);
            }
            if (!this.session.deface_finish_date) {
                return cb('Please wait for defacing to finish');
            }
            cb();
        },
    },
});
</script>
<style lang="scss" scoped>
.deface-page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0.5rem 1.25rem 2.75rem;
}

.deface-intro {
    margin-bottom: 1.25rem;
    padding: 1.35rem 1.5rem 1.5rem;
    border-radius: 10px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-fill-color-blank, #fff);
    box-shadow: 0 1px 2px rgb(0 0 0 / 4%);
}

.deface-intro__title {
    margin: 0 0 0.65rem;
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--el-text-color-primary, #303133);
}

.deface-intro__text {
    margin: 0.4rem 0 0;
    font-size: 14px;
    line-height: 1.6;
    color: var(--el-text-color-regular, #606266);
}

.deface-card {
    padding: 1.1rem 1.25rem;
    border-radius: 12px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-bg-color, #fff);
    margin-bottom: 1rem;
}

.deface-actions {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    flex-wrap: wrap;
}

.deface-actions__meta {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.deface-actions__hint {
    margin: 0;
    font-size: 13px;
    color: var(--el-text-color-secondary, #909399);
}

.deface-actions__buttons {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.deface-actions__alert {
    margin-top: 10px;
}

.deface-method-tag {
    font-weight: 600;
}

.deface-cta {
    height: 44px;
    padding: 0 26px;
    font-size: 15px;
    font-weight: 600;
    border-radius: 8px;
}
.table td {
    border-top: 1px solid #eee;
    padding: 0.5rem;
}
.table th {
    text-align: left;
    padding: 5px 0;
}
.table td {
    vertical-align: top;
}
.missingThumb {
    background-color: #f0f0f0;
    padding: 10px 20px;
    box-sizing: border-box;
    margin: 0;
}
.missingThumb.fail {
    background-color: #c44;
    color: white;
}
.el-form-item {
    margin-bottom: 0;
}
pre.status {
    background-color: #666;
    color: white;
    height: 125px;
    overflow: auto;
    padding: 10px;
    margin-bottom: 5px;
    border-radius: 5px;
    word-break: break-all;
    white-space: break-spaces;
}
</style>
