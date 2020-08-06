<template>
<div>
    <div v-if="$root.validated && $root.session.status == 'finished'">
        <p>All done!</p>
        <el-button @click="download" type="primary" size="small">Download</el-button>
        <el-button @click="sendBrainlife" size="small">Upload Data to <b>brainlife.io</b></el-button>
        <el-button @click="sendOpenneuro" size="small">Upload Data to <b>OpenNeuro</b></el-button>
        <el-button @click="finalize" size="small">Re-Finalize</el-button>
    </div>
    <div v-else-if="$root.validated && $root.session.status == 'analyzed'">
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

            //apply mappings
            let objects = JSON.parse(JSON.stringify(this.$root.objects));
            objects.forEach(o=>{
                if(!o.entities.sub) {
                    const subject = this.$root.findSubject(o);
                    o.entities.sub = subject.sub;
                } 
                if(!o.entities.ses) {
                    const session = this.$root.findSession(o);
                    o.entities.ses = session.ses;
                }

                const series = this.$root.findSeries(o);
                for(let k in o.entities) {
                    if(!o.entities[k] && series.entities[k]) {
                        o.entities[k] = series.entities[k];
                    }
                }
            });

            fetch(this.$root.apihost+'/session/'+this.$root.session._id+'/finalize', {
                method: "PATCH", 
                //headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    datasetDescription: this.$root.datasetDescription,
                    readme: this.$root.readme,
                    participants: this.$root.participants,
                    participantsColumn: this.$root.participantsColumn,
                    objects,
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

        sendBrainlife() {
            alert("ezbids://"+this.$root.session._id);
        },

        sendOpenneuro() {
            alert("ezbids://"+this.$root.session._id);
        },
    },
}
</script>

<style scoped>
</style>
