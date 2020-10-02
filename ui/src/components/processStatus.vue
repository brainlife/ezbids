<template>
<div v-if="$root.session">
    <div v-if="$root.session.status == 'uploaded'">
        <p>Waiting to be analyzed...</p>
    </div>
    <div v-if="$root.session.status == 'preprocessing'">
        <p v-if="$root.session.dicomDone && $root.session.dicomDone < $root.session.dicomCount">
            Converting dicoms to nifti ...
            <el-progress status="success" 
                :text-inside="true" 
                :stroke-width="24" 
                :percentage="($root.session.dicomDone / $root.session.dicomCount)*100"/>
        </p>
        <p v-else>Analyzing...</p>
        <p><small><i>{{$root.session.status_msg}}</i></small></p>
    </div>
    <div v-if="$root.session.status == 'analyzed'">
        <p>Analysis complete! Please proceed to the next tab.</p>
        <p>
            <!--<el-button type="primary" @click="$root.page = 'description'" size="small">Next</el-button>-->
        </p>
    </div>
    <div v-if="$root.session.status == 'failed'">
        <p>ezBIDS failed.. Please check the log and/or contact ezBIDS team.</p>
        <p>{{$root.session.status_msg}}</p>
    </div>
    <div v-if="$root.session.status == 'finalized'">
        <p>Waiting to be converted to BIDS...</p>
    </div>
    <div v-if="$root.session.status == 'bidsing'">
        <p>Being Converted to BIDS...</p>
    </div>
    <div v-if="$root.session.status == 'finished'">
        <p>All done! Please proceed to the next tab.</p>
    </div>

    <div v-if="$root.session.status != 'uploaded'">
        <br>
        <h4>Debugging</h4>
        <el-collapse v-model="activeLogs" @change="logChange">
            <el-collapse-item title="Preprocess/Analyzer Log" name="out">
                <pre class="text">{{out}}</pre>
            </el-collapse-item>
            <el-collapse-item title="Preprocess/Analyzer Error Log" name="err">
                <pre class="text">{{err}}</pre>
            </el-collapse-item>
            <el-collapse-item title="BIDS Conversion Log" name="bidsOut" v-if="$root.finalized">
                <pre class="text">{{bidsOut}}</pre>
            </el-collapse-item>
            <el-collapse-item title="BIDS Conversion Error Log" name="bidsErr" v-if="$root.finalized">
                <pre class="text">{{bidsErr}}</pre>
            </el-collapse-item>
            <el-collapse-item title="Objects" name="list" v-if="$root.analyzed">
                <pre class="text">{{list}}</pre>
                <div>
                    <h3>Subjects</h3>
                    <pre>{{this.$root.subjects}}</pre>
                    <h3>Sessions</h3>
                    <pre>{{this.$root.sessions}}</pre>
                    <h3>Series</h3>
                    <pre>{{this.$root.series}}</pre>
                    <h3>Objects</h3>
                    <pre>{{this.$root.objects}}</pre>
                </div>
            </el-collapse-item>
        </el-collapse>
    </div>
</div>
</template>

<script>

//import store from './store'
import Vue from 'vue'

export default {
    //store,
    components: {
    },
    data() {
        return {
            err: "",
            out: "",
            list: "",
            bidsErr: "",
            bidsOut: "",
            activeLogs: [],
            config: Vue.config,
        }
    },
    created() {
    },

    methods: {
        logChange() {
            if(this.activeLogs.includes("out")) {
                fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/preprocess.log').then(res=>res.text()).then(data=>{
                        this.out = data;
                });
            } else this.out = "";

            if(this.activeLogs.includes("err")) {
                fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/preprocess.err').then(res=>res.text()).then(data=>{
                        this.err= data;
                });
            } else this.err = "";

            if(this.activeLogs.includes("list")) {
                fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/list').then(res=>res.text()).then(data=>{
                        this.list = data;
                });
            } else this.list = "";

            if(this.activeLogs.includes("bidsOut")) {
                fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/bids.log').then(res=>res.text()).then(data=>{
                        this.bidsOut = data;
                });
            } else this.out = "";

            if(this.activeLogs.includes("bidsErr")) {
                fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/bids.err').then(res=>res.text()).then(data=>{
                        this.bidsErr = data;
                });
            } else this.out = "";

        },
    },
}
</script>

<style scoped>
pre.text {
    background-color: #f0f0f0;
    border-radius: 10px;
    height: 450px;
    padding: 10px;
    overflow: auto;
}
</style>
