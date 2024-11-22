<template>
    <el-dialog v-model="open" :title="path" width="70%" destroy-on-close center @close="close">
        <canvas ref="canvas" class="canvas" height="500" />
    </el-dialog>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';

// @ts-ignore
import { Niivue } from '@niivue/niivue';
import axios from '../axios.instance';

const nv = new Niivue({
    dragAndDropEnabled: false,
});

export default defineComponent({
    props: ['path'],
    emits: ['close'],
    data() {
        return {
            open: false,
        };
    },

    computed: {
        ...mapState(['session', 'config', 'ezbidsProcessingMode']),
    },

    watch: {
        path() {
            if (this.path) this.load();
        },
    },

    mounted() {
        if (this.path) this.load();
    },

    methods: {
        load() {
            if (this.ezbidsProcessingMode === 'EDGE') {
                // ANIBAL-TODO: Need to link the niivue component to some frontend generated image
                throw new Error('not yet implemented');
            } else {
                axios.get(`${this.config.apihost}/download/${this.session._id}/token`).then((res) => {
                    const url = `${this.config.apihost}/download/${this.session._id}/${this.path}?token=${res.data}`;
                    this.open = true;
                    this.$nextTick(() => {
                        nv.attachToCanvas(this.$refs.canvas);
                        nv.loadVolumes([
                            {
                                url: url,
                                volume: { hdr: null, img: null },
                                colorMap: 'gray',
                                opacity: 1,
                                visible: true,
                            },
                        ]);
                    });
                });
            }
        },

        close() {
            this.open = false;
            this.$emit('close');
        },
    },
});
</script>
<style scoped>
.datatype {
    font-size: 90%;
}
.bull {
    width: 8px;
    height: 8px;
    display: inline-block;
    border-radius: 50%;
    position: relative;
    top: 3px;
}
.canvas {
    width: 100%;
}
</style>
