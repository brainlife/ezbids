<template>
    <div v-if="errors" class="analysisError">
        <h3>dcm2niix Errors</h3>
        <p>
            We encountered a dcm2niix error (or errors) that may require attention. If this should be addressed, please
            submit an issue at
            <a href="https://github.com/rordenlab/dcm2niix/issues" target="rordenlagb/dcm2niix"
                >https://github.com/rordenlab/dcm2niix/issues</a
            >. Copy the information below for each unique error message (beginning with the "+" key) and paste into in
            the body of your dcm2niix issue, if you choose to submit an issue. You can send your error DICOM
            files/folders to the dcm2niix team via a shared Google Drive folder.
        </p>
        <pre class="errors">{{ errors }}</pre>
        <p>You may continue ezBIDS with the other successfully converted data if you wish.</p>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';

export default defineComponent({
    props: [],
    data() {
        return {
            errors: '',
        };
    },

    computed: {
        ...mapState(['session', 'config']),
    },

    async mounted() {
        const errors = await this.api.getDCM2NIIXError(this.session._id);
        if (errors) this.errors = errors;
    },

    methods: {
        /*
        change(v) {
            this.$emit("update:modelValue", v);
        },
        */
        /*
        composeSampleValue(key : string) {
            const samples = this.sampleValues[key].join(', ');
            if(samples.length > 30) return samples.substring(0, 30)+" ...";
            return samples;
        },
        */
    },
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
