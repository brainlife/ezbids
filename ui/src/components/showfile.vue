<template>
    <pre :style="{ maxHeight, height }" v-html="content" />
</template>

<script lang="ts">
// @ts-ignore
import Convert from 'ansi-to-html';
const convert = new Convert();

import { mapState } from 'vuex';
import { defineComponent } from 'vue';
import axios from '../axios.instance';
import { ElNotification } from 'element-plus';

export default defineComponent({
    props: {
        path: String,
        tall: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            content: '',
            maxHeight: '200px',
            height: '200px',
        };
    },

    computed: {
        ...mapState(['session', 'config']),
    },

    async mounted() {
        try {
            if (!this.path) return;
            this.content = await this.api.retrieveFileContents(this.session._id, this.path);
        } catch (e) {
            console.error(e);
            ElNotification({
                title: 'There was an error retrieve the file contents',
                message: '',
                type: 'error',
            });
        }

        if (this.tall) {
            this.maxHeight = '400px';
            this.height = '400px';
        }
    },
});
</script>
<style scoped>
pre {
    background-color: #333;
    color: white;
    margin: 0;
    overflow: auto;
    padding: 10px;
    border-radius: 5px;
}
</style>
