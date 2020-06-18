<template>
<div>
    <p>You can store metadata/phenotypical data for each subject/participants on this datasets within your BIDS dataset.</p>
    <p>This information allows you to perform group analysis with your data, for example.</p>
    <el-form>
        <el-row :gutter="20">
            <el-col :span="12">
                <h4>participants.json</h4>
                <el-input type="textarea"
                    placeholder="participants.json"
                    rows="22"
                    v-model="participants" @blur="updateParticipants"/>
            </el-col>
            <el-col :span="12">
                <h4>participants.tsv (column)</h4>
                <el-input type="textarea"
                    placeholder="participants.tsv"
                    rows="22"
                    v-model="participantsColumn" @blur="updateParticipantsColumn"/>
            </el-col>
        </el-row>
    </el-form>
    <!--
    <pre>{{$store.state.participants}}</pre>
    <el-button @click="increment">Increment {{$store.state}}</el-button>
    -->
</div>
</template>

<script>

//import store from './store'

export default {
    //store,
    watch: {
        '$root.participants'() {
            this.participants = JSON.stringify(this.$root.participants, null, 4);
            this.participantsColumn = JSON.stringify(this.$root.participantsColumn, null, 4);
        }
    },

    created() {
    },

    methods: {
        updateParticipants() {
            try {
                this.$root.participants = JSON.parse(this.participants);
            } catch (err) {
                const h = this.$createElement;
                this.$notify({
                    title: 'Parse Error',
                    message: h('i', { style: 'color: red' }, err.toString())
                });
            }
        },
        updateParticipantsColumn() {
            try {
                this.$root.participantsColumn = JSON.parse(this.participantsColumn);
            } catch (err) {
                const h = this.$createElement;
                this.$notify({
                    title: 'Parse Error',
                    message: h('i', { style: 'color: red' }, err.toString())
                });
            }
        },
    },
    data() {
        return {
            participants: "",
            participantsColumn: "",
        }
    },
}
</script>

<style scoped>
</style>
