<template>
<div>
    <div style="float: right;">
        <el-button @click="finalize" size="mini">Re-Finalize</el-button>
    </div>
    
    <div v-if="$root.session.status == 'finished'">
        <p>All done!</p>
        <el-button @click="download" type="primary" size="small">Download BIDS</el-button>
        <el-button @click="sendBrainlife" size="small">Upload Data to <b>brainlife.io</b></el-button>
        <el-button @click="sendOpenneuro" size="small">Upload Data to <b>OpenNeuro</b></el-button>
        <div class="mappings">
            <p @click="downloadSubjectMapping">
                <i class="el-icon-download"></i> PatientName to Subject Mapping
            </p>
            <p @click="downloadSessionMapping">
                <i class="el-icon-download"></i> AcquisitionDate to Session Mapping
            </p>
            <small>* Patient to Subject mapping may contain sensitive PHI data. Please make sure to store in a secure location.</small>
        </div>
    </div>
    <div v-else-if="$root.session.status == 'analyzed'">
        <p>Your data is ready to be converted to BIDS.</p>
        <p>Please click the finalize button below when you are ready to convert your data to BIDS.</p>
        <el-button @click="finalize" type="primary" size="small">Finalize</el-button>
    </div>
    <processStatus v-else/>
</div>
</template>

<script>

import processStatus from '@/components/processStatus';

export default {
    components: {
        processStatus,
    },

    data() {
        return {
            finalizing: false,
            reload_t: null,
        }
    },

    created() {
    },

    methods: {
        finalize() {
            clearTimeout(this.reload_t);

            fetch(this.$root.apihost+'/session/'+this.$root.session._id+'/finalize', {
                method: "PATCH", 
                //headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    datasetDescription: this.$root.datasetDescription,
                    readme: this.$root.readme,
                    participantsColumn: this.$root.participantsColumn,
                    subjects: this.$root.subjects, //for phenotype
                    objects: this.$root.objects,
                }),
            }).then(res=>res.text()).then(status=>{
                if(status == "ok") {
                    this.$root.finalized = true;
                    this.$root.pollSession();
                } else {
                    this.$notify({ title: 'Failed', message: 'Failed to finalize:'+status});
                }
            }); 
        },

        download() {
            document.location = this.$root.apihost+'/download/'+this.$root.session._id+'/bids';
        },

        downloadSubjectMapping() {
            this.downloadMapping(JSON.stringify(this.$root.subjects, null, 2), "subject_mappings.json");
        },

        downloadSessionMapping() {
            this.downloadMapping(JSON.stringify(this.$root.sessions, null, 2), "session_mappings.json");
        },

        downloadMapping(data, name) {
            const blob = new Blob([data], { type: 'application/json' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = name;
            link.click()
            URL.revokeObjectURL(link.href)
        },

        sendBrainlife() {
            alert("TODO.. invoke API call with fetch URL like.. ezbids://"+this.$root.session._id);
        },

        sendOpenneuro() {
            alert("TODO.. invoke API call with fetch URL like.. ezbids://"+this.$root.session._id);
        },
    },
}
</script>

<style scoped>
.mappings {
    background-color: #eee;
    margin-top: 10px;
    padding: 10px;
    font-size: 85%;
}
.mappings p {
    cursor: pointer;
    color: #409EFF;
}
.mappings p:hover {
    text-decoration: underline;
}
</style>
