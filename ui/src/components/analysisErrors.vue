<template>
<div class="analysisError" v-if="errors">
    <h3>dcm2niix Errors</h3>
    <p>
        We were not able to convert all DICOM files due to the following issues. Please submit an issue at <a href="https://github.com/rordenlab/dcm2niix/issues" target="rordenlagb/dcm2niix">https://github.com/rordenlab/dcm2niix/issues</a>. You can send your input DICOM files to dcm2niix team via a shared Google Drive folder.
    </p>
    <pre class="errors">{{errors}}</pre>
    <p>
        You can proceed with ezBIDS process with the other successfully converted data.
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
.analysisError {
    border: 3px solid var(--el-color-error);
    padding: 10px;
    border-radius: 5px;
    color: var(--el-color-error);
    background-color: #fee;
}
pre {
    background-color: #333;
    color: white;
    margin-left: -10px;
    margin-right: -10px;
    max-height: 300px;
    overflow: auto;
    padding: 10px;
    margin-top: 0;
    margin-bottom: 5px;
}
h3 {
}
p {
margin-bottom: 10px;
}
</style>
