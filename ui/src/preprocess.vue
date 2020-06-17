<template>
<div>
    <div v-if="session">
            <h3>{{this.$root.session}}</h3>
            <b>{{session.status}}</b>
            <span v-if="session.status == 'uploaded'">Waiting to be processed..</span>
            <p>{{session.status_msg}}</p>
            <!--
            <p>
                debug..
                <a :href="$root.apihost+'/session/processlog/'+this.$root.session">process.log</a>
                <a :href="$root.apihost+'/session/processerr/'+this.$root.session">process.err</a>
                <a :href="$root.apihost+'/session/list/'+this.$root.session">list</a>
            </p>
            {{session}}
            -->
    </div>
</div>
</template>

<script>

//import store from './store'

export default {
    //store,
    components: {
    },
    data() {
        return {
            session: null, //to-be-loaded
            reload_int: null,
        }
    },
    created() {
        this.reload_int = setInterval(this.load_session, 1000);
        this.load_session();
    },
    destroyed() {
        clearInterval(this.reload_int);
    },

    methods: {
        /*
        increment() {
            this.$store.commit('increment')
            console.log(this.$store.state.count);
        }
        */
        async load_session() {
            const res = await fetch(this.$root.apihost+'/session/'+this.$root.session, {
                method: "GET",
                headers: { 'Content-Type': 'application/json' },
            });
            this.session = await res.json();

            //DEBUG don't reload anymore if we reached the final state
            //if(this.session.pre_finish_date) clearInterval(this.reload_int);
        },
    },
}
</script>

<style scoped>
</style>
