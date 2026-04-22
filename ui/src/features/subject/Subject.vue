<template>
    <div class="subject-page">
        <header class="subject-intro">
            <h2 class="subject-intro__title">Subject mapping</h2>
            <p class="subject-intro__text">
                Please map DICOM subject IDs to BIDS subject IDs. You can also specify session
                (<strong>AcquisitionDate</strong>) mappings for each subject if needed. A mapping table can be
                downloaded at the end for future reference.
            </p>
        </header>

        <div class="subject-layout">
            <section class="subject-card">
                <div class="subject-card__toolbar">
                    <el-dropdown size="small" @command="resetSubjects">
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
                </div>

                <el-table :data="ezbids.subjects" size="small" class="table-align-top subject-table">
                    <el-table-column label="DICOM Patient" width="200">
                        <template #default="scope">
                            <div class="patient-cell">
                                <i class="el-icon-right patient-cell__arrow" />
                                <div class="patient-info">
                                    <p v-for="(info, idx) in scope.row.PatientInfo" :key="idx">
                                        <b>PatientID</b> {{ info.PatientID }}<br />
                                        <b>PatientName</b> {{ info.PatientName }}<br />
                                        <b>PatientBirthDate</b> {{ info.PatientBirthDate || '(not set)' }}<br />
                                        <b>Directory</b> {{ info.file_directory }}<br />
                                    </p>
                                </div>
                            </div>
                        </template>
                    </el-table-column>
                    <el-table-column label="Subject / Session Mappings">
                        <template #default="scope">
                            <div class="mapping-cell">
                                <div style="margin-top: 1rem">
                                    <el-input
                                        v-model.trim="scope.row.subject"
                                        size="small"
                                        @change="validate(scope.row)"
                                    >
                                        <template #prepend>sub-</template>
                                    </el-input>
                                    <div style="margin-top: 4px; line-height: normal">
                                        <el-checkbox
                                            v-model="scope.row.exclude"
                                            title="Exclude all objects from BIDS output for this subject"
                                        >
                                            Exclude this subject
                                        </el-checkbox>
                                    </div>
                                </div>

                                <el-table
                                    :data="scope.row.sessions"
                                    size="mini"
                                    :show-header="false"
                                    class="session-table"
                                >
                                    <el-table-column :span="24">
                                        <template #default="sessionScope">
                                            <el-row :gutter="12">
                                                <el-col :span="24">
                                                    <div style="margin-left: 2rem">
                                                        <div style="display: flex; align-items: center; gap: 0.5rem">
                                                            <b>AcquisitionDate</b>
                                                            {{ sessionScope.row.AcquisitionDate }}
                                                        </div>
                                                        <el-input
                                                            v-model.trim="sessionScope.row.session"
                                                            placeholder="no session"
                                                            size="small"
                                                            @change="validate(scope.row)"
                                                        >
                                                            <template #prepend>ses-</template>
                                                        </el-input>
                                                        <div style="margin-top: 4px; line-height: normal">
                                                            <el-checkbox
                                                                v-model="sessionScope.row.exclude"
                                                                title="Exclude all objects for this session"
                                                                class="session-checkbox"
                                                            >
                                                                Exclude this session
                                                            </el-checkbox>
                                                        </div>
                                                    </div>
                                                </el-col>
                                            </el-row>
                                        </template>
                                    </el-table-column>
                                </el-table>

                                <el-alert
                                    v-for="(error, idx) in scope.row.validationErrors"
                                    :key="idx"
                                    show-icon
                                    :closable="false"
                                    type="error"
                                    :title="error"
                                    class="mapping-error"
                                />
                            </div>
                        </template>
                    </el-table-column>
                </el-table>
            </section>

            <aside class="subject-card json-panel">
                <h3 class="json-panel__title">Subject mapping JSON</h3>
                <pre class="json-panel__content">{{ ezbids.subjects }}</pre>
            </aside>
        </div>
    </div>
</template>

<script lang="ts">
import { mapState } from 'vuex';
import { defineComponent } from 'vue';
import { Subject } from '@/store/store.types';

export default defineComponent({
    data() {
        return {};
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
    computed: {
        ...mapState(['ezbids', 'config']),
    },

    created() {
        console.log('Subject create');
        this.validateAll();
    },

    methods: {
        resetSubjects(command: string) {
            console.log('resetting subjects');
            let sub = 1;
            switch (command) {
                case 'num':
                    this.ezbids.subjects.forEach((s: Subject) => {
                        s.subject = sub.toString().padStart(2, '0');
                        sub++;
                    });
                    break;
                case 'pid':
                    this.ezbids.subjects.forEach((s: Subject) => {
                        const firstInfo = s.PatientInfo[0]; //TODO - should I concatenate all PatientInfo?
                        s.subject = firstInfo.PatientID.replace(/[^0-9a-zA-Z]/g, '');
                    });
                    break;
                case 'pname':
                    this.ezbids.subjects.forEach((s: Subject) => {
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

            if (s.subject.length == 0) {
                //this.$store.commit("addValidationError", {s, error:"subject is a required field"});
                s.validationErrors.push('subject is a required field');
            }

            let cleansub = s.subject.replace(/[^0-9a-zA-Z]/g, '');
            if (s.subject != cleansub) {
                //this.$store.commit("addValidationError", {s, error: "subject contains non alphanumeric characters"});
                s.validationErrors.push('subject contains non alphanumeric characters');
            }
        },

        isValid(cb: (v?: string) => void) {
            this.validateAll();

            let err = undefined;
            this.ezbids.subjects.forEach((s: Subject) => {
                if (s.validationErrors.length > 0) err = 'Please correct all issues';
            });
            return cb(err);
        },
    },
});
</script>

<style lang="scss" scoped>
.subject-page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0.5rem 1.25rem 2.75rem;
}

.subject-intro {
    margin-bottom: 1.5rem;
    padding: 1.35rem 1.5rem 1.5rem;
    border-radius: 10px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-fill-color-blank, #fff);
    box-shadow: 0 1px 2px rgb(0 0 0 / 4%);
}

.subject-intro__title {
    margin: 0 0 0.65rem;
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--el-text-color-primary, #303133);
}

.subject-intro__text {
    margin: 0;
    font-size: 14px;
    line-height: 1.65;
    color: var(--el-text-color-regular, #606266);
}

.subject-layout {
    display: grid;
    grid-template-columns: minmax(0, 3fr) minmax(300px, 2fr);
    gap: 1rem;
    align-items: start;
}

.subject-card {
    padding: 1.25rem;
    border-radius: 12px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-bg-color, #fff);
}

.subject-card__toolbar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 0.9rem;
}

.subject-table {
    width: 100%;
}

.patient-cell {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
}

.patient-cell__arrow {
    margin-top: 2px;
    font-size: 1rem;
    font-weight: 700;
    color: var(--el-text-color-secondary, #909399);
}

.patient-info {
    overflow-wrap: anywhere;

    p {
        margin-top: 0;
        margin-bottom: 5px;
        line-height: 1.4;
    }

    p:not(:first-child) {
        border-top: 1px solid var(--el-border-color-extra-light, #f2f6fc);
        padding-top: 5px;
    }
}

:deep(.el-checkbox__label) {
    font-size: 12px !important;
}

:deep(.el-checkbox) {
    height: 20px !important;
}

.mapping-cell {
    display: flex;
    flex-direction: column;
}

.mapping-error {
    margin-bottom: 0;
}

.session-table {
    padding-top: 0.25rem;
    padding-bottom: 1rem;
}

:deep(.el-table--mini .el-table__cell) {
    padding: 0px !important;
}

:deep(.session-table.el-table::before) {
    display: none;
}

:deep(.session-table .el-table__row > td) {
    border-bottom: none !important;
}

:deep(.subject-table .el-table__body tr:hover > td.el-table__cell) {
    background-color: transparent !important;
}

:deep(.session-table .el-table__body tr:hover > td.el-table__cell) {
    background-color: transparent !important;
}

.json-panel {
    position: sticky;
    top: 16px;
    max-height: calc(80vh);
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.json-panel__title {
    margin: 0 0 0.75rem;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--el-text-color-regular, #606266);
}

.json-panel__content {
    margin: 0;
    flex: 1;
    overflow: auto;
    padding: 0.5rem;
    border-radius: 8px;
    border: 1px solid var(--el-border-color-extra-light, #f2f6fc);
    background: var(--el-fill-color-light, #f5f7fa);
    font-size: 12px;
    line-height: 1.45;
}

el-table {
    border-color: transparent !important;
}

@media (max-width: 1100px) {
    .subject-layout {
        grid-template-columns: 1fr;
    }

    .json-panel {
        position: static;
        max-height: none;
    }

    .json-panel__content {
        max-height: 320px;
    }
}
</style>
