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
/**
 * ANIBAL-TODO: We will need to update this component to show images generated on the FE
 * instead of linking the image to a BE path
 */
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
        ...mapState(['config', 'session', 'ezbidsProcessingMode']),
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
            if (!this.path) return;
            this.api.downloadFile(this.session._id, this.path);
        },
        getURL(path: string | undefined) {
            if (!path) return '';
            return `${this.config.apihost}/download/${this.session._id}/${path}`;
        },
        updatePathWithToken() {
            if (this.ezbidsProcessingMode === 'EDGE') {
                // ANIBAL-TODO: Need to have a link that points to some frontend generated image
                throw new Error('not yet implemented');
            } else {
                axios
                    .get<string>(`${this.config.apihost}/download/${this.session._id}/token`)
                    .then((res) => {
                        this.pathWithToken = `${this.getURL(this.path)}?token=${res.data}`;
                    })
                    .catch((err) => {
                        console.error(err);
                    });
            }
        },
    },
});
</script>
