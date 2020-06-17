<template>
<div>
    <el-form>
        <el-row :gutter="20">
            <el-col :span="12">
                <h4>participants.json</h4>
                <el-input type="textarea"
                    placeholder="participants.json"
                    :autosize="{ minRows: 20, maxRows: 25}"
                    v-model="participants" @blur="updateParticipants"/>
            </el-col>
            <el-col :span="12">
                <h4>participants.tsv (column)</h4>
                <el-input type="textarea"
                    placeholder="participants.tsv"
                    :autosize="{ minRows: 20, maxRows: 25}"
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
    created() {
        this.participants = JSON.stringify(this.$root.participants, null, 4);
        this.participantsColumn = JSON.stringify(this.$root.participantsColumn, null, 4);
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
