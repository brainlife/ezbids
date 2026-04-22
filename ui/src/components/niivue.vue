<template>
    <div v-if="!openInDialog" class="niivue niivue--inline">
        <canvas v-if="path" ref="canvas" class="canvas" :style="inlineCanvasStyle" />
    </div>
    <el-dialog v-else v-model="open" :title="path" width="70%" destroy-on-close center @close="close">
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
    props: {
        path: {
            type: String,
            default: undefined,
        },
        /** When false, render the canvas inline instead of in a dialog. */
        openInDialog: {
            type: Boolean,
            default: true,
        },
        /** CSS height for the inline canvas (ignored when `openInDialog` is true). */
        height: {
            type: String,
            default: undefined,
        },
    },
    emits: ['close'],
    data() {
        return {
            open: false,
            nv: null as any,
            resizeObserver: null as ResizeObserver | null,
            resizeRaf: 0 as number,
        };
    },

    computed: {
        ...mapState(['session', 'config']),
        inlineCanvasStyle(): Record<string, string> | undefined {
            if (this.openInDialog || !this.height) return undefined;
            return {
                height: this.height,
                minHeight: this.height,
            };
        },
    },

    watch: {
        path() {
            this.load();
        },
        openInDialog() {
            this.scheduleResize();
        },
        height() {
            this.scheduleResize();
        },
    },

    mounted() {
        this.nv = new Niivue({ dragAndDropEnabled: false });
        window.addEventListener('resize', this.scheduleResize);
        this.resizeObserver = new ResizeObserver(() => this.scheduleResize());
        this.$nextTick(() => {
            const canvas = this.$refs.canvas as HTMLCanvasElement | undefined;
            if (canvas) this.resizeObserver?.observe(canvas);
        });
        this.load();
        this.scheduleResize();
    },

    activated() {
        this.scheduleResize();
    },

    beforeUnmount() {
        window.removeEventListener('resize', this.scheduleResize);
        if (this.resizeRaf) cancelAnimationFrame(this.resizeRaf);
        this.resizeObserver?.disconnect();
        this.resizeObserver = null;
        this.nv = null;
    },

    methods: {
        scheduleResize() {
            if (this.resizeRaf) cancelAnimationFrame(this.resizeRaf);
            this.resizeRaf = requestAnimationFrame(() => {
                this.resizeRaf = 0;
                this.resizeCanvas();
            });
        },

        resizeCanvas() {
            const canvas = this.$refs.canvas as HTMLCanvasElement | undefined;
            if (!canvas || !this.nv) return;
            if (typeof this.nv.resizeListener === 'function') {
                this.nv.resizeListener();
                return;
            }
            // Fallback for Niivue versions without resizeListener.
            this.nv.attachToCanvas(canvas);
        },

        load() {
            if (!this.path) {
                if (this.openInDialog) this.open = false;
                return;
            }
            axios.get(`${this.config.apihost}/download/${this.session._id}/token`).then((res) => {
                const url = `${this.config.apihost}/download/${this.session._id}/${this.path}?token=${res.data}`;
                if (this.openInDialog) this.open = true;
                this.$nextTick(() => {
                    const canvas = this.$refs.canvas as HTMLCanvasElement | undefined;
                    if (!canvas || !this.nv) return;
                    this.nv.attachToCanvas(canvas);
                    this.nv.loadVolumes([
                        {
                            url: url,
                            volume: { hdr: null, img: null },
                            colorMap: 'gray',
                            opacity: 1,
                            visible: true,
                        },
                    ]);
                    this.scheduleResize();
                });
            });
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
.niivue--inline {
    width: 100%;
    border-radius: 4px;
    background: #111;
}
.niivue--inline .canvas {
    display: block;
    width: 100%;
    height: min(58vh, 520px);
    min-height: 320px;
}
</style>
