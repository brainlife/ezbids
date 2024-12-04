<template>
    <div>
        <div v-if="!session">
            <h2 style="margin-bottom: 0; margin-top: 0">
                Welcome to <b><span style="letter-spacing: -2px; opacity: 0.5">ez</span>BIDS</b> - an online imaging
                data to BIDS conversion / organizing tool.
            </h2>
            <p style="color: gray; margin-top: 8px">To get started, upload a DICOM (or dcm2niix) dataset.</p>

            <div v-if="!starting">
                <div
                    class="drop-area"
                    :class="{ dragging }"
                    @drop="dropit"
                    @dragleave="dragging = false"
                    @dragover="dragover"
                >
                    <div class="drop-area-backdrop">
                        <b><span style="letter-spacing: -4vh">ez</span>BIDS</b>
                    </div>
                    <div>
                        <b>Drag & Drop DICOM (or dcm2niix) data here to start</b>
                        <br />
                        <br />
                        or
                        <br />
                        <br />
                        <input
                            type="file"
                            webkitdirectory
                            mozdirectory
                            msdirectory
                            odirectory
                            directory
                            multiple
                            style="font-size: 80%; width: 400px; background-color: #fff3; padding: 5px"
                            @change="selectit"
                        />
                    </div>
                </div>

                <div class="Info">
                    <h2 style="margin-bottom: 0">Not sure what to do?</h2>
                    <p style="color: gray; margin-top: 8px">
                        If you are new to ezBIDS, you can learn more by watching our
                        <a style="display: inline" href="https://brainlife.io/docs/tutorial/ezBIDS/" target="_blank"
                            ><b>ezBIDS tutorial</b></a
                        >
                        and taking a look at our
                        <a href="https://brainlife.io/docs/using_ezBIDS/" target="_blank"><b>user documentation</b></a
                        >.
                    </p>
                    <p style="color: gray">
                        If uploading anonymized data, please organize subject data into <i>sub-</i>formatted folder
                        names (e.g. <b>sub-01</b>). If you have multi-session data, place in <i>ses-</i>formatted
                        folders (e.g. <b>ses-A</b>) within the subject folders.
                    </p>
                    <p style="color: gray">See below for a brief ezBIDS tutorial video.</p>
                    <iframe
                        width="640"
                        height="360"
                        src="https://www.youtube.com/embed/L8rWA8qgnpo"
                        title="YouTube video player"
                        frameborder="0"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowfullscreen
                    ></iframe>
                </div>
                <br />
                <br />
                <br />
            </div>

            <div v-if="starting && !promptSignIn">
                <h3>Initializing ...</h3>
            </div>

            <div v-if="starting && promptSignIn">
                <p style="color: orange">
                    The files you are trying to upload are ~{{ formatNumber(total_size / (1024 * 1024 * 1024)) }} GB in
                    size, which is larger than the 4GB limit for ezBIDS edge mode (local processing).
                </p>
                <p>
                    Please
                    <a style="color: blue" href="https://brainlife.io">sign in</a> to continue via ezBIDS server mode.
                </p>
            </div>
        </div>

        <div v-if="session">
            <div v-if="session.status == 'created'">
                <h3 style="margin-top: 0">
                    Uploading
                    <font-awesome-icon icon="spinner" pulse />
                </h3>
                <small>Please do not close or refresh this page until all files are uploaded.</small>
                <div v-if="failed.length > 0">
                    <el-alert type="error"
                        >Permanently failed to upload some files, please email pestilli@utexas.edu for
                        assistance</el-alert
                    >
                    <pre v-for="idx in failed" :key="idx" type="info" style="font-size: 80%">{{ files[idx].path }}</pre>
                </div>

                <p>
                    <small>Total size {{ formatNumber(total_size / (1024 * 1024)) }} MB</small>
                    <small> | {{ files.length }} Files </small>
                    <small> ({{ uploaded.length }} uploaded) </small>
                    <small v-if="ignoreCount > 0">({{ ignoreCount }} ignored) </small>
                    <el-progress
                        status="success"
                        :text-inside="true"
                        :stroke-width="24"
                        :percentage="parseFloat(((uploaded.length / files.length) * 100).toFixed(1))"
                    />
                </p>
                <div v-for="(batch, idx) in batches" :key="idx">
                    <div v-if="batch.status != 'done'" class="batch-stat">
                        <b style="text-transform: uppercase">{{ batch.status }}</b>
                        batch {{ (idx + 1).toString() }}. {{ batch.fileidx.length }} files
                        <span> ({{ formatNumber(batch.size / (1024 * 1024)) }} MB) </span>
                        <div style="height: 20px">
                            <el-progress
                                v-if="batch.evt.total"
                                :status="batchStatus(batch)"
                                :text-inside="true"
                                :stroke-width="15"
                                :percentage="parseFloat(((batch.evt.loaded / batch.evt.total) * 100).toFixed(1))"
                            />
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="['preprocessing', 'uploaded'].includes(session.status)">
                <h3 v-if="session.dicomDone === undefined" style="margin-top: 0">
                    Inflating
                    <font-awesome-icon icon="spinner" pulse />
                </h3>
                <div v-else-if="session.dicomDone < session.dicomCount">
                    <h3>
                        Converting DICOMS to NIfTI
                        <font-awesome-icon icon="spinner" pulse />
                    </h3>
                    <el-progress
                        status="success"
                        :text-inside="true"
                        :stroke-width="24"
                        :percentage="parseFloat(((session.dicomDone * 100) / session.dicomCount).toFixed(1))"
                    />
                    <br />
                </div>
                <h3 v-else>
                    Analyzing
                    <font-awesome-icon icon="spinner" pulse />
                </h3>
                <pre class="status">{{ session.status_msg }}</pre>
                <small
                    >* Depending on the size of your dataset, this process might take several hours. You can shutdown
                    your computer while we process your data (please bookmark the URL for this page to come back to
                    it)</small
                >
            </div>

            <div v-if="session.status == 'failed'">
                <el-alert type="error"
                    >ezBIDS failed.. Please check the Debug logs and contact the ezBIDS team
                    (pestilli@utexas.edu).</el-alert
                >
                <br />
                <pre class="status">{{ session.status_msg }}</pre>
            </div>

            <div v-if="session.pre_finish_date">
                <div v-if="ezbids.notLoaded">
                    <h3 style="margin-top: 0">
                        Loading analysis results
                        <font-awesome-icon icon="spinner" pulse />
                    </h3>
                </div>

                <div v-if="!ezbids.notLoaded && ezbids.objects.length">
                    <h2 style="margin-top: 0">Analysis complete!</h2>
                    <AnalysisErrors />
                    <h3>
                        Object List <small>({{ ezbids.objects.length }})</small>
                    </h3>
                    <p>
                        <small
                            >We have identified the following files (objects) that can be organized into BIDS
                            structure.</small
                        >
                    </p>
                    <div v-for="(object, idx) in ezbids.objects" :key="idx" style="padding-bottom: 2px">
                        <p style="margin: 0">
                            <el-link @click="toggleObject(idx)">
                                <small>
                                    <el-tag size="mini" type="info">{{ idx }}</el-tag>
                                    {{ itemPath(object.items) }}
                                </small>
                            </el-link>
                        </p>
                        <pre v-if="opened.includes(idx)" class="status">{{ object }}</pre>
                    </div>
                </div>
                <div v-if="!ezbids.notLoaded && !ezbids.objects.length">
                    <el-alert type="error"
                        >We couldn't find any objects. Please upload data that contains at least 1 object. Contact the
                        ezBIDS team (pestilli@utexas.edu or https://github.com/brainlife/ezbids/issues) for
                        support</el-alert
                    >
                </div>
            </div>

            <br />
            <!-- ANIBAL-TODO: Not sure how these files will be generated or handled when computing via EDGE. I'm
                 going to hide them for now (when on EDGE) but you can change this to fit the use case -->
            <el-collapse v-if="ezbidsProcessingMode !== 'EDGE'">
                <el-collapse-item title="Debug (Download)">
                    <ul style="list-style: none; padding-left: 0">
                        <el-button
                            style="width: 168px"
                            type="warning"
                            size="mini"
                            @click="downloadFile('preprocess.log')"
                            >preprocess.log</el-button
                        >
                        <el-button type="warning" size="mini" @click="downloadFile('preprocess.err')"
                            >preprocess.err</el-button
                        >
                        <el-button type="warning" size="mini" @click="downloadFile('dcm2niix_error')"
                            >dcm2niix_error</el-button
                        >
                        <el-button type="warning" size="mini" @click="downloadFile('pet2bids_error')"
                            >pet2bids_error</el-button
                        >
                        <el-button type="warning" size="mini" @click="downloadFile('list')">data list</el-button>
                        <el-button type="warning" size="mini" @click="downloadFile('ezBIDS_core.json')"
                            >ezBIDS_core.json</el-button
                        >
                    </ul>

                    <el-button type="info" style="width: 168px" size="mini" @click="dump">Dump state</el-button>
                    <br />

                    <div v-if="ignoredFiles.length">
                        <b>Ignored Files</b>
                        <ul>
                            <li v-for="(file, idx) in ignoredFiles" :key="idx">
                                <pre>{{ file.path }}</pre>
                            </li>
                        </ul>
                    </div>
                </el-collapse-item>
            </el-collapse>
            <br />
            <br />
            <br />
        </div>
    </div>
</template>

<script>
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { formatNumber } from './filters';
import { ElNotification } from 'element-plus';
import { Dcm2niix } from '@niivue/dcm2niix';

import { hasJWT, authRequired } from './lib';

const SIZE_LIMIT_GB = 0.001;

export default defineComponent({
    components: {
        AnalysisErrors: () => import('./components/analysisErrors.vue'),
    },
    data() {
        return {
            dragging: false,
            starting: false, //wait for browser to handle all files
            promptSignIn: false, // if the files to upload are larger than 4GB, we prompt the user to sign in

            total_size: null,
            ignoreCount: 0,
            files: [] /*: FileList*/, //files to be uploaded

            uploaded: [], //index of files that are successfully uploaded
            failed: [], //index of files failed to upload
            batches: [], //object containing information for each batch upload {evt, fileidx}

            opened: [],

            doneUploading: false,

            activeLogs: [],
            list: '',
        };
    },

    computed: {
        ...mapState(['session', 'config', 'ezbids', 'ezbidsProcessingMode']),

        ignoredFiles() {
            let files = [];
            for (let i = 0; i < this.files.length; ++i) {
                let file = this.files[i];
                if (file.ignore) files.push(file);
            }
            return files;
        },
    },

    methods: {
        async downloadFile(fileName) {
            if (!fileName) return;
            try {
                this.api.downloadFile(this.session._id, fileName);
            } catch (e) {
                console.error(e);
                ElNotification({
                    message: 'there was an error downloading the file',
                    type: 'error',
                });
            }
        },

        formatNumber,

        toggleObject(idx) {
            let pos = this.opened.indexOf(idx);
            if (~pos) this.opened.splice(pos, 1);
            else this.opened.push(idx);
        },

        batchStatus(batch) {
            switch (batch.status) {
                case 'done':
                    return 'success';
                case 'failed':
                    return 'exception';
            }
            return null;
        },

        //HTML5 drop event doesn't work unless dragover is handled
        dragover(e /*: DragEvent*/) {
            e.preventDefault();
            this.dragging = true;
        },

        async dropit(e /*: DragEvent*/) {
            e.preventDefault();
            this.dragging = false;
            this.starting = true;

            await this.listDropFiles(e.dataTransfer?.items);
            this.upload();
        },

        async selectit(e /*: Event*/) {
            const target = e.target; /* as HTMLInputElement*/
            this.files = target.files /* as FileList*/;

            // dcm2niix --progress y -v 1 -ba n -z o -d 9 -f 'time-%t-sn-%s' $path

            const dcm2niix = new Dcm2niix();
            await dcm2niix.init();
            const convertedFiles = await dcm2niix.input(target.files).v(1).ba('n').z('o').d(9).f('time-%t-sn-%s').run();

            console.log('convertedFiles', convertedFiles);

            // this.starting = true;
            //this.$nextTick() won't update the UI with starting flag change
            setTimeout(() => {
                for (let file of this.files) {
                    file.path = file.webkitRelativePath;
                }
                // this.upload();
            }, 1000);
        },

        // Unlike file input(directory) selector, I have to do some convoluted thing to get all the files that user drops...
        async listDropFiles(items) {
            this.files = [];

            // Get all the entries (files or sub-directories) in a directory
            // by calling readEntries until it returns empty array
            async function readAllDirectoryEntries(directoryReader) {
                let entries = [];
                //console.log("reading directory entries");
                let readEntries = await readEntriesPromise(directoryReader);
                while (readEntries.length > 0) {
                    entries.push(...readEntries);
                    readEntries = await readEntriesPromise(directoryReader);
                }
                return entries;
            }

            // Wrap readEntries in a promise to make working with readEntries easier
            // readEntries will return only some of the entries in a directory
            // e.g. Chrome returns at most 100 entries at a time
            async function readEntriesPromise(directoryReader) /*: Promise<File[]>*/ {
                try {
                    return await new Promise((resolve, reject) => {
                        directoryReader.readEntries(resolve, reject);
                    });
                } catch (err) {
                    console.error(err);
                }
            }

            async function getFile(fileEntry) /*: Promise<File>*/ {
                try {
                    return await new Promise((resolve, reject) => fileEntry.file(resolve, reject));
                } catch (err) {
                    console.error(err);
                }
            }

            //https://stackoverflow.com/questions/3590058/does-html5-allow-drag-drop-upload-of-folders-or-a-folder-tree
            // Drop handler function to get all files
            let queue = [];
            for (let i = 0; i < items.length; i++) {
                queue.push(items[i].webkitGetAsEntry());
            }

            // Unfortunately dataTransferItemList is not iterable i.e. no forEach
            while (queue.length > 0) {
                let entry = queue.shift();
                if (entry.isFile) {
                    let file = await getFile(entry);
                    // @ts-ignore (we add path variable to store the fullpath)
                    file.path = entry.fullPath.substring(1); //remove / prefix
                    this.files.push(file);
                } else if (entry.isDirectory) {
                    queue.push(...(await readAllDirectoryEntries(entry.createReader())));
                }
            }
        }, //end listDropFiles()

        async upload() {
            //calculate total file size
            this.total_size = 0;
            for (let i = 0; i < this.files.length; ++i) {
                let file = this.files[i];
                this.total_size += file.size;
            }

            // this is due to WASM restrictions but may change in the future with the advent of WASM64
            const totalSizeInGB = this.total_size / (1024 * 1024 * 1024);
            if (totalSizeInGB >= SIZE_LIMIT_GB && authRequired() && !hasJWT()) {
                this.promptSignIn = true;
                return;
            }

            this.starting = false;
            this.doneUploading = false;

            //reset try counters
            for (let i = 0; i < this.files.length; ++i) {
                this.files[i].try = 0;
            }

            //create new session
            const ezbidsProcessingMode = totalSizeInGB >= SIZE_LIMIT_GB ? 'SERVER' : 'EDGE';
            this.$store.commit('setEzBidsProcessingMode', ezbidsProcessingMode);
            try {
                const res = await this.api.createNewSession();
                this.$store.commit('setSession', res);
                this.api.storeFiles(res._id, this.done, {
                    files: this.files,
                    uploaded: this.uploaded,
                    failed: this.failed,
                    ignoreCount: this.ignoreCount,
                    batches: this.batches,
                });
            } catch (e) {
                console.error(e);
                ElNotification({
                    title: 'Could not create a new session, please try again',
                    message: '',
                    type: 'error',
                });
            }
        },

        async done() {
            //we have multiple files uploading concurrently, so the last files will could make this call back
            if (this.doneUploading) return;
            this.doneUploading = true;

            //construct a good dataset description from the file paths
            const f = this.files[0];
            if (f) {
                const tokens = f.path.split('/'); //027_S_5093/HighResHippo/2017-04-28_12_48_14.0/S...
                const desc = tokens[0];
                this.$store.state.ezbids.datasetDescription.Name = desc;
            }
        },

        loadedPercentage(file_id) {
            let file = this.files[file_id];
            return ((file.loaded / file.size) * 100).toFixed(1);
        },

        isValid(cb) {
            //TODO..
            cb();
        },

        dump() {
            var element = document.createElement('a');
            element.setAttribute(
                'href',
                'data:text/plain;charset=utf-8,' + encodeURIComponent(JSON.stringify(this.ezbids, null, 4))
            );
            element.setAttribute('download', 'root.json');
            element.style.display = 'none';
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
        },

        itemPath(items) {
            let str = '';
            items.forEach((item) => {
                if (str == '') str = item.path;
                else {
                    //for subsequent path, skip the parts that's same
                    const strtokens = str.split('.');
                    const pathtokens = item.path.split('.');
                    const unique = [];
                    str += ' / ';
                    for (let i = 0; i < pathtokens.length; ++i) {
                        if (pathtokens[i] == strtokens[i]) continue;
                        else str += '.' + pathtokens[i];
                    }
                }
            });
            return str;
        },
    },
});
</script>

<style lang="scss" scoped>
.drop-area {
    z-index: 0;
    background-color: #0002;
    color: #999;
    padding: 25px;
    padding-top: 100px;
    border-radius: 5px;
    height: 300px;
    box-sizing: border-box;
    font-size: 125%;
    position: relative;
    overflow: hidden;
    text-align: center;
}
.drop-area.dragging {
    background-color: #999;
    color: white;
}
.drop-area-backdrop {
    position: absolute;
    font-size: 25vh;
    opacity: 0.1;
    top: 0;
    left: 0;
    right: 0;
    z-index: -1;
    padding: 30px 0;
    filter: blur(0.5vh);
}
.batch-stat {
    font-family: monospace;
    font-size: 90%;
}

pre.status {
    background-color: #666;
    color: white;
    height: 300px;
    overflow: auto;
    padding: 10px;
    margin-top: 0;
    margin-bottom: 5px;
    border-radius: 5px;
}
</style>
