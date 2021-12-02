<template>
<div>
    <p v-if="errors">
        <h3>dcm2niix Errors</h3>
        <small>We were not able to convert all DICOM files due to the following issues. Please submit issue ticket at <a href="https://github.com/rordenlab/dcm2niix/issues" target="rordenlagb/dcm2niix">https://github.com/rordenlab/dcm2niix/issues</a>You can proceed with ezBIDS process with the other successfully converted data.</small>
        <pre class="errors">{{errors}}</pre>
    </p>
</div>
</template>

<script lang="ts">

import { defineComponent } from 'vue'
import { mapState } from 'vuex'
//import axios from 'axios'

export default defineComponent({
    props: [],
    async mounted() {
        const url = this.config.apihost+'/download/'+this.session._id+'/dcm2niix_error';
        const res = await fetch(url);
        this.errors = "Failed to load dcm2niix error log";
        if(res.status == 200) this.errors = await res.text();
    },
    data() {
        return {
            errors: "",
        }
    },

    computed: {
        ...mapState(['session', 'config']),
    },

    methods: {
        /*
        change(v) {
            this.$emit("update:modelValue", v);
        },
        */

        composeSampleValue(key : string) {
            const samples = this.sampleValues[key].join(', ');
            if(samples.length > 30) return samples.substring(0, 30)+" ...";
            return samples;
        },
     }
});

</script>

<style lang="scss" scoped>
pre {
    background-color: #333;
    color: var(--el-color-error);
    height: 300px;
    overflow: auto;
    padding: 10px;
    margin-top: 0;
    margin-bottom: 5px;
}
</style>
