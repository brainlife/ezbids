<template>
<div>
    <!--
    <pre>{{$store.state.readme}}</pre>
    <el-button @click="increment">Increment {{$store.state}}</el-button>
    -->
    <el-form>
        <el-form-item label="README (.md)">
            <el-input type="textarea" 
                :autosize="{ minRows: 10, maxRows: 20}"
                v-model="README"/>
        </el-form-item>
    </el-form>
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
        }
    },
    created() {
    },
    methods: {
        /*
        increment() {
            this.$store.commit('increment')
            console.log(this.$store.state.count);
        }
        */
    },
    computed: {
        /*
        dataset_description() {
            return this.$store.state.dataset_description
        },
        */

        README: {
            get() {
                return this.$store.state.README;
            },
            set(v) {
                return this.$store.commit('updateREADME', v);
            },
        },
    }
}
</script>

<style scoped>
</style>
