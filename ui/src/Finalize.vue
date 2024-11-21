<template>
    <div style="max-width: calc(100vw - 260px - 4rem - 2rem);">
        <div v-if="session.status == 'analyzed' || session.status == 'defaced'">
            <p style="margin-top: 0">
                Your dataset is now ready to be converted to BIDS! Please click the button below to generate BIDS
                structure.
            </p>
            <p>
                <el-checkbox v-model="ezbids.includeExcluded">
                    Save all acquisitions set to 'exclude' in an excluded directory in output BIDS structure
                </el-checkbox>
            </p>
            <br />
            <el-button type="success" @click="finalize">Finalize</el-button>
        </div>

        <div
            v-else-if="session.status == 'finalized' || (session.finalize_begin_date && !session.finalize_finish_date)"
        >
            <h3>
                Converting to BIDS
                <font-awesome-icon icon="spinner" pulse />
            </h3>
            <p>
                <small
                    ><i>{{ session.status_msg }}</i></small
                >
            </p>
        </div>

        <div v-else-if="session.finalize_finish_date">
            <div class="download">
                <br />
                <el-button type="success" style="float: right" size="small" @click="session.status = 'analyzed'"
                    >Rerun Finalize Step</el-button
                >
                <h3 style="margin-top: 0">All Done!</h3>
                <p>Please download the BIDS formatted data to your local computer</p>
                <el-button
                    style="width: 250px"
                    type="primary"
                    @click="download(`bids/${ezbids.datasetDescription.Name}`)"
                    >Download BIDS</el-button
                >
                <el-button style="width: 250px" type="primary" @click="download(`finalized.json`)"
                    >Download configuration/template</el-button
                >
                <p>Or send the dataset to other cloud resources.</p>
                <p>
                    <el-dropdown v-if="hasAuth">
                        <el-button style="margin-right: 10px">
                            Send to <b>Brainlife.io</b>&nbsp;
                            <font-awesome-icon :icon="['fas', 'angle-down']" />
                        </el-button>
                        <template #dropdown>
                            <el-dropdown-menu>
                                <el-dropdown-item @click="sendBrainlife()">Send to brainlife</el-dropdown-item>
                                <el-dropdown-item @click="sendBrainlife('DWI')"
                                    >Send to brainlife and run DWI Pipeline</el-dropdown-item
                                >
                            </el-dropdown-menu>
                        </template>
                    </el-dropdown>
                    <el-button @click="sendOpenneuro">Send to <b>OpenNeuro</b></el-button>
                </p>

                <p style="background-color: #0001; padding: 20px; padding-top: 10px">
                    If you have re-named the original DICOM patient names for your BIDS subject/session names, you can
                    download the mapping file.
                    <el-button type="text" @click="downloadSubjectMapping">Download Subject Mapping (.json)</el-button>
                    <br />
                    <small
                        >* may contain sensitive PHI data. Please make sure to store the mapping file in a secure
                        location.</small
                    >
                </p>

                <h3>Citation</h3>
                <div style="background-color: #0001; padding: 20px; padding-top: 10px">
                    <p class="citation">
                        Levitas, D., Hayashi, S., Vinci-Booher, S., Heinsfeld, A., Bhatia, D., Lee, N., ... & Pestilli,
                        F. (2024). ezBIDS: Guided standardization of neuroimaging data interoperable with major data
                        archives and platforms. Scientific data, 11(1), 179.
                        <a href="https://doi.org/10.1038/s41597-024-02959-0" target="_blank"
                            >https://doi.org/10.1038/s41597-024-02959-0</a
                        >
                    </p>
                </div>
            </div>

            <el-row>
                <el-col :span="12">
                    <h4>BIDS Structure</h4>
                    <showfile path="tree.log" style="margin-right: 15px" :tall="true" />
                </el-col>
                <el-col :span="12">
                    <h4>bids-validator output</h4>
                    <showfile path="validator.log" :tall="true" />
                </el-col>
            </el-row>
        </div>

        <div v-if="session.status == 'failed'">
            <p>Failed to convert to BIDS</p>
            <el-button type="success" style="float: right" size="small" @click="finalize"
                >Rerun Finalize Step</el-button
            >
            <p>
                <small
                    ><i>{{ session.status_msg }}</i></small
                >
            </p>
        </div>

        <br />
        <br />
        <h4>Debugging</h4>
        <el-collapse v-model="activeLogs">
            <el-collapse-item v-if="session.status == 'finished'" title="BIDS Conversion Log" name="bids.log">
                <showfile path="bids.log" />
            </el-collapse-item>
            <el-collapse-item v-if="session.status == 'finished'" title="BIDS Conversion Error Log" name="bids.err">
                <showfile path="bids.err" />
            </el-collapse-item>
            <el-collapse-item title="Session" name="session">
                <pre class="text">{{ session }}</pre>
            </el-collapse-item>
        </el-collapse>
        <br />
        <br />
    </div>
</template>

<script lang="ts">
import { mapState } from 'vuex';
import { defineComponent } from 'vue';
import showfile from './components/showfile.vue';
import axios from './axios.instance';

import { ElNotification } from 'element-plus';
import { hasAuth } from './lib';

export default defineComponent({
    components: {
        showfile,
    },

    data() {
        return {
            submitting: false, //prevent double submit
            activeLogs: [],
        };
    },

    computed: {
        ...mapState(['ezbids', 'config', 'bidsSchema', 'session', 'events']),
        hasAuth() {
            return hasAuth();
        },
    },

    mounted() {
        //TODO - update this to do this on demand
        //this.rerun();
        //this.finalize();
    },

    methods: {
        finalize() {
            this.session.status = 'finalized';
            delete this.session.finalize_begin_date;
            delete this.session.finalize_finish_date;

            this.submitting = true;
            this.dofinalize((err: string | null) => {
                if (err)
                    ElNotification({
                        title: 'Failed',
                        message: 'Failed to finalize:' + err,
                    });
                if (err) console.error(err);
                this.submitting = false;
                this.$store.dispatch('loadSession', this.session._id);
            });
        },

        dofinalize(cb: (err: string | null) => void) {
            //TODO - why can't server just look up the bids schema by itself!?
            //mapping between things like like "subject" to "sub"
            const entityMappings = {} as { [key: string]: string };
            for (const key in this.bidsSchema.entities) {
                entityMappings[key] = this.bidsSchema.entities[key].entity;
            }

            axios
                .post(`${this.config.apihost}/session/${this.session._id}/finalize`, {
                    //basically we just need everything except _organized

                    //we store these so we can reload the session later
                    subjects: this.ezbids.subjects,
                    series: this.ezbids.series,
                    defacingMethod: this.ezbids.defacingMethod,
                    includeExcluded: this.ezbids.includeExcluded,

                    //things that convert.ts uses
                    objects: this.ezbids.objects, //most important thing that convert.ts needs
                    BIDSURI: this.ezbids.BIDSURI,
                    events: this.ezbids.events,
                    entityMappings, //helps with convert
                    datasetDescription: this.ezbids.datasetDescription,
                    readme: this.ezbids.readme,
                    participantsColumn: this.ezbids.participantsColumn,
                    participantInfo: this.ezbids.participantsInfo,
                })
                .then((res) => {
                    if (cb) cb(res.data === 'ok' ? null : res.data);
                });
        },

        /*
        rerun() {
            //fake it to make it looks like we haven't finalized yet.
            this.session.status = "finalized";
            delete this.session.finalize_begin_date;
            delete this.session.finalize_finish_date;
        },
        */

        async download(fileName: string) {
            if (!fileName) return;
            try {
                const res = await axios.get(`${this.config.apihost}/download/${this.session._id}/token`);
                const shortLivedJWT = res.data;

                window.location.href = `${this.config.apihost}/download/${this.session._id}/${fileName}?token=${shortLivedJWT}`;
            } catch (e) {
                console.error(e);
                ElNotification({
                    message: 'there was an error downloading the file',
                    type: 'error',
                });
            }
        },

        downloadSubjectMapping() {
            this.downloadMapping(JSON.stringify(this.ezbids.subjects, null, 2), 'subject_mappings.json');
        },

        //un-refactor this?
        downloadMapping(data: any, name: string) {
            const blob = new Blob([data], { type: 'application/json' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = name;
            link.click();
            URL.revokeObjectURL(link.href);
        },

        sendBrainlife(pipeline?: 'DWI') {
            const pipelineString = pipeline ? `&pipeline=${pipeline}` : '';
            window.open(
                `https://brainlife.io/projects#ezbids=${this.session._id}${pipelineString}`,
                `_brainlife.${this.session._id}`
            );
        },

        async sendOpenneuro() {
            try {
                const res = await axios.get(`${this.config.apihost}/download/${this.session._id}/token`);
                const shortLivedJWT = res.data;

                const url = `${this.config.apihost}/download/${this.session._id}/bids/${this.ezbids.datasetDescription.Name}?token=${shortLivedJWT}`;

                const fullurl = new URL(url, document.baseURI).href;
                window.open('https://openneuro.org/import?url=' + encodeURI(fullurl));

            } catch (e) {
                console.error(e);
                ElNotification({
                    message: 'there was an error downloading the data',
                    type: 'error',
                });
            }
        },

        isValid(cb: (err?: string) => void) {
            if (this.session.status != 'finished') return cb('Please finalize the page first');
            cb();
        },
    },
});
</script>

<style lang="scss" scoped>
.download {
    border-radius: 10px;
    background-color: #eee;
    padding: 20px;
    font-size: 85%;
}
.mappings p {
    cursor: pointer;
    color: #409eff;
}
.mappings p:hover {
    text-decoration: underline;
}
p.btn {
    background-color: white;
    padding: 5px;
    border-radius: 4px;
    display: inline-block;
    transition: background-color 0.3s;
    padding: 5px 10px;
}
p.btn:hover {
    background-color: rgb(103, 194, 58);
    color: white;
    cursor: pointer;
}
</style>
