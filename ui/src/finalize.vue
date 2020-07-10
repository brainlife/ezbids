<template>
<div>
    <div v-if="!finalizing">
        <p>Your data is ready to be converted to BIDS.</p>
        <p>Please click the finalize button below when you are ready to convert your data to BIDS.</p>
        <el-button @click="finalize" type="primary">Finalize</el-button>
    </div>
    <div v-if="finalizing">
        <!--<el-button @click="finalize" type="primary">agagin</el-button>-->
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

    </div>
</div>
</template>

<script>

export default {
    computed: {
    },

    components: {
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
            this.finalizing = true;
            fetch(this.$root.apihost+'/session/'+this.$root.session._id+'/finalize', {
                method: "PATCH", 
                //headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    datasetDescription: this.$root.datasetDescription,
                    readme: this.$root.readme,
                    participants: this.$root.participants,
                    participantsColumn: this.$root.participantsColumn,
                    objects: this.$root.objects,
                }),
            }).then(res=>res.text()).then(status=>{
                if(status == "ok") {
                    this.$root.finalized = true;
                    this.pollSession();
                } else {
                    this.$notify({ title: 'Failed', message: 'Failed to finalize:'+status});
                }
            }); 
        },

        async pollSession() {
            console.log("polling..", this.$root.session.status);
            const res = await fetch(this.$root.apihost+'/session/'+this.$root.session._id, {
                method: "GET",
                headers: { 'Content-Type': 'application/json' },
            });
            this.$root.session = await res.json();

            switch(this.$root.session.status) {
            case "finalized":
            case "bidsing":
                this.reload_t = setTimeout(()=>{
                    console.log("will reload");
                    this.pollSession();
                }, 1000);
                break;

            case "finished":
                this.$root.finished = true;
                break;

            case "failed":
                break;
            }
        },
    },
}
</script>

<style scoped>
E/style>
