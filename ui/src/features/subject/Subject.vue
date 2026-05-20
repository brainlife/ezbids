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
            <section class="subject-card subject-card--table">
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

                <div class="subject-table-wrap">
                    <el-table :data="ezbids.subjects" size="small" class="table-align-top subject-table">
                        <el-table-column label="DICOM Patient" min-width="160" width="180">
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
                        <el-table-column label="BIDS subject" min-width="160">
                            <template #default="scope">
                                <div class="subject-cell">
                                    <div class="subject-cell__exclude">
                                        <el-checkbox
                                            v-model="scope.row.exclude"
                                            title="Exclude all objects from BIDS output for this subject"
                                        >
                                            Exclude this subject
                                        </el-checkbox>
                                    </div>
                                    <el-input
                                        v-model.trim="scope.row.subject"
                                        size="small"
                                        @change="validate(scope.row)"
                                    >
                                        <template #prepend>sub-</template>
                                    </el-input>
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
                        <el-table-column label="Sessions" min-width="160">
                            <template #default="scope">
                                <div v-if="scope.row.sessions?.length" class="session-list">
                                    <div
                                        v-for="(session, sIdx) in scope.row.sessions"
                                        :key="`${session.AcquisitionDate}-${sIdx}`"
                                        class="session-item"
                                    >
                                        <div class="session-item__exclude">
                                            <el-checkbox
                                                v-model="session.exclude"
                                                title="Exclude all objects for this session"
                                                class="session-checkbox"
                                            >
                                                Exclude this session
                                            </el-checkbox>
                                        </div>
                                        <el-input
                                            v-model.trim="session.session"
                                            placeholder="no session"
                                            size="small"
                                            @change="validate(scope.row)"
                                        >
                                            <template #prepend>ses-</template>
                                        </el-input>
                                        <div class="session-item__date">
                                            AcquisitionDate: {{ session.AcquisitionDate }}
                                        </div>
                                    </div>
                                </div>
                                <span v-else class="session-list__empty">No sessions</span>
                            </template>
                        </el-table-column>
                    </el-table>
                </div>
            </section>

            <aside class="subject-card json-panel">
                <h3 class="json-panel__title">Subject mapping JSON</h3>
                <pre class="status">{{ ezbids.subjects }}</pre>
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
    width: 100%;
    max-width: min(1680px, 100%);
    margin: 0 auto;
    padding: 0.5rem 1.25rem 2.75rem;
    box-sizing: border-box;
    overflow-x: hidden;
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
    grid-template-columns: 1fr;
    gap: 1rem;
    align-items: start;
    min-width: 0;
}

@media (min-width: 1500px) {
    .subject-layout {
        grid-template-columns: minmax(0, 3fr) minmax(360px, 2fr);
    }
}

.subject-card {
    min-width: 0;
    padding: 1.25rem;
    border-radius: 12px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-bg-color, #fff);
}

.subject-card--table {
    overflow: hidden;
}

.subject-table-wrap {
    width: 100%;
    max-width: 100%;
    overflow-x: auto;
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
    vertical-align: top;
}

.patient-cell__arrow {
    margin-top: 2px;
    font-size: 1rem;
    font-weight: 700;
    color: var(--el-text-color-secondary, #909399);
}

.patient-info {
    overflow-wrap: anywhere;
    padding: 0px;
    vertical-align: top;

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

.subject-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;
    vertical-align: top;
}

.subject-cell__exclude {
    line-height: normal;
}

.mapping-error {
    margin-top: 4px;
    margin-bottom: 0;
}

.session-list {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.session-list__empty {
    font-size: 12px;
    color: var(--el-text-color-placeholder, #c0c4cc);
}

.session-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-bottom: 0.75rem;
}

.session-item:last-child {
    padding-bottom: 0;
    border-bottom: none;
}

.session-item__date {
    margin: 4px 0;
    font-size: 12px;
    line-height: 1.35;
    overflow-wrap: anywhere;
}

.session-item__exclude {
    line-height: normal;
}

:deep(.subject-table .el-table__body tr:hover > td.el-table__cell) {
    background-color: transparent !important;
}

:deep(td.el-table__cell) {
    vertical-align: top;
}

.json-panel {
    position: static;
    max-height: none;
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

.json-panel pre.status {
    max-height: 320px;
    min-height: 200px;
}

pre.status {
    flex: 1;
    margin: 0;
    padding: 10px;
    border-radius: 5px;
    background-color: #666;
    color: #fff;
    overflow: auto;
    word-break: break-all;
    min-height: 320px;
}

el-table {
    border-color: transparent !important;
}

@media (min-width: 1500px) {
    .json-panel {
        position: sticky;
        top: 16px;
        max-height: calc(80vh);
    }

    .json-panel pre.status {
        max-height: none;
        min-height: 320px;
    }
}
</style>
