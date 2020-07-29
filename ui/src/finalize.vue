<template>
<div>
    <div v-if="$root.validated && $root.session.status == 'analyzed'">
        <p>Your data is ready to be converted to BIDS.</p>
        <p>Please click the finalize button below when you are ready to convert your data to BIDS.</p>
        <el-button @click="finalize" type="primary" size="small">Finalize</el-button>
    </div>
    <processStatus v-else/>

    <br>
    <br>
    <br>
    <br>
    <el-button @click="finalize" type="primary" size="small">debug</el-button>
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
                    participants: this.$root.participants,
                    participantsColumn: this.$root.participantsColumn,

                    //TODO - should I go ahead and apply series info as object default?
                    //subjects: this.$root.subjects,  //not used yet..
                    series: this.$root.series,
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
    },
}
</script>

<style scoped>
E/style>
