<template>
    <div style="padding: 20px">
        <p>You can store metadata/phenotypical data for each participant in this dataset.</p>
        <p>Please skip this step if you do not need to store any phenotypical data.</p>
        <h5>Phenotype Columns</h5>
        <small>Define phenotypical keys stored for this study (recommended).</small>
        <br /><br />
        <el-form>
            <div v-for="(column, idx) in ezbids.participantsColumn" :key="idx" class="columnEditor">
                <span style="float: right">
                    <el-button type="danger" size="mini" @click="remove(idx)"><Remove style="width: 16px" /></el-button>
                </span>
                <b>{{ idx }}</b>
                <br />
                <br clear="both" />
                <el-form-item label="Description">
                    <el-input v-model="column.Description" type="textarea" placeholder="Description" size="mini" />
                </el-form-item>
                <el-form-item label="Units">
                    <el-input v-model="column.Units" placeholder="Units" size="mini" />
                </el-form-item>
                <el-form-item label="Levels">
                    <small>TODO.. (levels)</small>
                </el-form-item>
            </div>
            <span class="columnEditor" style="width: 200px">
                <el-input v-model="newcolumn" placeholder="Add New Column" size="mini">
                    <template #append>
                        <el-button type="primary" @click="addNewColumn">Add</el-button>
                    </template>
                </el-input>
                <div>
                    <a
                        href="https://bids-specification.readthedocs.io/en/stable/03-modality-agnostic-files.html#participants-file"
                        target="_blank"
                        >See here for suggestions</a
                    >
                </div>
            </span>
        </el-form>

        <br clear="both" />

        <h5>participants.tsv</h5>
        <small>Enter phenotypical data associated with each participant.</small>
        <br /><br />
        <div style="width: 100%">
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
    </div>
</template>

<script lang="ts">
import { mapState } from 'vuex';
import { defineComponent } from 'vue';

import { OrganizedSubject } from './store';
import { validateParticipantsInfo } from './libUnsafe';

//element-plus icons are bad .. replace it with fontawesome
// @ts-ignore
import { Remove } from '@element-plus/icons/lib';

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
        this.ezbids._organized.forEach((o: OrganizedSubject) => {
            if (!this.ezbids.participantsInfo[o.subject_idx]) this.ezbids.participantsInfo[o.subject_idx] = {};
        });
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

        remove(idx: number) {
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
            let errors = validateParticipantsInfo(this.ezbids);
            if (errors.length) {
                for (const e of errors) {
                    return cb(e);
                }
            }
            cb();
        },
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
    text-align: center;
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
