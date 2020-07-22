<template>
<div>
    <div v-if="$root.session">
        <el-button type="secondary" @click="$root.reset()" size="small" style="float: right;">Re-upload</el-button>

        <!--<small>{{this.$root.session}}</small>-->
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
            <p>Analysis has failed.. Please check the log and/or contact ezBIDS team.</p>
            <p>{{$root.session.status_msg}}</p>
        </div>
        <div v-if="$root.session.status == 'finalized'">
            <p>Waiting to be converted to BIDS...</p>
        </div>
        <div v-if="$root.session.status == 'bidsing'">
            <p>Being Converted to BIDS...</p>
        </div>
        <div v-if="$root.session.status == 'finished'">
            <p>All done!</p>
        </div>


        <el-collapse v-model="activeLogs" @change="logChange">
            <el-collapse-item title="Log" name="out">
                <pre class="text">{{out}}</pre>
            </el-collapse-item>
            <el-collapse-item title="Error Log" name="err">
                <pre class="text">{{err}}</pre>
            </el-collapse-item>
            <el-collapse-item title="Objects" name="list" v-if="$root.session.status == 'analyzed'">
                <pre class="text">{{list}}</pre>
                <!--<div v-if="config.debug">-->
                <div>
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
            activeLogs: [],
            config: Vue.config,
        }
    },
    created() {
    },

    methods: {
        logChange() {
            if(this.activeLogs.includes("out")) {
                if(!this.out) fetch(this.$root.apihost+'/session/'+this.$root.session._id+'/log').then(res=>res.text()).then(data=>{
                        this.out = data;
                });
            } else this.out = "";

            if(this.activeLogs.includes("err")) {
                if(!this.err) fetch(this.$root.apihost+'/session/'+this.$root.session._id+'/error').then(res=>res.text()).then(data=>{
                        this.err= data;
                });
            } else this.err = "";

            if(this.activeLogs.includes("list")) {
                if(!this.list) fetch(this.$root.apihost+'/session/'+this.$root.session._id+'/list').then(res=>res.text()).then(data=>{
                        this.list = data;
                });
            } else this.list = "";
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
