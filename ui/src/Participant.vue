<template>
<div style="padding: 20px">
    <p>You can store metadata/phenotypical data for each subject/participants on this datasets in the BIDS dataset.</p>
    <p>Please skip this step if you do not need to store any phenotypical data.</p>
    <h5>Phenotype Columns</h5>
    <small>Define phenotypical keys stored for this study (optional).</small>
    <br><br>
    <el-form>
        <div v-for="(column, key) in ezbids.participantsColumn" :key="key" class="columnEditor">
            <span style="float: right">
                <el-button type="danger" @click="remove(key)" size="mini"><Remove style="width: 16px;"/></el-button>
            </span>
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
    <small>Enter phenotypical data associated with each participants.</small>
    <br><br>
    <div style="width: 100%">
        <table class="phenotype">
        <thead>
        <tr>
            <th>Subject</th>
            <th v-for="(column, key) in ezbids.participantsColumn" :key="key">
                {{key}}
            </th>
        </tr>
        </thead>
        <tbody>
            <tr v-for="o_sub in ezbids._organized" :key="o_sub.sub">
                <th>{{o_sub.sub}}</th>
                <td v-for="(column, key) in ezbids.participantsColumn" :key="key">
                    <div v-if="findSubjectFromString(o_sub.sub) !== undefined">
                        <el-input v-model="findSubjectFromString(o_sub.sub).phenotype[key]" size="mini"/>
                    </div>
                </td>
            </tr>
        </tbody>
        </table>
    </div>
</div>
</template>

<script lang="ts">

import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue'

//element-plus icons are bad .. replace it with fontawesome
// @ts-ignore
import { Remove } from '@element-plus/icons/lib'

export default defineComponent({
    components: {
        Remove,
    },

    data() {
        return {
            newcolumn: "",
        }
    },

    computed: {
        ...mapState(['ezbids', 'config']),
        ...mapGetters(['findSubjectFromString']),

    },

    methods: {
        addNewColumn() {
            if(!this.newcolumn) return;
            this.ezbids.participantsColumn[this.newcolumn] = {
                LongName: "",
                Description: "",
                Units: "",
                Levels: {},
            }
            this.newcolumn = "";
        },

        remove(key: string|number|symbol) {
            delete this.ezbids.participantsColumn[key];
        },

        //TODO
        validate() {
            console.log("todo - validate participant");
        },

        isValid(cb: (v?: string)=>void) {
            console.log("validaging participant");
            this.validate();
            //TODO
            cb();
        }
    },
});
</script>

<style lang="scss" scoped>
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
table.phenotype {
    width: 100%;
    border-collapse: collapse;
    font-size: 90%;
}
table.phenotype thead {
    background-color: #eee;
    color: #666;
}
table.phenotype td,
table.phenotype th {
    padding: 5px 10px;
}
</style>
