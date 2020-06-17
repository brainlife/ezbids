<template>
<div>
    <p>Please populate as much information below as possible.</p>
    <p>This information will be used to generate <b>dataset_description.json</b> which is required by all BIDS dataset.
    </p>
    <br>
    <el-form label-width="150px">
        <el-row :gutter="20">
            <el-col :span="15">
                <h4 style="margin-left: 150px;">Dataset Description</h4>
                <el-form-item label="Dataset Name">
                    <el-input v-model="dd.Name" required></el-input>
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
                        <!--
                        <el-option
                        v-for="item in options"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value">
                        </el-option>
                        -->
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
                    <!--
                    <el-input type="textarea"
                        placeholder="Funding sources"
                        :autosize="{ minRows: 2, maxRows: 6}"
                        v-model="dd.Funding"/>
                    -->
                    <el-select v-model="dd.Funding" multiple filterable     
                        allow-create default-first-option
                        placeholder="Funding sources" style="width: 100%">
                        <!--
                        <el-option
                        v-for="item in options"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value">
                        </el-option>
                        -->
                    </el-select>
                </el-form-item>

                <el-form-item label="References and Links">
                    <el-select v-model="dd.referencesandlinks" multiple filterable     
                        allow-create default-first-option
                        placeholder="Add any references / citations / links" style="width: 100%">
                        <!--
                        <el-option
                        v-for="item in options"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value">
                        </el-option>
                        -->
                    </el-select>
                </el-form-item>

                <el-form-item label="Dataset DOI">
                    <el-input placeholder="DOI assigned for this dataset"
                        v-model="dd.DatasetDOI"/>
                </el-form-item>
            </el-col>
            <el-col :span="9">
                <h4>README.md</h4>
                <el-input type="textarea" 
                    :autosize="{ minRows: 20, maxRows: 25 }"
                    v-model="readme"/>
            </el-col>
        </el-row>
        <p style="border-top: 1px solid #ddd;"/>
    </el-form>

    <pre>{{dd}}</pre>
    <pre>{{readme}}</pre>

    <!--
    <pre>{{$store.state.dataset_description}}</pre>
    <el-button @click="increment">Increment {{$store.state}}</el-button>
    -->
</div>
</template>

<script>

//import store from './store'
//import { mapState } from 'vuex'

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
        return {
        }
    },
    created() {
    },
    methods: {
    },
}
</script>

<style scoped>
</style>
