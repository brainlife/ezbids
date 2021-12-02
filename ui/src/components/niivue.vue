<template>
<canvas ref="canvas" height="480" width="640"/>
</template>

<script lang="ts">

import { defineComponent } from 'vue'

// @ts-ignore
import { Niivue } from '@niivue/niivue'

export default defineComponent({
    props: [ 'url' ],
    data() {
        return {
        }
    },

    mounted() {
        const nv = new Niivue();
        console.dir(nv);
        nv.attachToCanvas(this.$refs.canvas);
        const vol = {
          url: this.url,
          volume: {hdr: null, img: null},
          colorMap: "gray",
          opacity: 80,
          visible: true,
        };
        console.log("loading volume", vol);
        nv.loadVolumes([vol]);
    },
    method: {
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
</style>
