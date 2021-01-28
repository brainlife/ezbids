<template>
<div v-if="$root.currentPage.id == 'subject'" style="padding: 20px;">
    <h4>Patient / Subject Mappings</h4>
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
        <el-table-column label="BIDS Subject ID" width="300px">
            <template slot-scope="scope">
                <el-input v-model="scope.row.sub" size="small" @change="validate(scope.row)">
                    <template slot="prepend">sub-</template>
                </el-input>
                <p>
                    <el-checkbox v-model="scope.row.exclude" title="Exclude all objects from BIDS output for this subject">Exclude this subject</el-checkbox>
                </p>
                <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in scope.row.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
            </template>
        </el-table-column>
        <el-table-column label="AcquisitionDate / Session ID Mappings">
            <template slot-scope="scope">
                <el-table :data="scope.row.sessions" size="mini" :show-header="false">
                    <el-table-column prop="AcquisitionDate" width="150px">
                        <!--
                        <template slot-scope="scope">
                            <div v-for="(session, idx) in scope.row.sessions" :key="idx">
                                {{session.AcquisitionDate}}
                            </div>
                        </template>
                        -->
                    </el-table-column>
                    <el-table-column>
                        <template slot-scope="sessionScope">
                            <el-input v-model="sessionScope.row.ses" placeholder="no session" size="small" @change="validate(scope.row)">
                                <template slot="prepend">ses-</template>
                            </el-input>
                        </template>
                    </el-table-column>
                    <el-table-column label="">
                        <template slot-scope="sessionScope">
                            <el-checkbox v-model="sessionScope.row.exclude" title="Exclude all objects for this session">Exclude this session</el-checkbox>
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
                this.$root.subjects.forEach(subject=>{
                    subject.sub = sub.toString().padStart(2, '0');
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

            //session is optional.
            /*
            s.sessions.forEach(ses=>{
                if(!ses.ses) s.validationErrors.push("Please populate session mapping for "+ses.AcquisitionDate);
            });
            */
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
