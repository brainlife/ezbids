<template>
<div v-if="$root.currentPage.id == 'subject'" style="padding: 20px;">
    <h4>Patient/Subject and Acq/Session Mappings</h4>
    <el-dropdown @command="resetSubjects" style="float: right; margin: 10px;" size="small">
        <el-button type="primary" size="small">
            Reset Subject Mapping <i class="el-icon-arrow-down el-icon--right"></i>
        </el-button>
        <el-dropdown-menu slot="dropdown">
            <el-dropdown-item command="pname">Use PatientName</el-dropdown-item>
            <el-dropdown-item command="pid">Use PatientID</el-dropdown-item>
            <el-dropdown-item command="num">Numerical (1,2,3..)</el-dropdown-item>
        </el-dropdown-menu>
    </el-dropdown>
    <p>Decide how you want to map DICOM PatientID to BIDS Subject ID. You can also specify AcquisitionDate/session mappings for each subject. You can download the mapping table later.</p>
    <el-table :data="$root.subjects" style="width: 100%" size="mini" class="table-align-top">
        <el-table-column label="DICOM Patient" width="270px">
            <template slot-scope="scope">
                <i class="el-icon-right" style="float: right; font-size: 150%; font-weight: bold;"/>
                <div>
                    <b>PatientID</b> {{scope.row.PatientID}}<br>
                    <b>PatientName</b> {{scope.row.PatientName}}<br>
                    <b>PatientBirthDate</b> {{scope.row.PatientBirthDate||'(not set)'}}<br>
                </div>
            </template>
        </el-table-column>
        <el-table-column label="Subject/Sessions">
            <template slot-scope="scope">
                <el-row :gutter="10">
                    <el-col :span="16">
                        <el-input v-model="scope.row.subject" size="small" @change="validate(scope.row)">
                            <template slot="prepend">sub-</template>
                        </el-input>
                    </el-col>
                    <el-col :span="8">
                        <el-checkbox v-model="scope.row.exclude" title="Exclude all objects from BIDS output for this subject">Exclude this subject</el-checkbox>
                    </el-col>
                </el-row>
                <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in scope.row.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                <el-table :data="scope.row.sessions" size="mini" :show-header="false">
                    <el-table-column :span="16">
                        <template slot-scope="sessionScope">
                            <el-row :gutter="10">
                                <el-col :span="6">
                                    <b>AcquisitionDate</b> {{sessionScope.row.AcquisitionDate}}
                                </el-col>
                                <el-col :span="8">
                                    <el-input v-model="sessionScope.row.session" placeholder="no session" size="small" @change="validate(scope.row)">
                                        <template slot="prepend">ses-</template>
                                    </el-input>
                                </el-col>
                                <el-col :span="10">
                                    <el-checkbox v-model="sessionScope.row.exclude" title="Exclude all objects for this session">Exclude this session</el-checkbox>
                                </el-col>
                            </el-row>
                        </template>
                    </el-table-column>
                </el-table>

            </template>
        </el-table-column>
    </el-table>

    <pre v-if="config.debug">{{$root.subjects}}</pre>

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
            config: Vue.config,
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
                this.$root.subjects.forEach(s=>{
                    s.subject = sub.toString().padStart(2, '0');
                    sub++;
                });
                break;
            case "pid":
                this.$root.subjects.forEach(s=>{
                    s.subject = s.PatientID.replace(/[^0-9a-zA-Z]/g, '');
                });
                break;
            case "pname":
                this.$root.subjects.forEach(s=>{
                    s.subject = s.PatientName.replace(/[^0-9a-zA-Z]/g, '');
                });
                break;
            }        

            this.$root.subjects.forEach(this.validate);
        },

        validate(s) {
            Vue.set(s, 'validationErrors', []);
            s.subject = s.subject.trim();
            if(s.subject.length == 0) {
                s.validationErrors.push("subject is a required field");
            }
            let cleansub = s.subject.replace(/[^0-9a-zA-Z]/g, '');
            if(s.subject != cleansub) {
                s.validationErrors.push("subject contains non alphanumeric characters");
            }
        },

        next() {
            let valid = true;
            this.$root.subjects.forEach(s=>{
                if(s.validationErrors.length > 0) valid = false;
            });
            if(valid) {
                this.$root.changePage("participant");
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


