<template>
<div>
    <p>Please decide how you'd like to map DICOM PatientID to BIDS Subject IDs. You can download the mapping table once you are done mapping.</p>
    <br>

    <el-dropdown @command="resetSubjects" style="float: right;" size="small">
        <el-button type="primary">
            Reset Mapping <i class="el-icon-arrow-down el-icon--right"></i>
        </el-button>
        <el-dropdown-menu slot="dropdown">
            <el-dropdown-item command="pid">Use PatientID</el-dropdown-item>
            <el-dropdown-item command="num">Numerical (1,2,3..)</el-dropdown-item>
        </el-dropdown-menu>
    </el-dropdown>
    <h4>Patient/Subject Mappings</h4>
    <el-table :data="$root.subjects" style="width: 100%" size="mini">
        <el-table-column label="DICOM PatientID">
            <template slot-scope="scope">
                <i class="el-icon-right" style="float: right"/>
                {{scope.row.PatientID}}
            </template>
        </el-table-column>
        <el-table-column label="BIDS Subject ID">
            <template slot-scope="scope">
                <el-input v-model="scope.row.sub" size="small">
                    <template slot="prepend">sub-</template>
                </el-input>
            </template>
        </el-table-column>
    </el-table>
</div>
</template>

<script>

export default {
    data() {
        return {
            //subjects: [] 
        }
    },
    watch: {
        '$root.subjects'(v, ov) {
            console.log("subjects updated.. initializing keys");
            if(v.length == 0) return; //prevent infinite loop
            if(ov.length == 0) {
                this.resetSubjects('pid');
            }
        },

    },

    created() {
    },

    methods: {
        resetSubjects(command) {
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
                    subject.sub = subject.PatientID;
                });
                break;
            }        
        },
    },
}
</script>

<style scoped>
</style>
