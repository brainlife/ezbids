<template>
    <div style="padding: 20px;">
        <div v-if="!session">
            <p>
                Welcome to <b><span style="letter-spacing: -2px; opacity: 0.5">ez</span>BIDS</b> - an online imaging data to BIDS conversion / organizing tool.
            </p>
    
            <div v-if="!starting">
                <div class="drop-area" :class="{dragging}"
                    @drop="dropit"
                    @dragleave="dragging = false"
                    @dragover="dragover">
                    <div class="drop-area-backdrop"><b><span style="letter-spacing: -4vh;">ez</span>BIDS</b></div>
                    <div>
                        <b>Drag & Drop DICOM (or dcm2niix) data here to start</b>
                        <br>
                        <br>
                        or
                        <br>
                        <br>
                        <input type="file"
                                webkitdirectory
                                mozdirectory
                                msdirectory
                                odirectory
                                directory
                                multiple
                                @change="selectit" style="font-size: 80%; width: 400px; background-color: #fff3; padding: 5px;"/>
                    </div>
                </div>

                <div class="Info">
                    <h2>Information</h2>
                    <ul style="line-height: 200%;">
                        <li>If you are new to ezBIDS, please read our <a href="https://brainlife.io/docs/using_ezBIDS/" target="_blank" ><b>User documentation</b></a></li>
                        <li>See below for a brief ezBIDS video</li>
                    </ul>
                    <iframe width="640" height="360" src="https://www.youtube.com/embed/mY3_bmt_e80" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
                </div>
                <br>
                <br>
                <br>
            </div>
    
            <div v-if="starting">
                <h3>Initializing ... </h3>
            </div>
        </div>
    
        <div v-if="session">
            <div v-if="session.status == 'created'">
                <p>
                    <h3>
                        Uploading
                        <font-awesome-icon icon="spinner" pulse/>
                    </h3>
                    <small>Please do not close/refresh this page until all files are uploaded.</small>
                </p>
                <div v-if="failed.length > 0">
                    <el-alert type="error">Permanently failed to upload some files</el-alert>
                    <pre type="info" v-for="idx in failed" :key="idx" style="font-size: 80%;">{{files[idx].path}}</pre>
                </div>
    
                <p>
                    <small>Total size {{formatNumber(total_size/(1024*1024))}} MB</small>
                    <small> | {{files.length}} Files </small>
                    <small> ({{uploaded.length}} uploaded) </small>
                    <small v-if="ignoreCount > 0">({{ignoreCount}} ignored) </small>
                    <el-progress status="success"
                        :text-inside="true"
                        :stroke-width="24"
                        :percentage="parseFloat(((uploaded.length/files.length)*100).toFixed(1))"/>
                </p>
                <div v-for="(batch, idx) in batches" :key="idx">
                    <div v-if="batch.status != 'done'" class="batch-stat">
                        <b style="text-transform: uppercase;">{{batch.status}}</b>
                        batch {{(idx+1).toString()}}. {{batch.fileidx.length}} files
                        <span> ({{formatNumber(batch.size/(1024*1024))}} MB) </span>
                        <div style="height: 20px">
                            <el-progress v-if="batch.evt.total"
                                :status="batchStatus(batch)"
                                :text-inside="true" :stroke-width="15"
                                :percentage="parseFloat(((batch.evt.loaded/batch.evt.total)*100).toFixed(1))"/>
                        </div>
                    </div>
                </div>
            </div>
    
            <div v-if="['preprocessing', 'uploaded'].includes(session.status)">
                <h3 v-if="session.dicomDone === undefined">
                    Inflating
                    <font-awesome-icon icon="spinner" pulse/>
                </h3>
                <div v-else-if="session.dicomDone < session.dicomCount">
                    <h3>
                        Converting DICOMS to NIfTI
                        <font-awesome-icon icon="spinner" pulse/>
                    </h3>
                    <el-progress status="success"
                        :text-inside="true"
                        :stroke-width="24"
                        :percentage="parseFloat((session.dicomDone*100 / session.dicomCount).toFixed(1))"/>
                    <br>
                </div>
                <h3 v-else>
                    Analyzing
                    <font-awesome-icon icon="spinner" pulse/>
                </h3>
                <pre class="status">{{session.status_msg}}</pre>
                <small>* Depending on the size of your dataset, this process might take several hours. You can shutdown your computer while we process your data (please bookmark the URL for this page to come back to it)</small>
            </div>
    
            <div v-if="session.status == 'failed'">
                <el-alert type="error">ezBIDS failed.. Please check the Debug logs and contact ezBIDS team.</el-alert>
                <br>
                <pre class="status">{{session.status_msg}}</pre>
            </div>
    
            <div v-if="session.pre_finish_date">
                <div v-if="ezbids.notLoaded">
                    <h3>
                        Loading analysis results
                        <font-awesome-icon icon="spinner" pulse/>
                    </h3>
                </div>
    
                <div v-if="!ezbids.notLoaded && ezbids.objects.length">
                    <h2>Analysis complete!</h2>
                    <AnalysisErrors />
                    <h3>Object List <small>({{ezbids.objects.length}})</small></h3>
                    <p><small>We have identified the following objects that can be organized into BIDS structure.</small></p>
                    <div v-for="(object, idx) in ezbids.objects" :key="idx" style="padding-bottom: 2px;">
                        <p style="margin: 0;">
                            <el-link @click="toggleObject(idx)">
                                <small>
                                    <el-tag size="mini" type="info">{{idx}}</el-tag>
                                    {{itemPath(object.items)}}
                                </small>
                            </el-link>
                        </p>
                        <pre v-if="opened.includes(idx)" class="status">{{object}}</pre>
                    </div>
                </div>
                <div v-if="!ezbids.notLoaded && !ezbids.objects.length">
                   <el-alert type="error">We couldn't find any objects. Please upload data that contains at least 1 object.</el-alert>
                </div>
            </div>
    
            <br>
            <el-collapse>
                <el-collapse-item title="Debug">
                    <ul style="list-style: none; padding-left: 0;">
                        <el-button @click="downloadPreProcess">Download preprocess.log</el-button>
                        <li><a :href="config.apihost+'/download/'+session._id+'/test'">download test</a></li>
                        <li><a :href="config.apihost+'/download/'+session._id+'/preprocess.log'">preprocess.log</a></li>
                        <li><a :href="config.apihost+'/download/'+session._id+'/preprocess.err'">preprocess.err</a></li>
                        <li><a :href="config.apihost+'/download/'+session._id+'/dcm2niix_error'">dcm2niix_error</a></li>
                        <li><a :href="config.apihost+'/download/'+session._id+'/list'">list</a></li>
                        <li><a :href="config.apihost+'/download/'+session._id+'/ezBIDS_core.json'">ezBIDS_core.json</a></li>
                    </ul>
    
                    <el-button @click="dump" size="mini">Dump state</el-button>
                    <br>
    
                    <p v-if="ignoredFiles.length">
                        <b>Ignored Files</b>
                        <ul>
                            <li v-for="(file, idx) in ignoredFiles" :key="idx"><pre>{{file.path}}</pre></li>
                        </ul>
                    </p>
                </el-collapse-item>
            </el-collapse>
            <br>
            <br>
            <br>
        </div>
    </div>
</template>

<script>
import { defineComponent } from 'vue'
import { mapState } from 'vuex'
import { formatNumber } from './filters'
import axios from './axios.instance';
import { ElNotification } from 'element-plus';

export default defineComponent({
    components: {
        AnalysisErrors: () => import('./components/analysisErrors.vue'),
    },
    data() {
        return {
            dragging: false,
            starting: false, //wait for browser to handle all files

            total_size: null,
            ignoreCount: 0,
            files: []/*: FileList*/, //files to be uploaded

            uploaded: [], //index of files that are successfully uploaded
            failed: [], //index of files failed to upload

            batches: [], //object containing information for each batch upload {evt, fileidx}

            opened: [],

            doneUploading: false,

            activeLogs: [],
            list: "",
        }
    },

    mounted() {
        console.log("mounted Upload.vue");
    },
    computed: {
        ...mapState(['session', 'config', 'ezbids']),

        ignoredFiles() {
            let files = [];
            for(let i = 0;i < this.files.length; ++i) {
                let file = this.files[i];
                if(file.ignore) files.push(file);
            }
            return files;
        }
    },

    methods: {
        async downloadPreProcess(fileName) {
            try {
                const res = await axios.get(`${this.config.apihost}/download/${this.session._id}/token`)
                console.log(res);
                const shortLivedJWT = res.data;

                window.location.href = `${this.config.apihost}/download/${this.session._id}/${fileName}?token=${shortLivedJWT}`;
                // axios.get(`${this.config.apihost}/download/${this.session._id}/preprocess.log`).then((res) => {
    
                //     console.log({
                //         headers: res
                //     })
                // }).catch((err) => {
                //     console.log(err)
                // })
    
                // const response = await axios.get(`${this.config.apihost}/download/${this.session._id}/preprocess.log`, { responseType: 'stream' });
                // console.log({response})
            } catch (e) {
                console.error(e)
                ElNotification({
                    message: 'there was an error downloading the file',
                    type: 'error'
                })
            }
        },

        formatNumber,

        toggleObject(idx) {
            let pos = this.opened.indexOf(idx);
            if(~pos) this.opened.splice(pos, 1);
            else this.opened.push(idx);
        },

        batchStatus(batch) {
            switch(batch.status) {
            case "done": return "success";
            case "failed": return "exception";
            }
            return null;
        },

        //HTML5 drop event doesn't work unless dragover is handled
        dragover(e/*: DragEvent*/) {
            e.preventDefault();
            this.dragging = true;
        },

        async dropit(e/*: DragEvent*/) {
            e.preventDefault();
            this.dragging = false;
            this.starting = true;

            //I can't wrap this around timeout because chrome won't allow accessing dataTransfer.items outside dropevent context for security reason
            await this.listDropFiles(e.dataTransfer?.items);
            this.upload();
        },

        selectit(e/*: Event*/) {
            const target = e.target/* as HTMLInputElement*/;
            this.files = target.files/* as FileList*/;

            this.starting = true;
            //this.$nextTick() won't update the UI with starting flag change
            setTimeout(()=>{
                for(let file of this.files) {
                    file.path = file.webkitRelativePath;
                }
                this.upload();
            }, 1000);
        },

        // Unlike file input(directory) selector, I have to do some convoluted thing to get all the files that user drops...
        async listDropFiles(items) {
            this.files = [];

            console.log("listDropFiles");
            // console.dir(items);

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
            async function readEntriesPromise(directoryReader)/*: Promise<File[]>*/ {
                try {
                    return await new Promise((resolve, reject) => {
                        directoryReader.readEntries(resolve, reject);
                    });
                } catch (err) {
                    console.error(err);
                }
            }

            async function getFile(fileEntry)/*: Promise<File>*/ {
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
                    queue.push(...await readAllDirectoryEntries(entry.createReader()));
                }
            }
        },  //end listDropFiles()

        async upload() {
            this.starting = false;
            this.doneUploading = false;

            //calculate total file size
            this.total_size = 0;
            for(let i = 0;i < this.files.length;++i) {
                let file = this.files[i];
                this.total_size += file.size;
            }

            //reset try counters
            for(let i = 0;i < this.files.length;++i) {
                this.files[i].try = 0;
            }

            //create new session
            const res = await axios.post(`${this.config.apihost}/session`, {
                headers: { 'Content-Type': 'application/json' }
            })
            console.log("created new session");
            this.$store.commit('setSession', await res.data);
            this.processFiles();
        },

        processFiles() {
            //find next files to upload
            let data = new FormData();
            let fileidx = [];
            let batchSize = 0;

            for(let i = 0;i < this.files.length;++i) {
                let file = this.files[i];
                if(this.uploaded.includes(i)) continue;
                if(file.uploading) continue;
                if(file.ignore) continue;
                if(file.try > 5) {
                    if(!this.failed.includes(i)) this.failed.push(i);
                    continue; //TODO we should abort upload?
                }
                batchSize += file.size;

                //limit batch size (3000 files causes network error - probably too many?)
                if(fileidx.length > 0 && (fileidx.length >= 500 || batchSize > 1024*1014*300)) break;

                //let's proceed!
                file.uploading = true;
                fileidx.push(i);
                data.append("files", file);

                //file doesn't contains the real path and lastModifiedDate. I need to pass this separately
                data.append("paths", file.path);
                data.append("mtimes", file.lastModified);
            }

            if(fileidx.length == 0) {
                console.log("no more files to process.");
                return; //all done!
            }

            //prepare a batch
            let batch = {fileidx, evt: {}, status: "uploading", size: batchSize};
            this.batches.push(batch);

            function doSend() {
                axios.post(this.config.apihost+'/upload-multi/'+this.session._id, data, {
                    onUploadProgress: evt=>{
                        //count++;
                        batch.evt = evt;
                    }
                }).then(res=>{
                    let msg = res.data;
                    if(msg == "ok") {
                        batch.status = "done";
                        fileidx.forEach(idx=>{
                            this.uploaded.push(idx);
                        });

                        if(this.uploaded.length+this.ignoreCount == this.files.length) {
                            console.log("upload completed.. calling doneUploading");
                            this.done();
                        } else {
                            //handle next batch
                            this.processFiles();
                        }
                    } else {
                        //server side error?
                        batch.status = "failed";
                        console.error(res);
                    }
                }).catch(err=>{
                    console.dir(err);
                    batch.status = "failed";
                    //retry these files on a different batch
                    fileidx.forEach(idx=>{
                        this.files[idx].try++;
                    });
                    setTimeout(this.processFiles, 1000*13);
                }).then(()=>{
                    fileidx.forEach(idx=>{
                        this.files[idx].uploading = false;
                    });
                });

                //see how many batches we are currently uploading
                let uploadingBatches = this.batches.filter(b=>b.status == "uploading");
                if(uploadingBatches.length < 4) {
                    setTimeout(this.processFiles, 1000*3);
                }
            }

            doSend.call(this);
        },

        async done() {
            //we have multiple files uploading concurrently, so the last files will could make this call back
            if(this.doneUploading) return;
            this.doneUploading = true;

            //mark the session as uploaded
            await axios.patch(`${this.config.apihost}/session/uploaded/${this.session._id}`, {
                headers: { 'Content-Type': 'application/json' }
            })

            //construct a good dataset description from the file paths
            const f = this.files[0];
            if(f) {
                console.dir(f.path);
                const tokens = f.path.split("/"); //027_S_5093/HighResHippo/2017-04-28_12_48_14.0/S...
                const desc = tokens[0];
                this.$store.state.ezbids.datasetDescription.Name = desc;
            }
        },

        loadedPercentage(file_id) {
            let file = this.files[file_id];
            return ((file.loaded / file.size)*100).toFixed(1);
        },

        isValid(cb) {
            //TODO..
            cb();
        },

        dump() {
            var element = document.createElement('a');
            element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(JSON.stringify(this.ezbids, null, 4)));
            element.setAttribute('download', "root.json");
            element.style.display = 'none';
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
        },

        itemPath(items) {
            let str = "";
            items.forEach(item=>{
                if(str == "") str = item.path;
                else {
                    //for subsequent path, skip the parts that's same
                    const strtokens = str.split(".");
                    const pathtokens = item.path.split(".");
                    const unique = [];
                    str += " / ";
                    for(let i = 0;i < pathtokens.length; ++i) {
                        if(pathtokens[i] == strtokens[i]) continue;
                        else str += "."+pathtokens[i];
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
