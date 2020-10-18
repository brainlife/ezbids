<template>
<div v-if="$root.currentPage.id == 'participant'">
    <h4>Participants Info</h4>
    <p>You can optionally store metadata/phenotypical data for each subject/participants on this datasets within your BIDS dataset.</p>
    <h5>Phenotype Columns</h5>
    <p>Define phenotypical keys stored for this study (optional).</p>
    <el-form>
        <div v-for="(column, key) in $root.participantsColumn" :key="key" class="columnEditor">
            <el-button type="danger" style="float: right;" icon="el-icon-delete" @click="remove(key)" size="mini"/>
            <b>{{key}}</b>
            <br>
            <br clear="both">
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
        </div>
        <p class="columnEditor" style="width: 200px;">
            <el-input placeholder="Add New Column" v-model="newcolumn" size="mini">
                <el-button @click="addNewColumn" type="primary" slot="append">Add</el-button>
            </el-input>
        </p>

    </el-form>

    <br clear="both">

    <h5>phenotype.tsv</h5>
    <p>Enter phenotypical data associated with each participants.</p>
    <el-table :data="$root.subjects" style="width: 100%" size="mini">
        <el-table-column label="participant_id" width="200">
            <template slot-scope="scope">
                {{scope.row.PatientID}}<br>
                <small>{{scope.row.sub}}</small>
            </template>
        </el-table-column>
        <el-table-column v-for="(column, key) in $root.participantsColumn" :key="key" :label="key">
            <template slot-scope="scope">
                <el-input v-model="scope.row.phenotype[key]" size="mini"/>
            </template>
        </el-table-column>
    </el-table>

    <br>
    <br>
    <br>
    <br>
    <div class="page-action">
        <el-button type="primary" @click="next">Next</el-button>
        <el-button @click="back">Back</el-button>
    </div>
    <br>
</div>
</template>

<script>
export default {
    data() {
        return {
            newcolumn: "",
        }
    },

    watch: {
        '$root.currentPage'(v) {
            if(v.id == 'participant') {
                this.validate();
            }
        },
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

        validate() {
            console.log("todo - validate participant");
            return true;
        },

        next() {
            if(this.validate()) {
                this.$root.changePage("object");
            } else {
                alert('Please correct all issues');
                return false;
            }
        },

        back() {
            this.$root.changePage("series");
        },
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
