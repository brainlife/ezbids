<template>
<div v-if="$root.currentPage.id == 'finalize'" style="padding: 20px;">
    <!--
    <div style="float: right;">
        <el-button @click="finalize" size="mini">Re-Finalize</el-button>
    </div>
    -->
    <div v-if="$root.session && $root.session.status == 'finalized'">
        <p>Being Converted to BIDS...</p>
        <p><small><i>{{$root.session.status_msg}}</i></small></p>
    </div>
    <div v-if="$root.session && $root.session.status == 'finished'">
        <div class="download">
            <br>
            <h3>Congratulations!</h3>
            <p>
                <el-button @click="download" type="primary">Download BIDS</el-button>
            </p>
            <br>
            <p @click="downloadSubjectMapping">
                <i class="el-icon-download"></i> PatientName to Subject Mapping
            </p>
            <p @click="downloadSessionMapping">
                <i class="el-icon-download"></i> AcquisitionDate to Session Mapping
            </p>
            <small>* Patient to Subject mapping may contain sensitive PHI data. Please make sure to store in a secure location.</small>
        </div>
        <p>
            <el-button @click="sendBrainlife" size="small">TODO.. Upload Data to <b>brainlife.io</b></el-button>
            <el-button @click="sendOpenneuro" size="small">TODO.. Upload Data to <b>OpenNeuro</b></el-button>
        </p>
    </div>
    <!---
    <div v-else-if="$root.session.status == 'analyzed'">
        <p>Your data is ready to be converted to BIDS.</p>
        <p>Please click the finalize button below when you are ready to convert your data to BIDS.</p>
        <el-button @click="finalize" type="primary" size="small">Finalize</el-button>
    </div>
    -->
    <div class="page-action">
        <el-button type="secondary" @click="back">Back</el-button>
    </div>
</div>
</template>

<script>

//import processStatus from '@/components/processStatus';

export default {
    components: {
        //processStatus,
    },

    data() {
        return {
            //finalizing: false,
            //reload_t: null,
        }
    },

    created() {
    },

    methods: {

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

        back() {
            this.$root.changePage("object");
        },
    },
}
</script>

<style scoped>
.download {
    border-radius: 10px;
    background-color: #eee;
    padding: 20px;
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
