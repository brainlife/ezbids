<template>
    <div>
        <a style="cursor: pointer" @click="handleGoToLink">
            <img v-if="pathWithToken" style="width: 100%" :src="pathWithToken" alt="...loading" />
        </a>
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
        };
    },
    computed: {
        ...mapState(['config', 'session']),
    },
    watch: {
        path: function (oldPath, newPath) {
            this.updatePathWithToken();
        },
    },
    mounted() {
        this.updatePathWithToken();
    },
    methods: {
        handleGoToLink() {
            axios.get<string>(`${this.config.apihost}/download/${this.session._id}/token`).then((res) => {
                window.location.href = `${this.getURL(this.path)}?token=${res.data}`;
            });
        },
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
