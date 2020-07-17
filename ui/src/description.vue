<template>
<div>
    <p>A BIDS dataset requires "dataset description". Please populate the following information as much as possible.</p>
    <br>
    <el-form label-width="150px">
        <h4 style="margin-left: 150px;">Dataset Description</h4>
        <el-form-item label="Dataset Name">
            <el-input v-model="dd.Name" required></el-input>
        </el-form-item>
        <el-form-item label="DatasetType">
            <el-input v-model="dd.DatasetType" required disabled></el-input>
        </el-form-item>
        <el-form-item label="BIDSVersion">
            <el-input v-model="dd.BIDSVersion" required disabled></el-input>
        </el-form-item>
        <el-form-item label="License">
            <el-input v-model="dd.License"></el-input>
        </el-form-item>
        <el-form-item label="Authors">
            <el-select v-model="dd.Authors" multiple filterable allow-create default-first-option
                placeholder="Enter Author Names" style="width: 100%">
            </el-select>
        </el-form-item>
        <el-form-item label="Acknowledgements">
            <el-input type="textarea"
                placeholder="Any acknowledgements you'd like to add.." 
                :autosize="{ minRows: 2, maxRows: 6}"
                v-model="dd.Acknowledgements"/>
        </el-form-item>

        <el-form-item label="How To Acknowledge">
            <el-input type="textarea"
                placeholder="Enter how you want your users to acknowlege when they use this dataset"
                :autosize="{ minRows: 2, maxRows: 6}"
                v-model="dd.HowToAcknowledge"/>
        </el-form-item>

        <el-form-item label="Funding Sources">
            <el-select v-model="dd.Funding" multiple filterable     
                allow-create default-first-option
                placeholder="Funding sources" style="width: 100%">
            </el-select>
        </el-form-item>

        <el-form-item label="References and Links">
            <el-select v-model="dd.ReferencesAndLinks" multiple filterable     
                allow-create default-first-option
                placeholder="Add any references / citations / links" style="width: 100%">
            </el-select>
        </el-form-item>

        <el-form-item label="Dataset DOI">
            <el-input placeholder="DOI assigned for this dataset"
                v-model="dd.DatasetDOI"/>
        </el-form-item>

        <p style="border-top: 1px solid #0002"/>
        <el-form-item label="README(.md)">
            <el-input type="textarea" 
                :autosize="{ minRows: 20, maxRows: 25 }"
                v-model="readme"/>
        </el-form-item>
    </el-form>
</div>
</template>

<script>

export default {
    computed: {

        dd() {
            return this.$root.datasetDescription;
        },

        readme: {
            get() {
                return this.$root.readme;
            },
            set(v) {
                this.$root.readme = v;
            },
        },
    },

    components: {
    },

    data() {
        return {}
    },

    created() {
    },

    methods: {
    },
}
</script>

<style scoped>
</style>
