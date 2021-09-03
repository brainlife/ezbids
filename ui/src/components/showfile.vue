<template>
<pre v-html="content" :style="{maxHeight, height}"/>
</template>

<script lang="ts">

// @ts-ignore
import Convert from 'ansi-to-html';
const convert = new Convert();

import { mapState } from 'vuex'
import { defineComponent } from 'vue'

export default defineComponent({
    props: {
        path: String,
        tall: {
            type: Boolean,
            default: false
        },
    },

    data() {
        return {
            content: "",
            maxHeight: "200px",
            height: "200px",
        }
    },

    computed: {   
        ...mapState(['session', 'config']),
    },

    mounted() {
        fetch(this.config.apihost+'/download/'+this.session._id+'/'+this.path+"?t="+new Date().getTime()).then(res=>res.text()).then(data=>{
            this.content = convert.toHtml(data);
        });

        if(this.tall) {
            this.maxHeight = "400px";
            this.height = "400px";
        }
    },
});

</script>
<style scoped>
pre {
    background-color: #333;
    color: white;
    padding: 10px;
    margin: 0;
    overflow: auto;
}
</style>
