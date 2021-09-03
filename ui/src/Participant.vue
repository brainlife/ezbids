<template>
<div style="padding: 20px">
    <p>You can optionally store metadata/phenotypical data for each subject/participants on this datasets within your BIDS dataset.</p>
    <h5>Phenotype Columns</h5>
    <p>Define phenotypical keys stored for this study (optional).</p>
    <el-form>
        <div v-for="(column, key) in ezbids.participantsColumn" :key="key" class="columnEditor">
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
                <template #append>
                    <el-button @click="addNewColumn" type="primary">Add</el-button>
                </template>
            </el-input>
        </p>

    </el-form>

    <br clear="both">

    <h5>phenotype.tsv</h5>
    <p>Enter phenotypical data associated with each participants.</p>
    <div style="width: 100%">
        <el-table :data="ezbids.subjects" size="mini">
            <el-table-column label="subject" width="200">
                <template #default="scope">
                    {{scope.row.subject}} <small>({{scope.row.PatientID||scope.row.PatientName}})</small>
                </template>
            </el-table-column>
            <el-table-column v-for="(column, key) in ezbids.participantsColumn" :key="key" :label="key">
                <template #default="scope">
                    <el-input v-model="scope.row.phenotype[key]" size="mini"/>
                </template>
            </el-table-column>
        </el-table>
    </div>

    <!--
    <br>
    <br>
    <br>
    <br>
    <div class="page-action">
        <el-button @click="back">Back</el-button>
        <el-button type="primary" @click="next" style="float: right;">Next</el-button>
    </div>
    <br>
    -->
    
    <!--
    <pre>{{ezbids.participantsColumn}}</pre>
    -->
</div>
</template>

<script lang="ts">

import { mapState } from 'vuex'
import { defineComponent } from 'vue'
import { t } from 'element-plus/lib/locale';

export default defineComponent({
    data() {
        return {
            newcolumn: "",
        }
    },

    computed: {
        ...mapState(['ezbids', 'config']),
    },

    /*
    watch: {
        '$root.currentPage'(v) {
            if(v.id == 'participant') {
                this.validate();
            }
        },
    },
    */

    methods: {
        addNewColumn() {
            if(!this.newcolumn) return;
            /*
            this.$set(this.ezbids.participantsColumn, this.newcolumn,  {
                LongName: "",
                Description: "",
                Units: "",
                Levels: {},
            });
            */
           this.ezbids.participantsColumn[this.newcolumn] = {
                LongName: "",
                Description: "",
                Units: "",
                Levels: {},   
           }
            this.newcolumn = "";
        },

        remove(key: string|number|symbol) {
            console.log("removing", key);
            delete this.ezbids.participantsColumn[key];
            //this.$forceUpdate();
        },

        //TODO
        validate() {
            console.log("todo - validate participant");
        },

        isValid(cb: (v?: string)=>void) {
            this.validate();
            //TODO
            cb();
        }

        /*
        next() {
            if(this.validate()) {
                this.$root.changePage("series");
            } else {
                alert('Please correct all issues');
                return false;
            }
        },

        back() {
            this.$root.changePage("subject");
        },
        */
    },
});
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
