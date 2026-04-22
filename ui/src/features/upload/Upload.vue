<template>
    <div>
        <div v-if="!session" class="upload-session-pending">
            <h3 style="margin-top: 0">Loading session …</h3>
            <p style="color: gray; margin-top: 8px">
                New datasets are uploaded from the dashboard. If this message persists,
                <router-link :to="{ name: 'dashboard' }">go to the dashboard</router-link>
                or open your saved session link.
            </p>
        </div>

        <div v-else>
            <div v-if="session.status == 'created'">
                <h3 style="margin-top: 0">
                    Waiting for upload
                    <font-awesome-icon icon="spinner" pulse />
                </h3>
                <p style="color: gray">
                    File transfer is handled on the dashboard. If you still see this after a long wait, return to the
                    dashboard and try again, or refresh this page.
                </p>
            </div>

            <div v-if="['preprocessing', 'uploaded'].includes(session.status)">
                <h3 v-if="session.dicomDone === undefined" style="margin-top: 0">
                    Inflating
                    <font-awesome-icon icon="spinner" pulse />
                </h3>
                <div v-else-if="session.dicomDone < session.dicomCount">
                    <h3>
                        Converting DICOMS to NIfTI
                        <font-awesome-icon icon="spinner" pulse />
                    </h3>
                    <el-progress
                        status="success"
                        :text-inside="true"
                        :stroke-width="24"
                        :percentage="parseFloat(((session.dicomDone * 100) / session.dicomCount).toFixed(1))"
                    />
                    <br />
                </div>
                <h3 v-else>
                    Analyzing
                    <font-awesome-icon icon="spinner" pulse />
                </h3>
                <pre class="status">{{ session.status_msg }}</pre>
                <small
                    >* Depending on the size of your dataset, this process might take several hours.
                    {{
                        isElectron
                            ? 'Please keep ezBIDS Desktop open while we process your data'
                            : 'You can shutdown your computer while we process your data'
                    }}
                </small>
            </div>

            <div v-if="session.status == 'failed'">
                <el-alert type="error"
                    >ezBIDS failed.. Please check the Debug logs and contact the ezBIDS team
                    (pestilli@utexas.edu).</el-alert
                >
                <br />
                <pre class="status">{{ session.status_msg }}</pre>
            </div>

            <div v-if="session.pre_finish_date">
                <div v-if="ezbids.notLoaded">
                    <h3 style="margin-top: 0">
                        Loading analysis results
                        <font-awesome-icon icon="spinner" pulse />
                    </h3>
                </div>

                <div v-if="!ezbids.notLoaded && ezbids.objects.length">
                    <h2 style="margin-top: 0">Analysis complete!</h2>
                    <AnalysisErrors />
                    <h3>
                        Object List <small>({{ ezbids.objects.length }})</small>
                    </h3>
                    <p>
                        <small
                            >We have identified the following files (objects) that can be organized into BIDS
                            structure.</small
                        >
                    </p>
                    <UploadObjectsPanel :objects="ezbids.objects" />
                </div>
                <div v-if="!ezbids.notLoaded && !ezbids.objects.length">
                    <el-alert type="error"
                        >We couldn't find any objects. Please upload data that contains at least 1 object. Contact the
                        ezBIDS team (pestilli@utexas.edu or https://github.com/brainlife/ezbids/issues) for
                        support</el-alert
                    >
                </div>
            </div>

            <br />
            <SessionDebugDownloads />
            <br />
            <br />
            <br />
        </div>
    </div>
</template>

<script>
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import SessionDebugDownloads from '@/components/SessionDebugDownloads.vue';
import UploadObjectsPanel from '@/features/upload/UploadObjectsPanel.vue';

export default defineComponent({
    components: {
        AnalysisErrors: () => import('@/components/analysisErrors.vue'),
        SessionDebugDownloads,
        UploadObjectsPanel,
    },

    computed: {
        ...mapState(['session', 'ezbids']),
        isElectron() {
            return window.env.IS_ELECTRON === 'true';
        },
    },

    methods: {
        isValid(cb) {
            //TODO..
            cb();
        },
    },
});
</script>

<style lang="scss" scoped>
.upload-session-pending {
    margin-bottom: 1rem;
}

pre.status {
    background-color: #666;
    color: white;
    height: 300px;
    overflow: auto;
    padding: 10px;
    margin-top: 0;
    margin-bottom: 0;
    border-radius: 5px;
    flex-grow: 1;
    word-break: break-all;
    white-space: break-spaces;
}
</style>
