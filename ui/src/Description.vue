<script lang="ts">

import { defineComponent } from 'vue'
import { mapState } from 'vuex'
import { formatNumber } from './filters'
import { DatasetDescription } from './store'

export default defineComponent({
    //props: [ 'dd' ],
    data() {
        return {
            /*
            dd: {
                Name: "",
                DatasetType: "",
                BIDSVersion: "",
                License: "",
                Authors: [],
                Acknowledgements: "",
                HowToAcknowledge: "",
                Funding: [],
                ReferencesAndLinks: [],
                DatasetDOI: "",
                readme: "",
            },
            */

            rules: {
                Name: [
                    {required: true, message: "Please enter dataset description", trigger: "blur"},    
                ],
                DatasetType: [
                    {required: true, message: "Please enter Dataset Type", trigger: "blur"},    
                ],
                BIDSVersion: [
                    {required: true, message: "Please enter BIDS Version", trigger: "blur"},    
                ],
            },
        }

    },
    mounted() {
        console.log("mounted Description");
    },

    computed: {
        ...mapState(['session', 'ezbids', 'config']),

        readme: {
            get(): string {
                return this.ezbids.readme;
            },
            set(v: string) {
                this.$store.commit("setEzbidsReadme", v);
            },
        },
       /*
       ...mapState({
           dd: state=>state.ezbids.DatasetDescription,
       })
       */
        dd: {
            get(): DatasetDescription {
                return this.ezbids.datasetDescription;
            },
            set(v: DatasetDescription) {
                console.error("form doesn't set .. only get", v);
            }
        },
        /*
        Name: {
            get(): string {
                return this.ezbids.datasetDescription.Name;
            },
            set(v: string) {
                this.$store.commit('updateDDName', v);
            }
        },
        */
    },
    methods: {
        //...mapActions(['resetSession']),

        formatNumber,      

        isValid(cb: (v?: string)=>void) {
            // @ts-ignore
            return this.$refs['descForm'].validate(valid=>{
                if(valid) return cb()
                else cb("Please correct all issues on the form.")
            });
        }
    },
});
</script>

<template>
<div style="padding: 20px;">
    <p>A BIDS dataset allows you to store "dataset description". Please populate as much information as much as possible.</p>
    <br>
    <el-form label-width="150px" ref="descForm" :model="dd" :rules="rules">
        <el-form-item label="Dataset Name" prop="Name">
            <el-input v-model="dd.Name"></el-input>
        </el-form-item>
        <el-form-item label="DatasetType" prop="DatasetType">
            <el-input v-model="dd.DatasetType" disabled></el-input>
        </el-form-item>
        <el-form-item label="BIDSVersion" prop="BIDSVersion">
            <el-input v-model="dd.BIDSVersion" disabled></el-input>
        </el-form-item>
        <el-form-item label="License" prop="License">
            <el-input v-model="dd.License"></el-input>
        </el-form-item>
        <el-form-item label="Authors" prop="Authors">
            <el-select v-model="dd.Authors" multiple filterable allow-create default-first-option
                placeholder="Enter Author Names" style="width: 100%">
            </el-select>
        </el-form-item>
        <el-form-item label="Acknowledgements" prop="Acknowledgements">
            <el-input type="textarea"
                placeholder="Any acknowledgements you'd like to add.." 
                :autosize="{ minRows: 2, maxRows: 6}"
                v-model="dd.Acknowledgements"/>
        </el-form-item>

        <el-form-item label="How To Acknowledge" prop="HowToAckowledge">
            <el-input type="textarea"
                placeholder="Enter how you want your users to acknowlege when they use this dataset"
                :autosize="{ minRows: 2, maxRows: 6}"
                v-model="dd.HowToAcknowledge"/>
        </el-form-item>

        <el-form-item label="Funding Sources" prop="Funding">
            <el-select v-model="dd.Funding" multiple filterable     
                allow-create default-first-option
                placeholder="Funding sources" style="width: 100%">
            </el-select>
        </el-form-item>

        <el-form-item label="References and Links" prop="ReferencesAndLinks">
            <el-select v-model="dd.ReferencesAndLinks" multiple filterable     
                allow-create default-first-option
                placeholder="Add any references / citations / links" style="width: 100%">
            </el-select>
        </el-form-item>

        <el-form-item label="Dataset DOI" prop="DatasetDOI">
            <el-input placeholder="DOI assigned for this dataset"
                v-model="dd.DatasetDOI"/>
        </el-form-item>

        <p style="border-top: 1px solid #0002" prop="readme"/>
        <el-form-item label="README(.md)">
            <el-input type="textarea" 
                placeholder="BIDS README. Should not be empty"
                :autosize="{ minRows: 10, maxRows: 25 }"
                v-model="readme"/>
        </el-form-item>
        <!--
        <div class="page-action">
            <el-button @click="back">Back</el-button>
            <el-button type="primary" @click="next" style="float: right;">Next</el-button>
        </div>
        -->
    </el-form>

</div>
</template>

<style scoped>

</style>
