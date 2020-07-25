<template>
<div>
    <h4>Participants Info</h4>
    <p>You can optionally store metadata/phenotypical data for each subject/participants on this datasets within your BIDS dataset.</p>
    <h5>Phenotype Columns</h5>
    <p>Define phenotypical keys stored for this study (optional).</p>
    <!--
    <el-input type="textarea"
        placeholder="participants.tsv"
        rows="10"
        v-model="participantsColumn"/>
    -->
    <div v-for="(column, key) in $root.participantsColumn" :key="key" class="columnEditor">
        <el-button type="danger" style="float: right;" icon="el-icon-delete" @click="remove(key)" size="mini"/>
        <b>{{key}}</b>
        <br>
        <br clear="both">

        <el-form label-width="100px" size="mini">
            <el-form-item label="Long Name">
                <el-input placeholder="LongName" v-model="column.LongName" size="mini"/>
            </el-form-item>
            <el-form-item label="Units">
                <el-input placeholder="Units" v-model="column.Units" size="mini"/>
            </el-form-item>
            <el-form-item label="Description">
                <el-input type="textarea" placeholder="Description" v-model="column.Description" size="mini"/>
            </el-form-item>
            <el-form-item label="Options">
                <small>TODO.. (levels)</small>
            </el-form-item>
        </el-form>
    </div>
    <p class="columnEditor" style="width: 200px;">
        <el-input placeholder="Add New Column" v-model="newcolumn" size="mini">
            <el-button @click="addNewColumn" type="primary" slot="append">Add</el-button>
        </el-input>
    </p>
    <br clear="both">

    <h5>phenotype.tsv</h5>
    <p>Enter phenotypical data associated with each participants.</p>
    <el-table :data="$root.subjects" style="width: 100%" size="mini">
        <el-table-column label="Subject" width="200">
            <template slot-scope="scope">
                {{scope.row.PatientID}}<br>
                <small>{{scope.row.sub}}</small>
            </template>
        </el-table-column>
        <el-table-column v-for="(column, key) in $root.participantsColumn" :key="key" :label="key">
            <template slot-scope="scope">
                <el-input v-model="scope.row.phenotype[key]" size="mini"/>
            </template>
            <!--
            <template slot-scope="scope">
                <el-input type="textarea"
                    placeholder="participants.json"
                    v-model="scope.row._phenotype"/>
            </template>
            -->
        </el-table-column>
    </el-table>

    <!--
                <h4>participants.json</h4>
            </el-col>
            <el-col :span="12">
                        </el-col>
        </el-row>
    </el-form>
    -->
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
    /*
    watch: {
        '$root.participants'() {
            this.participants = JSON.stringify(this.$root.participants, null, 4);
            this.participantsColumn = JSON.stringify(this.$root.participantsColumn, null, 4);
        }
    },
    */

    created() {
    },

    methods: {
        addNewColumn() {
            if(!this.newcolumn) return;
            this.$set(this.$root.participantsColumn, this.newcolumn,  {
                LongName: "",
                Description: "",
                Units: "",
                Levels: {},
            });
            this.newcolumn = "";
        },
        remove(key) {
            console.log("removing", key);
            delete this.$root.participantsColumn[key];
            this.$forceUpdate();
        },

        /*
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
        */
    },
    data() {
        return {
            //participants: "",
            //participantsColumn: "",
            newcolumn: "",
        }
    },
}
</script>

<style scoped>
.columnEditor {
background-color: #f9f9f9;
margin-bottom: 10px;
padding: 15px;
border-radius: 5px;
width: 300px;
float: left;
margin-right: 10px;
margin-bottom: 10px;
margin-top: 0;
}
</style>
