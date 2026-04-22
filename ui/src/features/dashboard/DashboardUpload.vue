<template>
    <section class="dashboard-card" aria-labelledby="dashboard-cta-title">
        <div class="dashboard-cta-stack">
            <h2 id="dashboard-cta-title" class="dashboard-cta-title">Start a new conversion</h2>
            <p class="dashboard-cta-sub">
                Drag and drop a DICOM or dcm2niix folder onto the area below, or use the button to choose a folder. When
                the upload finishes, you will continue on the converter to track preprocessing progress.
            </p>

            <template v-if="!flowStarted">
                <div
                    class="dashboard-drop"
                    :class="{ 'is-dragging': dragging }"
                    @drop="dropit"
                    @dragover="dragover"
                    @dragleave="dragging = false"
                >
                    <div class="dashboard-drop-content">
                        <p class="dashboard-drop-line"><strong>Drag &amp; drop</strong> your dataset folder here</p>
                        <p class="dashboard-drop-or">or</p>
                        <el-button type="primary" size="large" @click.stop="triggerFolderPicker">
                            <el-icon class="dashboard-cta-icon"><UploadFilled /></el-icon>
                            Choose folder…
                        </el-button>
                    </div>
                    <input
                        ref="folderInput"
                        type="file"
                        class="dashboard-hidden-input"
                        webkitdirectory
                        mozdirectory
                        msdirectory
                        odirectory
                        directory
                        multiple
                        @change="selectit"
                    />
                </div>
            </template>

            <div v-else class="dashboard-upload-progress">
                <div v-if="starting && !promptSignIn">
                    <h3 class="dashboard-upload-heading">Initializing …</h3>
                </div>

                <template v-else-if="session && session.status == 'created'">
                    <h3 class="dashboard-upload-heading">
                        Uploading
                        <font-awesome-icon icon="spinner" pulse />
                    </h3>
                    <small>Please do not leave this page until all files are uploaded.</small>
                    <div v-if="failed.length > 0">
                        <el-alert type="error"
                            >Permanently failed to upload some files, please email pestilli@utexas.edu for
                            assistance</el-alert
                        >
                        <pre v-for="idx in failed" :key="idx" class="dashboard-failed-path">{{ files[idx].path }}</pre>
                    </div>
                    <p>
                        <small>Total size {{ formatNumber((total_size || 0) / (1024 * 1024)) }} MB</small>
                        <small> | {{ files.length }} Files </small>
                        <small> ({{ uploaded.length }} uploaded) </small>
                        <small v-if="ignoreCount > 0">({{ ignoreCount }} ignored) </small>
                        <el-progress
                            status="success"
                            :text-inside="true"
                            :stroke-width="24"
                            :percentage="parseFloat(((uploaded.length / files.length) * 100).toFixed(1))"
                        />
                    </p>
                    <div v-for="(batch, idx) in batches" :key="idx">
                        <div v-if="batch.status != 'done'" class="batch-stat">
                            <b style="text-transform: uppercase">{{ batch.status }}</b>
                            batch {{ (idx + 1).toString() }}. {{ batch.fileidx.length }} files
                            <span> ({{ formatNumber(batch.size / (1024 * 1024)) }} MB) </span>
                            <div style="height: 20px">
                                <el-progress
                                    v-if="batch.evt.total"
                                    :status="batchStatus(batch)"
                                    :text-inside="true"
                                    :stroke-width="15"
                                    :percentage="batchPercentage(batch)"
                                />
                            </div>
                        </div>
                    </div>
                </template>
            </div>
        </div>
    </section>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { UploadFilled } from '@element-plus/icons-vue';
import { formatNumber } from '@/filters';
import axios from '@/axios.instance';
import { ElNotification } from 'element-plus';
import { gatherDroppedFiles } from '@/features/dashboard/utils/gatherDroppedFiles';

type AugmentedFile = File & {
    path?: string;
    try?: number;
    uploading?: boolean;
    ignore?: boolean;
};

export default defineComponent({
    name: 'DashboardUpload',

    components: {
        UploadFilled,
    },

    data() {
        return {
            dragging: false,
            starting: false,

            total_size: null as number | null,
            ignoreCount: 0,
            files: [] as AugmentedFile[],
            uploaded: [] as number[],
            failed: [] as number[],
            batches: [] as {
                fileidx: number[];
                evt: { loaded?: number; total?: number };
                status: string;
                size: number;
            }[],

            doneUploading: false,

            /** True from first user selection/drop through navigation to convert (avoids a flash before session exists). */
            flowStarted: false,
        };
    },

    computed: {
        ...mapState(['session', 'config']),

        /** Mirrors Upload.vue: `promptSignIn` is referenced but not defined, so it stays undefined (falsy). */
        promptSignIn(): boolean {
            return false;
        },
    },

    methods: {
        formatNumber,

        triggerFolderPicker() {
            (this.$refs.folderInput as HTMLInputElement | undefined)?.click();
        },

        batchStatus(batch: { status: string }) {
            switch (batch.status) {
                case 'done':
                    return 'success';
                case 'failed':
                    return 'exception';
            }
            return undefined;
        },

        batchPercentage(batch: { evt: { loaded?: number; total?: number } }) {
            const total = batch.evt.total;
            if (!total) return 0;
            return parseFloat((((batch.evt.loaded || 0) / total) * 100).toFixed(1));
        },

        dragover(e: DragEvent) {
            e.preventDefault();
            this.dragging = true;
        },

        async dropit(e: DragEvent) {
            e.preventDefault();
            this.dragging = false;
            this.flowStarted = true;
            this.starting = true;
            await this.listDropFiles(e.dataTransfer?.items);
            if (!this.files.length) {
                this.starting = false;
                this.flowStarted = false;
                ElNotification({ message: 'No files found in the drop.', type: 'warning' });
                return;
            }
            this.upload();
        },

        selectit(e: Event) {
            const target = e.target as HTMLInputElement;
            const list = target.files;
            if (!list?.length) return;
            this.files = Array.from(list) as AugmentedFile[];

            setTimeout(() => {
                this.flowStarted = true;
                this.starting = true;
                for (const file of this.files) {
                    file.path = file.webkitRelativePath;
                }
                this.upload();
                target.value = '';
            }, 1000);
        },

        async listDropFiles(items: DataTransferItemList | undefined | null) {
            this.files = (await gatherDroppedFiles(items)) as AugmentedFile[];
        },

        async upload() {
            this.starting = false;
            this.doneUploading = false;

            this.total_size = 0;
            for (let i = 0; i < this.files.length; ++i) {
                this.total_size += this.files[i].size;
            }

            for (let i = 0; i < this.files.length; ++i) {
                this.files[i].try = 0;
            }

            const res = await axios.post(`${this.config.apihost}/session`, {
                headers: { 'Content-Type': 'application/json' },
            });
            this.$store.commit('setSession', await res.data);
            this.processFiles();
        },

        processFiles() {
            const data = new FormData();
            const fileidx: number[] = [];
            let batchSize = 0;

            for (let i = 0; i < this.files.length; ++i) {
                const file = this.files[i];
                if (this.uploaded.includes(i)) continue;
                if (file.uploading) continue;
                if (file.ignore) continue;
                if ((file.try || 0) > 5) {
                    if (!this.failed.includes(i)) this.failed.push(i);
                    continue;
                }
                batchSize += file.size;

                if (fileidx.length > 0 && (fileidx.length >= 500 || batchSize > 1024 * 1014 * 300)) break;

                file.uploading = true;
                fileidx.push(i);
                data.append('files', file);
                data.append('paths', file.path || '');
                data.append('mtimes', String(file.lastModified));
            }

            if (fileidx.length == 0) {
                return;
            }

            const batch = {
                fileidx,
                evt: {} as { loaded?: number; total?: number },
                status: 'uploading',
                size: batchSize,
            };
            this.batches.push(batch);

            const doSend = () => {
                axios
                    .post(this.config.apihost + '/upload-multi/' + this.session._id, data, {
                        onUploadProgress: (evt) => {
                            batch.evt = evt;
                        },
                    })
                    .then((res) => {
                        const msg = res.data;
                        if (msg == 'ok') {
                            batch.status = 'done';
                            fileidx.forEach((idx) => {
                                this.uploaded.push(idx);
                            });

                            if (this.uploaded.length + this.ignoreCount == this.files.length) {
                                this.done();
                            } else {
                                this.processFiles();
                            }
                        } else {
                            batch.status = 'failed';
                            console.error(res);
                        }
                    })
                    .catch(() => {
                        batch.status = 'failed';
                        fileidx.forEach((idx) => {
                            const f = this.files[idx];
                            f.try = (f.try || 0) + 1;
                        });
                        setTimeout(() => this.processFiles(), 1000 * 13);
                    })
                    .then(() => {
                        fileidx.forEach((idx) => {
                            this.files[idx].uploading = false;
                        });
                    });

                const uploadingBatches = this.batches.filter((b) => b.status == 'uploading');
                if (uploadingBatches.length < 4) {
                    setTimeout(() => this.processFiles(), 1000 * 3);
                }
            };

            doSend();
        },

        async done() {
            if (this.doneUploading) return;
            this.doneUploading = true;

            await axios.patch(`${this.config.apihost}/session/uploaded/${this.session._id}`, {
                headers: { 'Content-Type': 'application/json' },
            });

            const f = this.files[0];
            if (f?.path) {
                const tokens = f.path.split('/');
                const desc = tokens[0];
                this.$store.state.ezbids.datasetDescription.Name = desc;
            }

            const id = this.session._id;
            await this.$router.push({ name: 'convert', hash: '#' + id });
        },
    },
});
</script>

<style scoped lang="scss">
.dashboard-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(15, 23, 42, 0.08);
    border: 1px solid rgba(226, 232, 240, 0.9);
    padding: 1.25rem 1.5rem 1.5rem;
    min-height: 0;
}

.dashboard-cta-stack {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.dashboard-cta-title {
    margin: 0 0 1rem;
    font-size: 1.1rem;
    font-weight: 700;
    color: #2d3748;
}

.dashboard-cta-sub {
    margin: 0;
    color: #718096;
    line-height: 1.55;
    max-width: 42rem;
}

.dashboard-cta-icon {
    margin-right: 6px;
    vertical-align: middle;
}

.dashboard-hidden-input {
    position: fixed;
    left: -9999px;
    width: 1px;
    height: 1px;
    opacity: 0;
}

.dashboard-drop {
    position: relative;
    min-height: 100px;
    background: linear-gradient(145deg, #edf2f7, #e2e8f0);
    border: 2px dashed #a0aec0;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2rem 1.5rem;
    overflow: hidden;
    transition:
        background 0.2s ease,
        border-color 0.2s ease,
        box-shadow 0.2s ease;
}

.dashboard-drop.is-dragging {
    background: #cbd5e0;
    border-color: #4299e1;
    box-shadow: inset 0 0 0 2px rgba(66, 153, 225, 0.35);
}

.dashboard-drop-content {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    color: #4a5568;
}

.dashboard-drop-line {
    margin: 0;
    font-size: 1.05rem;
}

.dashboard-drop-or {
    margin: 0;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #a0aec0;
}

.dashboard-upload-progress {
    color: #2d3748;
}

.dashboard-upload-heading {
    margin-top: 0;
}

.dashboard-failed-path {
    font-size: 80%;
}

.batch-stat {
    font-family: monospace;
    font-size: 90%;
}
</style>
