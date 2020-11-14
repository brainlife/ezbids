<template>
<div v-if="$root.currentPage.id == 'session'" style="padding: 20px">
    <h4>AcquisitionDate / Session Mappings</h4>
    <p>Decide how want to map DICOM AcquisitionDate to BIDS Session IDs. You should leave it blank if it's single session. You can download the mapping table later.</p>
    <!--series ID-->
    <el-dropdown @command="resetSessions" style="float: right;" size="small">
        <el-button type="primary" size="small">
            Reset Mapping <i class="el-icon-arrow-down el-icon--right"></i>
        </el-button>
        <el-dropdown-menu slot="dropdown">
            <el-dropdown-item command="empty">Leave them empty</el-dropdown-item>
            <el-dropdown-item command="date">Use AcquisitionDates</el-dropdown-item>
            <el-dropdown-item command="num">Numerical (1,2,3..)</el-dropdown-item>
            <el-dropdown-item command="same">Set all to the same ID ...</el-dropdown-item>
        </el-dropdown-menu>
    </el-dropdown>
    <el-table :data="$root.sessions" style="width: 100%" size="mini">
        <el-table-column label="DICOM AcquisitionDate" width="300px">
            <template slot-scope="scope">
                {{scope.row.AcquisitionDate}}
                <small>{{scope.row.desc}}</small>
            </template>
        </el-table-column>
        <el-table-column label="Unique Subjects" width="200px">
            <template slot-scope="scope">
                <i class="el-icon-right" style="float: right; font-size: 150%; font-weight: bold;"/>
                <span v-for="sub in findUniqueSubjects(scope.row.AcquisitionDate)" :key="sub">{{sub}}&nbsp;</span>
            </template>
        </el-table-column>
        <el-table-column label="BIDS Session ID">
            <template slot-scope="scope">
                <el-input v-model="scope.row.ses" placeholder="no session" size="small" @change="validate(scope.row)">
                    <template slot="prepend">ses-</template>
                </el-input>
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
            if(v.id == 'session') {
                this.$root.objects.forEach(this.$root.mapObject);
                this.$root.sessions.forEach(this.validate);
            }
        },
    },

    methods: {

        findUniqueSubjects(acqDate) {
            let subjects = this.$root.objects.filter(o=>o.AcquisitionDate == acqDate).map(o=>o._entities.sub);
            return [...new Set(subjects)]; //unique
        },

        resetSessions(command) {
            console.log("reset session");
            let num = 1;
            let id;
            switch(command) {
            case "empty":
                this.$root.sessions.forEach(session=>{
                    session.ses = "";
                });
                break;
            case "date":
                this.$root.sessions.forEach(session=>{
                    session.ses = session.AcquisitionDate;
                });
                break;
            case "num":
                this.$root.sessions.forEach(session=>{
                    session.ses = num.toString();
                    num++;
                });
                break;
            case "same":
                id = prompt("Please enter session ID to set");
                this.$root.sessions.forEach(session=>{
                    session.ses = id;
                    num++;
                });
                break;
            }        
            this.$root.sessions.forEach(this.validate);
        },

        validate(s) {
            //TODO..
            Vue.set(s, 'validationErrors', []);
        },

        next() {
            let valid = true;
            this.$root.sessions.forEach(s=>{
                if(s.validationErrors.length > 0) valid = false;
            });
            if(valid) {
                this.$root.changePage("series");
            } else {
                alert('Please correct all issues');
            }
        },

        back() {
            this.$root.changePage("subject");
        },

    },
}
</script>

<style scoped>
</style>
