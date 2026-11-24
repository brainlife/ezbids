<template>
    <div>
        <a class="qc-thumb" title="Open full size" @click="open = true">
            <img v-if="pathWithToken" style="width: 100%" :src="pathWithToken" alt="...loading" />
        </a>
        <!-- QC images open full size in a dialog over the page, like the NiiVue viewer, instead of
             replacing the app with the PNG -->
        <el-dialog v-model="open" :title="path" width="80%" top="5vh" append-to-body center>
            <div class="qc-full">
                <img v-if="pathWithToken" :src="pathWithToken" :alt="path" />
            </div>
        </el-dialog>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import axios from '../axios.instance';

export default defineComponent({
    props: {
        path: String,
    },
    data() {
        return {
            pathWithToken: '',
            open: false,
        };
    },
    computed: {
        ...mapState(['config', 'session']),
    },
    watch: {
        path: function () {
            this.updatePathWithToken();
        },
    },
    mounted() {
        this.updatePathWithToken();
    },
    methods: {
        getURL(path: string | undefined) {
            if (!path) return '';
            return `${this.config.apihost}/download/${this.session._id}/${path}`;
        },
        updatePathWithToken() {
            axios
                .get<string>(`${this.config.apihost}/download/${this.session._id}/token`)
                .then((res) => {
                    this.pathWithToken = `${this.getURL(this.path)}?token=${res.data}`;
                })
                .catch((err) => {
                    console.error(err);
                });
        },
    },
});
</script>

<style scoped>
.qc-thumb {
    cursor: zoom-in;
}
.qc-full {
    display: flex;
    justify-content: center;
    background: #0b1a24;
    border-radius: var(--panel-radius);
    padding: 8px;
}
.qc-full img {
    max-width: 100%;
    max-height: 78vh;
    object-fit: contain;
}
</style>
