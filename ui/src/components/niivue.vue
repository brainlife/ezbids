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

export default defineComponent({
    props: ['path'],
    emits: ['close'],
    data() {
        return {
            open: false,
            //per-component instance; el-dialog uses destroy-on-close so the prior
            //canvas is removed each time, which would orphan a shared WebGL context
            nv: null as any,
        };
    },

    computed: {
        ...mapState(['session', 'config']),
    },

    watch: {
        path() {
            if (this.path) this.load();
        },
    },

    mounted() {
        this.nv = new Niivue({ dragAndDropEnabled: false });
        if (this.path) this.load();
    },

    beforeUnmount() {
        if (this.nv) this.nv.closeAllVolumes();
    },

    methods: {
        load() {
            axios.get(`${this.config.apihost}/download/${this.session._id}/token`).then((res) => {
                const url = `${this.config.apihost}/download/${this.session._id}/${this.path}?token=${res.data}`;
                this.open = true;
                this.$nextTick(() => {
                    this.nv.attachToCanvas(this.$refs.canvas);
                    this.nv.loadVolumes([
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
        },

        close() {
            if (this.nv) this.nv.closeAllVolumes();
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
