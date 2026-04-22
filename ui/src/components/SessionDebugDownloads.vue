<template>
    <div style="width: 100%">
        <el-collapse :class="wrapperClass">
            <el-collapse-item :title="collapseTitle">
                <ul class="session-debug-downloads__list">
                    <el-button style="width: 168px" type="warning" size="mini" @click="downloadFile('preprocess.log')"
                        >preprocess.log</el-button
                    >
                    <el-button type="warning" size="mini" @click="downloadFile('preprocess.err')"
                        >preprocess.err</el-button
                    >
                    <el-button type="warning" size="mini" @click="downloadFile('dcm2niix_error')"
                        >dcm2niix_error</el-button
                    >
                    <el-button type="warning" size="mini" @click="downloadFile('pet2bids_error')"
                        >pet2bids_error</el-button
                    >
                    <el-button type="warning" size="mini" @click="downloadFile('list')">data list</el-button>
                    <el-button type="warning" size="mini" @click="downloadFile('unprocessed_list')"
                        >unprocessed_list</el-button
                    >
                    <el-button type="warning" size="mini" @click="downloadFile('ezBIDS_core.json')"
                        >ezBIDS_core.json</el-button
                    >
                </ul>

                <el-button v-if="showDumpButton" type="info" style="width: 168px" size="mini" @click="dumpState"
                    >Dump state</el-button
                >
            </el-collapse-item>
        </el-collapse>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import axios from '../axios.instance';
import { ElNotification } from 'element-plus';

export default defineComponent({
    name: 'SessionDebugDownloads',

    props: {
        collapseTitle: {
            type: String,
            default: 'Debug (Download)',
        },
        /** Extra class on the root `el-collapse` (e.g. layout spacing). */
        wrapperClass: {
            type: String,
            default: '',
        },
        showDumpButton: {
            type: Boolean,
            default: true,
        },
    },

    computed: {
        ...mapState(['session', 'config', 'ezbids']),
    },

    methods: {
        async buildDownloadUrl(fileName: string): Promise<string> {
            if (!this.session?._id) throw new Error('No session id');
            const res = await axios.get(`${this.config.apihost}/download/${this.session._id}/token`);
            const shortLivedJWT = res.data;
            const pathInUrl = String(fileName)
                .split('/')
                .map((seg) => encodeURIComponent(seg))
                .join('/');
            return `${this.config.apihost}/download/${this.session._id}/${pathInUrl}?token=${shortLivedJWT}`;
        },

        async downloadFile(fileName: string) {
            if (!fileName || !this.session?._id) return;
            try {
                const url = await this.buildDownloadUrl(fileName);
                const dl = await axios.get(url, { responseType: 'blob' });
                const blob = dl.data;
                const baseName = fileName.includes('/') ? fileName.split('/').pop() : fileName;
                const objectUrl = URL.createObjectURL(blob);
                try {
                    const link = document.createElement('a');
                    link.href = objectUrl;
                    link.download = baseName || 'download';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } finally {
                    URL.revokeObjectURL(objectUrl);
                }
            } catch (e) {
                console.error(e);
                ElNotification({
                    message: 'there was an error downloading the file',
                    type: 'error',
                });
            }
        },

        dumpState() {
            const element = document.createElement('a');
            element.setAttribute(
                'href',
                'data:text/plain;charset=utf-8,' + encodeURIComponent(JSON.stringify(this.ezbids, null, 4))
            );
            element.setAttribute('download', 'root.json');
            element.style.display = 'none';
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
        },
    },
});
</script>

<style scoped lang="scss">
.session-debug-downloads__list {
    list-style: none;
    padding-left: 0;
}
</style>
