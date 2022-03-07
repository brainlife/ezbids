<template>
<el-dialog v-model="open" :title="path" width="70%" destroy-on-close center @close="close">
    <canvas ref="canvas" class="canvas" height="500"/>
</el-dialog>
</template>

<script lang="ts">

import { defineComponent } from 'vue'
import { mapGetters, } from 'vuex'

// @ts-ignore
import { Niivue } from '@niivue/niivue'

const nv = new Niivue({
    dragAndDropEnabled: false
});

export default defineComponent({
    props: [ 'path' ],
    data() {
        return {
            open: false,
        }
    },

    mounted() {
        if(this.path) this.load();
    },

    watch: {
        path() {
            if(this.path) this.load();
        }
    },

    computed: {
        ...mapGetters(['getURL']),
    },

    methods: {
        load() {
            console.log("loading niivuew", this.path);
            this.open = true;
            this.$nextTick(()=>{
                console.log("canvas", this.$refs.canvas)
                nv.attachToCanvas(this.$refs.canvas);
                nv.loadVolumes([{
                    url: this.getURL(this.path),
                    volume: {hdr: null, img: null},
                    colorMap: "gray",
                    opacity: 1,
                    visible: true,
                }]);
            })
        },

        close() {
            this.open = false;
            this.$emit("close");
        }

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
.canvas{
    width: 100%;
}
</style>
