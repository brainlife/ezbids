<template>
<div v-if="$root.session">
    <!--show any background task going on-->

    <!--
    <div class="process-status" v-if="$root.session.status == 'failed'">
    </div>
    -->
    <!--
    <div class="process-status" v-if="$root.session.status == 'analyzed'">
        <p>Analysis complete! Please proceed to the next tab.</p>
    </div>
    <div class="process-status" v-if="$root.session.status == 'uploaded'">
        <p>Waiting to be analyzed...</p>
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
    </div>
    -->
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
.process-status {
    position: fixed;
    bottom: 0;
    width: 400px;
    right: 0;
    background-color: gray;
    padding: 10px;
    color: white;
}
</style>
