<template>
    <pre v-html="content" :style="{ maxHeight, height }" />
</template>

<script lang="ts">
// @ts-ignore
import Convert from 'ansi-to-html';
const convert = new Convert();

import { mapState } from 'vuex';
import { defineComponent } from 'vue';
import axios from '../axios.instance';

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
                const text = JSON.stringify(res.data, undefined, 4);
                this.content = convert.toHtml(text);
            })
            .catch((err) => {
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
