<template>
<div style="padding: 20px;">
    <p>Please map DICOM PatientID to BIDS Subject ID. 
        You can also specify AcquisitionDate/session mappings for each subject. 
        The mapping table can be downloaded later for future references.</p>

    <el-dropdown @command="resetSubjects" style="float: right; margin: 10px;" size="small">
        <el-button type="primary" size="small">
            Reset Subject Mapping <i class="el-icon-arrow-down el-icon--right"></i>
        </el-button>
        <template #dropdown>
            <el-dropdown-menu>
                <el-dropdown-item command="pname">Use PatientName</el-dropdown-item>
                <el-dropdown-item command="pid">Use PatientID</el-dropdown-item>
                <el-dropdown-item command="num">Numerical (1,2,3..)</el-dropdown-item>
            </el-dropdown-menu>
        </template>
    </el-dropdown>

    <el-table :data="ezbids.subjects" style="width: 100%" size="mini" class="table-align-top">
        <el-table-column label="DICOM Patient" width="330px">
            <template #default="scope">
                <i class="el-icon-right" style="float: right; font-size: 150%; font-weight: bold;"/>
                <div class="patient-info">
                <p v-for="(info, idx) in scope.row.PatientInfo" :key="idx">
                    <b>PatientID</b> {{info.PatientID}}<br>
                    <b>PatientName</b> {{info.PatientName}}<br>
                    <b>PatientBirthDate</b> {{info.PatientBirthDate||'(not set)'}}<br>
                </p>
                </div>
            </template>
        </el-table-column>
        <el-table-column label="Subject/Sessions Mappings">
            <template #default="scope">

                <el-checkbox v-model="scope.row.exclude" title="Exclude all objects from BIDS output for this subject">
                    Exclude this patient / subject
                </el-checkbox>
                <el-input v-model.trim="scope.row.subject" size="small" @change="validate(scope.row)">
                    <template #prepend>sub-</template>
                </el-input>

                <el-table :data="scope.row.sessions" size="mini" :show-header="false">
                    <el-table-column :span="16">
                        <template #default="sessionScope">
                            <el-row>
                                <el-col :span="8">
                                    <b>AcquisitionDate</b><br>
                                    {{sessionScope.row.AcquisitionDate}}
                                </el-col>
                                <el-col :span="16">
                                    <el-checkbox v-model="sessionScope.row.exclude" title="Exclude all objects for this session">
                                        Exclude this acquisition / session
                                    </el-checkbox>
                                    <el-input v-model.trim="sessionScope.row.session" placeholder="no session" size="small" @change="validate(scope.row)">
                                        <template #prepend>ses-</template>
                                    </el-input>
                                </el-col>
                            </el-row>
                        </template>
                    </el-table-column>
                </el-table>

                <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in scope.row.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
            </template>
        </el-table-column>
    </el-table>

    <pre>{{ezbids.subjects}}</pre>
</div>
</template>

<script lang="ts">

import { mapState } from 'vuex'
import { Subject } from './store'
import { defineComponent } from 'vue'

export default defineComponent({
    data() {
        return {
        }
    },
    /*
    watch: {
        '$root.currentPage'(v) {
            if(v.id == 'subject') {
                this.$root.subjects.forEach(this.validate);
            }
        },
    },
    */
    created() {
        console.log("Subject create");
        this.validateAll();
    },

    computed: {
        ...mapState(['ezbids', 'config']),
    },

    methods: {
        resetSubjects(command: string) {
            console.log("resetting subjects");
            let sub = 1;
            switch(command) {
            case "num":
                this.ezbids.subjects.forEach((s:Subject)=>{
                    s.subject = sub.toString().padStart(2, '0');
                    sub++;
                });
                break;
            case "pid":
                this.ezbids.subjects.forEach((s:Subject)=>{
                    const firstInfo = s.PatientInfo[0]; //TODO - should I concatenate all PatientInfo?
                    s.subject = firstInfo.PatientID.replace(/[^0-9a-zA-Z]/g, '');
                });
                break;
            case "pname":
                this.ezbids.subjects.forEach((s:Subject)=>{
                    const firstInfo = s.PatientInfo[0]; //TODO - should I concatenate all PatientInfo?
                    s.subject = firstInfo.PatientName.replace(/[^0-9a-zA-Z]/g, '');
                });
                break;
            }        

            this.validateAll();
        },

        validateAll() {
            this.ezbids.subjects.forEach(this.validate);
        },

        validate(s: Subject) {
            //Vue.set(s, 'validationErrors', []);
            s.validationErrors = [];

            if(s.subject.length == 0) {
                //this.$store.commit("addValidationError", {s, error:"subject is a required field"});
                s.validationErrors.push("subject is a required field");
            }

            let cleansub = s.subject.replace(/[^0-9a-zA-Z]/g, '');
            if(s.subject != cleansub) {
                //this.$store.commit("addValidationError", {s, error: "subject contains non alphanumeric characters"});
                s.validationErrors.push("subject contains non alphanumeric characters");
            }
        },

        isValid(cb: (v?: string)=>void) {
            this.validateAll();

            let err = undefined;
            this.ezbids.subjects.forEach((s: Subject)=>{
                if(s.validationErrors.length > 0) err = "Please correct all issues";
            });
            return cb(err);
        },
    },
});

</script>


<style lang="scss" scoped>
.patient-info {
    p {
        margin-top: 0px;
        margin-bottom: 5px;
    }
    p:not(:first-child) {
        border-top: 1px solid #0001;  
        padding-top: 5px;  
    }
}
</style>
