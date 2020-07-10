<template>
<div>
    <p>You can optionally store metadata/phenotypical data for each subject/participants on this datasets within your BIDS dataset.</p>
    <p>This information allows you to perform group analysis with your data, for example.</p>
    <h4>Phenotype Columns</h4>
    <p>Define phenotypical keys stored for this study (optional).</p>
    <!--
    <el-input type="textarea"
        placeholder="participants.tsv"
        rows="10"
        v-model="participantsColumn"/>
    -->
    <div v-for="(column, key) in $root.participantsColumn" :key="key" class="columnEditor">
        <el-row :gutter="10">
        <el-col :span="3">
            {{key}}
        </el-col>
        <el-col :span="19">
            <el-input placeholder="LongName" v-model="column.LongName" size="mini">
                <template slot="prepend">Long Name</template>
            </el-input>
            <el-input placeholder="Units" v-model="column.Units" size="mini">
                <template slot="prepend">Units</template>
            </el-input>
            <el-input type="textarea" placeholder="Description" v-model="column.Description" size="mini"/>
            <small>TODO.. levels</small>
        </el-col>
        <el-col :span="2">
            <el-button type="danger" icon="el-icon-delete" @click="remove(key)" size="mini"/>
        </el-col>
        </el-row>
    </div>
    <p class="columnEditor">
        <el-input placeholder="Add New Column" v-model="newcolumn" size="mini">
            <el-button @click="addNewColumn" slot="append">Add</el-button>
        </el-input>
    </p>

    <h4>phenotype.tsv</h4>
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
background-color: #eee;
margin-bottom: 10px;
padding: 15px;
border-radius: 5px;
}
</style>
