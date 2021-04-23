<template>
<div v-if="$root.currentPage.id == 'finalize'" style="padding: 20px;">

    <div v-if="$root.session.status == 'analyzed' || $root.session.status == 'defaced'">
        <p>Your data is ready to be converted to BIDS!</p>
        <el-form>
            <el-form-item>
                <el-button @click="finalize" type="primary" :disable="submitting">Finalize</el-button>
            </el-form-item>
        </el-form>
    </div>

    <div v-if="$root.session.status == 'bidsing' || $root.session.status == 'finalized'">
        <h3>Converting to BIDS...</h3>
        <p><small><i>{{$root.session.status_msg}}</i></small></p>
    </div>

    <div v-if="$root.session.status == 'finished'">
        <div class="download">
            <br>
            <h3>All Done!</h3>
            <p>
            Please download the BIDS formatted data to your local computer, or send the data to other cloud resources.
            </p>
            <p>
                <el-button @click="rerun" type="success" style="float: right" size="small">Rerun Finalize Step</el-button>
                <el-button @click="download" type="primary">Download BIDS</el-button>
                <el-button @click="sendBrainlife">Send to <b>brainlife.io</b></el-button>
                <el-button @click="sendOpenneuro">Send to <b>OpenNeuro</b></el-button>
            </p>
            <p @click="downloadSubjectMapping">
                <i class="el-icon-download"></i> PatientName to Subject/Session Mapping
                <small>* may contain sensitive PHI data. Please make sure to store in a secure location.</small>
            </p>
        </div>

        <br>
        <h4>BIDS Structure</h4>
        <showfile path="tree.log"/>

        <br>
        <h4>bids-validator output</h4>
        <showfile path="validator.log"/>

    </div>

    <div v-if="$root.session.status == 'failed'">
        <p>Failed to convert to BIDS...</p>
        <el-button @click="rerun" type="success" style="float: right" size="small">Rerun Finalize Step</el-button>
        <p><small><i>{{$root.session.status_msg}}</i></small></p>
    </div>

    <!--defacing status-->
    <div v-if="defacingStats">
        <p v-for="stat in defacingStats" :key="stat.id">
            {{stat}}
        </p>
    </div><!--end of defacing status-->

    <br>
    <br>
    <h4>Debugging</h4>
    <el-collapse v-model="activeLogs">
        <el-collapse-item title="BIDS Conversion Log" name="bids.log" v-if="$root.session.status == 'finished'">
            <showfile path="bids.log" />
        </el-collapse-item>
        <el-collapse-item title="BIDS Conversion Error Log" name="bids.err" v-if="$root.session.status == 'finished'">
            <showfile path="bids.err"/>
        </el-collapse-item>
        <el-collapse-item title="Session" name="session">
            <pre class="text">{{$root.session}}</pre>
        </el-collapse-item>
        <el-collapse-item title="Files" name="files">
            <a :href="$root.apihost+'/download/'+$root.session._id+'/finalized.json'">finalized.json</a>
        </el-collapse-item>
    </el-collapse>
    <br>
    <br>

    <div class="page-action">
        <el-button type="secondary" @click="back">Back</el-button>
    </div>
</div>
</template>

<script>

import showfile from '@/components/showfile'

export default {
    components: { showfile },

    data() {
        return {
            submitting: false,

            activeLogs: [],
            //stdout: "",
            //stderr: "",

            defacingStats: null,
        }
    },

    created() {},

    methods: {

        finalize() {
            this.submitting = true;
            this.$root.finalize(err=>{
                if(err) this.$notify({ title: 'Failed', message: 'Failed to finalize:'+err});
                if(err) console.error(err);
                this.submitting = false;
            });
        },

        rerun() {
            console.log("going back to analyzed step")
            this.$root.session.status = 'analyzed';
        },

        download() {
            document.location = this.$root.apihost+'/download/'+this.$root.session._id+'/bids';
        },

        downloadSubjectMapping() {
            this.downloadMapping(JSON.stringify(this.$root.subjects, null, 2), "subject_mappings.json");
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
            window.open("../projects#ezbids:"+this.$root.session._id, "_brainlife");
        },

        sendOpenneuro() {
            alert("Sorry! This functionality is yet to be implemented!");
        },

        /*
        logChange() {
            if(this.activeLogs.includes("out")) {
                if(!this.out) fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/bids.log').then(res=>res.text()).then(data=>{
                        this.stdout = data;
                });
            } else this.out = "";

            if(this.activeLogs.includes("err")) {
                if(!this.err) fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/bids.err').then(res=>res.text()).then(data=>{
                        this.stderr = data;
                });
            } else this.err = "";
        },
        */

        back() {
            this.$root.changePage("deface");
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


