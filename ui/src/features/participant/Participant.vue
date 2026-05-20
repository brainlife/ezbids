<template>
    <div class="participant-page">
        <header class="participant-intro">
            <h2 class="participant-intro__title">Participant Metadata</h2>
            <p class="participant-intro__text">
                You can store metadata and phenotypical data for each participant in this dataset.
            </p>
            <p class="participant-intro__text">
                Skip this step if you do not wish to include participant-level phenotypical information.
            </p>
        </header>

        <section class="participant-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start">
                <div class="section-head">
                    <h3 class="section-title">Phenotype Columns</h3>
                    <small class="section-subtitle"
                        >Define phenotypical keys stored for this study (recommended).</small
                    >
                </div>
                <div>
                    <div style="margin-bottom: 4px">
                        <el-input v-model="newcolumn" placeholder="Add New Column" size="mini">
                            <template #append>
                                <el-button type="primary" @click="addNewColumn">Add</el-button>
                            </template>
                        </el-input>
                    </div>
                    <a
                        class="column-editor__link"
                        href="https://bids-specification.readthedocs.io/en/stable/03-modality-agnostic-files.html#participants-file"
                        target="_blank"
                    >
                        See BIDS suggestions
                    </a>
                </div>
            </div>

            <el-form label-width="92px" class="column-editor-form">
                <div class="column-grid">
                    <div v-for="(column, idx) in ezbids.participantsColumn" :key="idx" class="column-editor">
                        <div class="column-editor__head">
                            <b>{{ idx }}</b>
                            <el-button type="danger" size="mini" @click="remove(idx)">
                                <Remove style="width: 16px" />
                            </el-button>
                        </div>
                        <el-form-item label="Description">
                            <el-input
                                v-model="column.Description"
                                type="textarea"
                                placeholder="Description"
                                size="mini"
                            />
                        </el-form-item>
                        <el-form-item label="Units">
                            <el-input v-model="column.Units" placeholder="Units" size="mini" />
                        </el-form-item>
                        <!-- <el-form-item label="Levels">
                            <small>TODO.. (levels)</small>
                        </el-form-item> -->
                    </div>
                </div>
            </el-form>
        </section>

        <section class="participant-card">
            <div class="section-head">
                <h3 class="section-title">participants.tsv</h3>
                <small class="section-subtitle">Enter phenotypical data associated with each participant.</small>
            </div>

            <div class="table-wrap">
                <table class="phenotype">
                    <thead>
                        <tr>
                            <th>participant_id</th>
                            <th v-for="(column, key) in ezbids.participantsColumn" :key="key">
                                {{ key }}
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="subject_idx in finalSubs" :key="subject_idx">
                            <th>{{ 'sub-' + ezbids.subjects[subject_idx].subject }}</th>
                            <td v-for="(column, key) in ezbids.participantsColumn" :key="key">
                                <el-input v-model.trim="ezbids.participantsInfo[subject_idx][key]" size="mini" />
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>
    </div>
</template>

<script lang="ts">
import { mapState } from 'vuex';
import { defineComponent } from 'vue';
// import { updateParticipantsInfo } from './libUnsafe';

//element-plus icons are bad .. replace it with fontawesome
// @ts-ignore
import { Remove } from '@element-plus/icons/lib';
import { OrganizedSubject } from '@/store/store.types';

export default defineComponent({
    components: {
        Remove,
    },

    data() {
        return {
            newcolumn: '',
        };
    },

    computed: {
        ...mapState(['ezbids', 'config']),
        //...mapGetters(['findSubjectFromString']),

        // //only show subjects that are really used (not excluded)
        // finalSubs() {
        //     let finalSubs: any = [];
        //     this.ezbids._organized.forEach((sub: OrganizedSubject) => {
        //         let use = false;
        //         sub.sess.forEach((ses) => {
        //             if (ses.objects.some((o) => !o._exclude)) use = true;
        //         });
        //         if (use) finalSubs.push({ subIdx: sub.subject_idx, subID: sub.sess[0].objects[0]._entities.subject });
        //     });
        //     console.log('finalSubs', finalSubs);
        //     return finalSubs;
        // },

        //only show subjects that are really used (not excluded)
        finalSubs() {
            let finalSubs = [] as number[];
            this.ezbids._organized.forEach((sub: OrganizedSubject) => {
                let use = false;
                sub.sess.forEach((ses) => {
                    if (ses.objects.some((o) => !o._exclude)) use = true;
                });
                if (use) finalSubs.push(sub.subject_idx);
            });
            return finalSubs;
        },
    },

    created() {
        //initialize
        // TODO: don't need this I think if we're updating participants Info due to user changes in UI.
        this.ezbids._organized.forEach((o: OrganizedSubject) => {
            if (!this.ezbids.participantsInfo[o.subject_idx]) this.ezbids.participantsInfo[o.subject_idx] = {};
        });
        // this.ezbids.participantsInfo = updateParticipantsInfo(this.ezbids);
    },

    methods: {
        addNewColumn() {
            if (!this.newcolumn) return;
            if (this.ezbids.participantsColumn && this.ezbids.participantsColumn[this.newcolumn]) return;

            this.ezbids.participantsColumn[this.newcolumn] = {
                Description: '',
                Units: '',
                Levels: {},
            };
            this.newcolumn = '';
        },

        remove(idx: string | number) {
            delete this.ezbids.participantsColumn[idx];
        },

        //TODO
        validate() {
            console.log('todo - validate participant');
        },

        // isValid(cb: (v?: string)=>void) {
        //     this.validate();
        //     cb();
        // }

        isValid(cb: (v?: string) => void) {
            this.validate();
            // let errors = validateParticipantsInfo(this.ezbids);
            // if (errors.length) {
            //     for (const e of errors) {
            //         return cb(e);
            //     }
            // }
            cb();
        },
    },
});
</script>

<style lang="scss" scoped>
.participant-page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0.5rem 1.25rem 2.75rem;
}

.participant-intro {
    margin-bottom: 1.5rem;
    padding: 1.35rem 1.5rem 1.5rem;
    border-radius: 10px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-fill-color-blank, #fff);
    box-shadow: 0 1px 2px rgb(0 0 0 / 4%);
}

.participant-intro__title {
    margin: 0 0 0.65rem;
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--el-text-color-primary, #303133);
}

.participant-intro__text {
    margin: 0.45rem 0 0;
    font-size: 14px;
    line-height: 1.6;
    color: var(--el-text-color-regular, #606266);
}

.participant-card {
    padding: 1.1rem 1.25rem;
    border-radius: 12px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-bg-color, #ffffff);
    margin-bottom: 1rem;
}

.section-head {
    margin-bottom: 2rem;
}

.section-title {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
}

.section-subtitle {
    display: block;
    margin-top: 0.35rem;
    color: var(--el-text-color-secondary, #909399);
}

.column-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
}

.column-editor {
    background: #ffffff;
    border: 1px solid var(--el-border-color-extra-light, #f2f6fc);
    border-radius: 8px;
    padding: 12px;
}

.column-editor__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    padding: 0 4px;
}

.column-editor--add {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 8px;
    min-height: 180px;
    border: 2px solid lightblue;
}

.column-editor__link {
    font-size: 12px;
}

.column-editor-form :deep(.el-form-item) {
    margin-bottom: 8px;
}

.column-editor-form :deep(.el-form-item__label) {
    text-align: right;
    color: var(--el-text-color-secondary, #909399);
}

.column-editor-form :deep(.el-form-item__content) {
    min-width: 0;
}

.table-wrap {
    overflow-x: auto;
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
    padding: 6px 10px;
    white-space: nowrap;
}
</style>
