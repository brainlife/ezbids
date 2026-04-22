<template>
    <div class="description-page">
        <header class="description-intro">
            <h2 class="description-intro__title">Dataset description</h2>
            <p class="description-intro__text">
                Enter the metadata that will be written to <strong>dataset_description.json</strong>. For field
                definitions and examples, see the
                <a
                    href="https://bids-specification.readthedocs.io/en/stable/03-modality-agnostic-files.html#dataset_descriptionjson"
                    target="_blank"
                    rel="noopener noreferrer"
                    >BIDS specification</a
                >
                and a
                <a
                    href="https://github.com/bids-standard/bids-examples/blob/master/ds000117/dataset_description.json"
                    target="_blank"
                    rel="noopener noreferrer"
                    >sample file</a
                >.
            </p>
        </header>

        <div class="description-card">
            <el-form
                ref="descForm"
                class="description-form"
                label-width="168px"
                label-position="right"
                :model="dd"
                :rules="rules"
            >
                <el-form-item label="Dataset name" prop="Name">
                    <el-input v-model="dd.Name" class="full-width" placeholder="Short name for this dataset" />
                </el-form-item>
                <el-form-item label="BIDS version" prop="BIDSVersion">
                    <el-input v-model="dd.BIDSVersion" class="full-width" disabled />
                </el-form-item>
                <el-form-item label="HED version" prop="HEDVersion">
                    <el-select
                        v-model="dd.HEDVersion"
                        class="full-width"
                        multiple
                        filterable
                        allow-create
                        default-first-option
                        placeholder="Enter HED tags"
                    >
                    </el-select>
                </el-form-item>
                <el-form-item label="Dataset type" prop="DatasetType">
                    <el-input v-model="dd.DatasetType" class="full-width" disabled />
                </el-form-item>
                <el-form-item label="License" prop="License">
                    <el-input v-model="dd.License" class="full-width" placeholder="e.g. CC0-1.0" />
                </el-form-item>
                <el-form-item label="Authors" prop="Authors">
                    <el-select
                        v-model="dd.Authors"
                        class="full-width"
                        multiple
                        filterable
                        allow-create
                        default-first-option
                        placeholder="Author names"
                    >
                    </el-select>
                </el-form-item>
                <el-form-item label="Acknowledgements" prop="Acknowledgements">
                    <el-input
                        v-model="dd.Acknowledgements"
                        class="full-width"
                        type="textarea"
                        placeholder="Optional acknowledgements"
                        :autosize="{ minRows: 2, maxRows: 6 }"
                    />
                </el-form-item>
                <el-form-item label="How to acknowledge" prop="HowToAcknowledge">
                    <el-input
                        v-model="dd.HowToAcknowledge"
                        class="full-width"
                        type="textarea"
                        placeholder="How you want others to cite or acknowledge this dataset"
                        :autosize="{ minRows: 2, maxRows: 6 }"
                    />
                </el-form-item>
                <el-form-item label="Funding" prop="Funding">
                    <el-select
                        v-model="dd.Funding"
                        class="full-width"
                        multiple
                        filterable
                        allow-create
                        default-first-option
                        placeholder="Funding sources"
                    >
                    </el-select>
                </el-form-item>
                <el-form-item label="Ethics approvals" prop="EthicsApprovals">
                    <el-select
                        v-model="dd.EthicsApprovals"
                        class="full-width"
                        multiple
                        filterable
                        allow-create
                        default-first-option
                        placeholder="Ethics committee approvals"
                    >
                    </el-select>
                </el-form-item>
                <el-form-item label="References & links" prop="ReferencesAndLinks">
                    <el-select
                        v-model="dd.ReferencesAndLinks"
                        class="full-width"
                        multiple
                        filterable
                        allow-create
                        default-first-option
                        placeholder="References, citations, or URLs"
                    >
                    </el-select>
                </el-form-item>
                <el-form-item label="Dataset DOI" prop="DatasetDOI">
                    <el-input
                        v-model="dd.DatasetDOI"
                        class="full-width"
                        placeholder="DOI for this dataset, if assigned"
                    />
                </el-form-item>

                <el-form-item label="Generated by" class="description-form__generated">
                    <div v-if="dd.GeneratedBy?.[0]" class="generated-block">
                        <div class="generated-subsection__title">Details</div>
                        <div v-for="key in generatedByFieldKeys" :key="key" class="generated-row">
                            <label class="generated-row__label" :for="`generated-by-${key}`">{{ key }}</label>
                            <el-input
                                :id="`generated-by-${key}`"
                                v-model="(dd.GeneratedBy[0] as any)[key]"
                                class="full-width"
                                :placeholder="String((dd.GeneratedBy[0] as any)[key] ?? '')"
                            />
                        </div>

                        <div v-if="dd.GeneratedBy[0].Container" class="generated-subsection">
                            <div class="generated-subsection__title">Container</div>
                            <div v-for="ck in generatedByContainerKeys" :key="ck" class="generated-row">
                                <label class="generated-row__label" :for="`generated-container-${ck}`">{{ ck }}</label>
                                <el-input
                                    :id="`generated-container-${ck}`"
                                    v-model="(dd.GeneratedBy[0].Container as any)[ck]"
                                    class="full-width"
                                    :placeholder="String((dd.GeneratedBy[0].Container as any)[ck] ?? '')"
                                />
                            </div>
                        </div>
                    </div>
                </el-form-item>

                <el-form-item label="README (.md)">
                    <el-input
                        v-model="readme"
                        class="full-width"
                        type="textarea"
                        placeholder="Content for README.md in the BIDS dataset root"
                        :autosize="{ minRows: 10, maxRows: 25 }"
                    />
                </el-form-item>
            </el-form>
        </div>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { DatasetDescription } from '@/store/store.types';

export default defineComponent({
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
        ...mapState(['ezbids']),

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

        /** Keys on `GeneratedBy[0]` except `Container`, in a sensible order. */
        generatedByFieldKeys(): string[] {
            const row = this.dd.GeneratedBy?.[0] as unknown as Record<string, unknown> | undefined;
            if (!row) return [];
            const preferred = ['Name', 'Version', 'Description', 'CodeURL'];
            const keys = Object.keys(row).filter((k) => k !== 'Container');
            const head = preferred.filter((k) => keys.includes(k));
            const tail = keys.filter((k) => !head.includes(k));
            return [...head, ...tail];
        },

        /** Keys on `GeneratedBy[0].Container` with Type/Tag first when present. */
        generatedByContainerKeys(): string[] {
            const c = this.dd.GeneratedBy?.[0]?.Container as unknown as Record<string, unknown> | undefined;
            if (!c || typeof c !== 'object') return [];
            const preferred = ['Type', 'Tag'];
            const keys = Object.keys(c);
            const head = preferred.filter((k) => keys.includes(k));
            const tail = keys.filter((k) => !head.includes(k));
            return [...head, ...tail];
        },
    },

    methods: {
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

<style lang="scss" scoped>
.description-page {
    max-width: 920px;
    margin: 0 auto;
    padding: 0.5rem 1.25rem 2.75rem;
}

.description-intro {
    margin-bottom: 1.75rem;
    padding: 1.35rem 1.5rem 1.5rem;
    border-radius: 10px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-fill-color-blank, #fff);
    box-shadow: 0 1px 2px rgb(0 0 0 / 4%);
}

.description-intro__title {
    margin: 0 0 0.65rem;
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--el-text-color-primary, #303133);
}

.description-intro__text {
    margin: 0;
    font-size: 14px;
    line-height: 1.65;
    color: var(--el-text-color-regular, #606266);
}

.description-intro__text :deep(a) {
    font-weight: 500;
}

.description-card {
    padding: 1.75rem 2rem 2.25rem;
    border-radius: 12px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-bg-color, #fff);
    box-shadow:
        0 1px 2px rgb(0 0 0 / 4%),
        0 8px 28px rgb(0 0 0 / 6%);
}

.description-form :deep(.el-form-item) {
    margin-bottom: 1.35rem;
}

.description-form :deep(.el-form-item:last-child) {
    margin-bottom: 0;
}

.description-form :deep(.el-form-item__label) {
    font-weight: 500;
    color: var(--el-text-color-regular, #606266);
    padding-right: 16px;
}

.description-form :deep(.el-input__inner),
.description-form :deep(.el-textarea__inner) {
    border-radius: 8px;
}

.description-form :deep(.el-select .el-input__inner) {
    border-radius: 8px;
}

.full-width {
    width: 100%;
}

.description-form__generated :deep(.el-form-item__content) {
    flex: 1;
    min-width: 0;
    line-height: 1.4;
}

.generated-block {
    width: 100%;
    box-sizing: border-box;
    padding: 0.75rem 1.35rem 1.2rem 3rem;
    border-radius: 8px;
    background: var(--el-fill-color-light, #f5f7fa);
    border: 1px solid var(--el-border-color-extra-light, #f2f6fc);
}

.generated-row {
    display: grid;
    grid-template-columns: minmax(90px, 110px) minmax(0, 1fr);
    gap: 8px 18px;
    align-items: center;
    margin-bottom: 1rem;
}

.generated-row:last-child {
    margin-bottom: 0;
}

.generated-row__label {
    margin: 0;
    font-size: 13px;
    font-weight: 500;
    line-height: 1.35;
    color: var(--el-text-color-regular, #606266);
    text-align: right;
    word-break: break-word;
}

.generated-subsection {
    margin-top: 1.1rem;
    padding-top: 1.1rem;
    border-top: 1px dashed var(--el-border-color, #dcdfe6);
}

.generated-subsection__title {
    margin: 0 0 0.85rem;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--el-text-color-secondary, #909399);
}

.generated-subsection .generated-row:last-child {
    margin-bottom: 0;
}

@media (max-width: 640px) {
    .generated-row {
        grid-template-columns: 1fr;
        gap: 6px;
        align-items: stretch;
    }

    .generated-row__label {
        text-align: left;
    }
}

.description-section-label {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 2rem 0 1.25rem;
}

.description-section-label::before,
.description-section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--el-border-color-lighter, #ebeef5);
}

.description-section-label__text {
    flex-shrink: 0;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--el-text-color-secondary, #909399);
}
</style>
