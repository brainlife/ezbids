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

    mounted() {
        axios
            .get(`${this.config.apihost}/download/${this.session._id}/token`)
            .then((res) => {
                const shortLivedJWT = res.data;
                return axios.get(
                    `${this.config.apihost}/download/${this.session._id}/${this.path}?token=${shortLivedJWT}`
                );
            })
            .then((res) => {
                if (typeof res.data === 'string') {
                    this.content = convert.toHtml(res.data);
                } else {
                    this.content = convert.toHtml(JSON.stringify(res.data, undefined, 4));
                }
            })
            .catch((err) => {
                ElNotification({
                    title: 'There was an error retrieving the file contents',
                    message: '',
                    type: 'error',
                });
                console.error(err);
            });

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
