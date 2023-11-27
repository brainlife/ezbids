<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { formatNumber } from './filters';
import { DatasetDescription } from './store';

export default defineComponent({
    //props: [ 'dd' ],
    data() {
        return {
            rules: {
                Name: [{ required: true, message: 'Please enter dataset description', trigger: 'blur' }],
                DatasetLinks: [
                    { required: true, message: 'Please enter Dataset Links if BIDS URI(s) used', trigger: 'blur' },
                ],
                BIDSVersion: [{ required: true, message: 'Please enter BIDS Version', trigger: 'blur' }],
            },
        };
    },
    computed: {
        ...mapState(['session', 'ezbids', 'config']),

        readme: {
            get(): string {
                return this.ezbids.readme;
            },
            set(v: string) {
                this.$store.commit('setEzbidsReadme', v);
            },
        },

        dd: {
            get(): DatasetDescription {
                return this.ezbids.datasetDescription;
            },
            set(v: DatasetDescription) {
                console.error("form doesn't set .. only get", v);
            },
        },
    },

    mounted() {},

    methods: {
        formatNumber,

        isValid(cb: (v?: string) => void) {
            // @ts-ignore
            return this.$refs['descForm'].validate((valid) => {
                if (valid) return cb();
                else cb('Please correct all issues on the form.');
            });
        },
    },
});
</script>

<template>
    <div style="padding: 20px">
        <p>
            Please enter as much information you like to include in the <b>dataset_description.json</b>. For specific
            For specific information and examples, see
            <a
                href="https://bids-specification.readthedocs.io/en/stable/03-modality-agnostic-files.html#dataset_descriptionjson"
                target="_blank"
                >here</a
            >
            and
            <a
                href="https://github.com/bids-standard/bids-examples/blob/master/ds000117/dataset_description.json"
                target="_blank"
                >here</a
            >
        </p>
        <br />
        <el-form ref="descForm" label-width="150px" :model="dd" :rules="rules">
            <el-form-item label="Dataset Name" prop="Name">
                <el-input v-model="dd.Name"></el-input>
            </el-form-item>
            <el-form-item label="BIDSVersion" prop="BIDSVersion">
                <el-input v-model="dd.BIDSVersion" disabled></el-input>
            </el-form-item>
            <el-form-item label="HEDVersion" prop="HEDVersion">
                <el-select
                    v-model="dd.HEDVersion"
                    multiple
                    filterable
                    allow-create
                    default-first-option
                    placeholder="Enter HED tags"
                    style="width: 100%"
                >
                </el-select>
            </el-form-item>
            <el-form-item label="DatasetType" prop="DatasetType">
                <el-input v-model="dd.DatasetType" disabled></el-input>
            </el-form-item>
            <el-form-item label="License" prop="License">
                <el-input v-model="dd.License"></el-input>
            </el-form-item>
            <el-form-item label="Authors" prop="Authors">
                <el-select
                    v-model="dd.Authors"
                    multiple
                    filterable
                    allow-create
                    default-first-option
                    placeholder="Enter Author Names"
                    style="width: 100%"
                >
                </el-select>
            </el-form-item>
            <el-form-item label="Acknowledgements" prop="Acknowledgements">
                <el-input
                    v-model="dd.Acknowledgements"
                    type="textarea"
                    placeholder="Any acknowledgements you'd like to add.."
                    :autosize="{ minRows: 2, maxRows: 6 }"
                />
            </el-form-item>
            <el-form-item label="How To Acknowledge" prop="HowToAckowledge">
                <el-input
                    v-model="dd.HowToAcknowledge"
                    type="textarea"
                    placeholder="Enter how you want your users to acknowledge when they use this dataset"
                    :autosize="{ minRows: 2, maxRows: 6 }"
                />
            </el-form-item>
            <el-form-item label="Funding Sources" prop="Funding">
                <el-select
                    v-model="dd.Funding"
                    multiple
                    filterable
                    allow-create
                    default-first-option
                    placeholder="Funding sources"
                    style="width: 100%"
                >
                </el-select>
            </el-form-item>
            <el-form-item label="EthicsApprovals" prop="EthicsApprovals">
                <el-select
                    v-model="dd.EthicsApprovals"
                    multiple
                    filterable
                    allow-create
                    default-first-option
                    placeholder="Enter list of ethics committee approvals of the research"
                    style="width: 100%"
                >
                </el-select>
            </el-form-item>
            <el-form-item label="References and Links" prop="ReferencesAndLinks">
                <el-select
                    v-model="dd.ReferencesAndLinks"
                    multiple
                    filterable
                    allow-create
                    default-first-option
                    placeholder="Add any references / citations / links"
                    style="width: 100%"
                >
                </el-select>
            </el-form-item>
            <el-form-item label="Dataset DOI" prop="DatasetDOI">
                <el-input v-model="dd.DatasetDOI" placeholder="DOI assigned for this dataset" />
            </el-form-item>
            <el-form-item label="GeneratedBy">
                <br />
                <div v-if="dd.GeneratedBy">
                    <template v-for="(value, key, index) in dd.GeneratedBy[0]" :key="index">
                        <el-form-item v-if="key !== 'Container'" :label="key">
                            <el-input v-model="dd.GeneratedBy[0][key]" :placeholder="value" />
                        </el-form-item>
                        <el-form-item v-if="key == 'Container'" :label="key" style="width: 50px"></el-form-item>
                    </template>
                    <div v-if="dd.GeneratedBy[0].Container">
                        <el-form-item
                            v-for="(containerValue, containerKey, containerIndex) in dd.GeneratedBy[0].Container"
                            :key="containerIndex"
                            :label="containerKey"
                        >
                            <el-input
                                v-model="dd.GeneratedBy[0].Container[containerKey]"
                                :placeholder="containerValue"
                            />
                        </el-form-item>
                    </div>
                </div>
            </el-form-item>
            <!-- <el-form-item label="SourceDatasets">
                <div v-if="dd.SourceDatasets && dd.SourceDatasets[0]">
                    <el-form-item v-for="(value, key) in dd.SourceDatasets[0]" :key="key" :label="key">
                        <el-input :placeholder="value" v-model="dd.SourceDatasets[0][key]" />
                    </el-form-item>
                </div>
            </el-form-item> -->
            <p style="border-top: 1px solid #0002" prop="readme" />
            <el-form-item label="README(.md)">
                <el-input
                    v-model="readme"
                    type="textarea"
                    placeholder="BIDS README. Should not be empty"
                    :autosize="{ minRows: 10, maxRows: 25 }"
                />
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

<style lang="scss" scoped></style>
