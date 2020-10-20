<template>
<div v-if="$root.currentPage.id == 'subject'" style="padding: 20px;">
    <h4>Patient / Subject Mappings</h4>
    <p>Decide how you want to map DICOM PatientID to BIDS Subject ID. You can download the mapping table later.</p>
    <el-dropdown @command="resetSubjects" style="float: right;" size="small">
        <el-button type="primary" size="small">
            Reset Mapping <i class="el-icon-arrow-down el-icon--right"></i>
        </el-button>
        <el-dropdown-menu slot="dropdown">
            <el-dropdown-item command="pname">Use PatientName</el-dropdown-item>
            <el-dropdown-item command="pid">Use PatientID</el-dropdown-item>
            <el-dropdown-item command="num">Numerical (1,2,3..)</el-dropdown-item>
        </el-dropdown-menu>
    </el-dropdown>
    <el-table :data="$root.subjects" style="width: 100%" size="mini" class="table-align-top">
        <el-table-column label="DICOM Patient" width="300px">
            <template slot-scope="scope">
                <i class="el-icon-right" style="float: right; font-size: 150%; font-weight: bold;"/>
                <div>
                    <b>PatientID</b> {{scope.row.PatientID}}<br>
                    <b>PatientName</b> {{scope.row.PatientName}}<br>
                    <b>PatientBirthDate</b> {{scope.row.PatientBirthDate}}<br>
                </div>
            </template>
        </el-table-column>
        <el-table-column label="BIDS Subject ID">
            <template slot-scope="scope">
                <el-input v-model="scope.row.sub" size="small" @change="validate(scope.row)">
                    <template slot="prepend">sub-</template>
                </el-input>
                <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in scope.row.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
            </template>
        </el-table-column>
    </el-table>

    <br>
    <br>
    <br>
    <div class="page-action">
        <el-button @click="back">Back</el-button>
        <el-button type="primary" @click="next" style="float: right;">Next</el-button>
    </div>
</div>
</template>

<script>
import Vue from 'vue'

export default {
    data() {
        return {
            //subjects: [] 
        }
    },
    watch: {
        '$root.currentPage'(v) {
            if(v.id == 'subject') {
                this.$root.subjects.forEach(this.validate);
            }
        },
    },

    methods: {
        resetSubjects(command) {
            console.log("resetting subjects");
            let sub = 1;
            switch(command) {
            case "num":
                this.$root.subjects.forEach(subject=>{
                    subject.sub = sub.toString();
                    sub++;
                });
                break;
            case "pid":
                this.$root.subjects.forEach(subject=>{
                    subject.sub = subject.PatientID.replace(/[^0-9a-zA-Z]/g, '');
                });
                break;
            case "pname":
                this.$root.subjects.forEach(subject=>{
                    subject.sub = subject.PatientName.replace(/[^0-9a-zA-Z]/g, '');
                });
                break;
            }        

            this.$root.subjects.forEach(this.validate);
        },

        validate(s) {
            Vue.set(s, 'validationErrors', []);
            s.sub = s.sub.trim();
            if(s.sub.length == 0) {
                s.validationErrors.push("subject is a required field");
            }
            let cleansub = s.sub.replace(/[^0-9a-zA-Z]/g, '');
            if(s.sub != cleansub) {
                s.validationErrors.push("subject contains non alphanumeric characters");
            }
        },

        next() {
            let valid = true;
            this.$root.subjects.forEach(s=>{
                if(s.validationErrors.length > 0) valid = false;
            });
            if(valid) {
                this.$root.changePage("session");
            } else {
                alert('Please correct all issues');
                return false;
            }
        },

        back() {
            this.$root.changePage("description");
        },
    },
}
</script>

<style scoped>
</style>
