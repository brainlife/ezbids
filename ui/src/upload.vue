<template>
<div v-if="$root.currentPage.id == 'upload'" style="padding: 20px;">
    <div v-if="!$root.session">
        <p>
            Welcome to the <b><span style="letter-spacing: -2px; opacity: 0.5">ez</span>BIDS</b> - an online DICOM to BIDS conversion / organizing tool. 
        </p>

        <div class="drop-area" :class="{dragging}" v-if="!starting"
            @drop="dropit" 
            @dragleave="dragging = false" 
            @dragover="dragover">
            <center class="drop-area-backdrop"><b><span style="letter-spacing: -4vh;">ez</span>BIDS</b></center>
            <center>
                <b>Drag & Drop a DICOM folder here to start</b>
                <br>
                <br>
                or
                <input type="file"
                        webkitdirectory 
                        mozdirectory 
                        msdirectory 
                        odirectory 
                        directory 
                        multiple 
                        @change="selectit"/>
            </center>
        </div>

        <div v-if="starting">
            <h3>Initializing..</h3>
        </div>
    </div>

    <div v-if="$root.session">

        <div v-if="$root.session.status == 'created'">
            <h3>Uploading ...</h3>

            <div v-if="failed.length > 0">
                <el-alert type="error">Permanently failed to upload some files</el-alert>
                <pre type="info" v-for="idx in failed" :key="idx" style="font-size: 80%;">{{files[idx].path}}</pre>
            </div>

            <p>
                <small>Total size {{(total_size/(1024*1024))|formatNumber}} MB</small>
                <small> | {{files.length}} Files </small>
                <small> ({{uploaded.length}} done) </small>
                <el-progress status="success" 
                    :text-inside="true" 
                    :stroke-width="24" 
                    :percentage="parseFloat(((uploaded.length/files.length)*100).toFixed(1))"/>
            </p>
            <div v-for="(batch, bid) in batches" :key="bid">
                <div v-if="batch.status != 'done'" class="batch-stat">
                    batch {{bid+1}}. {{batch.fileidx.length}} files 
                    <span> ({{(batch.size/(1024*1024))|formatNumber}} MB) </span>
                    <b>{{batch.status}}</b> 
                    <div style="height: 20px">
                        <el-progress v-if="batch.evt && batch.evt.total > 0"
                            :status="batchStatus(batch)"
                            :text-inside="true" :stroke-width="15"
                            :percentage="parseFloat(((batch.evt.loaded/batch.evt.total)*100).toFixed(1))"/>
                    </div>
                </div>
            </div>
            <div class="page-action">
                <el-button type="secondary" @click="$root.reset()">Cancel</el-button>
            </div>
        </div>

        <div v-if="['preprocessing', 'uploaded'].includes($root.session.status)">
            <div v-if="$root.session.dicomDone !== undefined && $root.session.dicomDone < $root.session.dicomCount">
                <h3>Converting dicoms to nifti ...</h3>
                <el-progress status="success"
                    :text-inside="true" 
                    :stroke-width="24" 
                    :percentage="($root.session.dicomDone / $root.session.dicomCount)*100"/>
            </div>
            <h3 v-else>Analyzing...</h3>
            <pre style="white-space: pre-wrap;">{{$root.session.status_msg}}</pre>
            <div class="page-action">
                <el-button type="secondary" @click="$root.reset()">Cancel</el-button>
            </div>
        </div>

        <div v-if="$root.session.status == 'failed'">
            <p>ezBIDS failed.. Please check the log and/or contact ezBIDS team.</p>
            <pre style="white-space: pre-wrap;">{{$root.session.status_msg}}</pre>
            <br>
            <h4>Debugging</h4>
            <el-collapse v-model="activeLogs" @change="logChange">
                <el-collapse-item title="Preprocess/Analyzer Log" name="out">
                    <pre class="text">{{stdout}}</pre>
                </el-collapse-item>
                <el-collapse-item title="Preprocess/Analyzer Error Log" name="err">
                    <pre class="text">{{stderr}}</pre>
                </el-collapse-item>
            </el-collapse>
            <br>
            <br>
            <br>
            <br>
            <br>
            <br>
            <div class="page-action">
                <el-button type="secondary" @click="$root.reset()">Re-Upload</el-button>
            </div>
        </div>

        <div v-if="['analyzed', 'finalized', 'finished'].includes($root.session.status)">
            <p>Analysis complete! Please proceed to the next tab.</p>
            <h4>Object List ({{$root.objects.length}})</h4>
            <div v-for="(object, idx) in $root.objects" :key="idx">
                <p style="margin: 0;">
                    <el-link @click="toggleObject(idx)">
                        <small><el-tag size="mini" type="info">{{idx}}</el-tag> {{object.paths[0]}}</small>
                    </el-link>
                </p>
                <pre v-if="opened.includes(idx)" class="object-detail" style="font-size: 85%">{{object}}</pre>
            </div>

            <br>
            <br>
            <el-collapse v-model="activeLogs" @change="logChange">
                <el-collapse-item title="Preprocess/Analyzer Log" name="out">
                    <pre class="text">{{stdout}}</pre>
                </el-collapse-item>

                <el-collapse-item title="Preprocess/Analyzer Error Log" name="err">
                    <pre class="text">{{stderr}}</pre>
                </el-collapse-item>
            </el-collapse>

            <br>
            <br>
            <br>
            <br>
            <div class="page-action">
                <el-button type="secondary" @click="$root.reset()">Re-Upload</el-button>
                <el-button type="primary" @click="next" style="float: right;">Next</el-button>
            </div>
        </div>
    </div>
</div>
</template>

<script>

//import Vue from 'vue'
import axios from 'axios'

export default {
    //store,
    components: {
    },
    data() {
        return {
            dragging: false,
            starting: false, //wait for browser to handle all files

            total_size: null,
            files: [], //files to be uploaded (html5 file object)

            //reload_t: null,

            //uploading: [], //index of files that are currently being uploaded
            uploaded: [], //index of files that are successfully uploaded
            failed: [], //index of files failed to upload

            batches: [], //object containing information for each batch upload {evt, fileidx} 

            opened: [],

            doneUploading: false,

            //debug logs
            activeLogs: [],
            stdout: "",
            stderr: "",
            list: "",
        }
    },
    mounted() {
        console.log("upload mounted..");
    },
    created() {
        console.log("upload created..");
    },
    destroyed() {
    },
    methods: {
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
        dragover(e) {
            e.preventDefault();
            this.dragging = true;
        },

        async dropit(e) {
            e.preventDefault();
            this.dragging = false;
            this.starting = true;
            this.$nextTick(async ()=>{
                await this.listDropFiles(e.dataTransfer.items);
                this.upload();
            });
        },

        logChange() {
            if(this.activeLogs.includes("out")) {
                if(!this.out) fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/preprocess.log').then(res=>res.text()).then(data=>{
                        this.stdout = data;
                });
            } else this.out = "";

            if(this.activeLogs.includes("err")) {
                if(!this.err) fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/preprocess.err').then(res=>res.text()).then(data=>{
                        this.stderr = data;
                });
            } else this.err = "";

            if(this.activeLogs.includes("list")) {
                if(!this.list) fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/list').then(res=>res.text()).then(data=>{
                        this.list = data;
                });
            } else this.list = "";
        },

        selectit(e) {
            this.starting = true;
            this.$nextTick(()=>{
                this.files = e.target.files;
                for(let file of e.target.files) {
                    file.path = file.webkitRelativePath;
                }
                this.upload();
            });
        },

        //Unlike file input(directory) selecter, I have to do some convoluted thing to get all the files that user drops...
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
            async function readEntriesPromise(directoryReader) {
                try {
                    return await new Promise((resolve, reject) => {
                        directoryReader.readEntries(resolve, reject);
                    });
                } catch (err) {
                    console.error(err);
                }
            }

            async function getFile(fileEntry) {
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
                    file.path = entry.fullPath.substring(1); //remove / prefix
                    this.files.push(file);
                } else if (entry.isDirectory) {
                    queue.push(...await readAllDirectoryEntries(entry.createReader()));
                }
            }
        },

        async upload() {
            this.$root.analyzed = false;
            this.$root.validatedSeries = false;
            this.$root.validatedObject = false;
            
            //clearTimeout(this.reload_t);
            this.starting = false;
            this.doneUploading = false;

            //mark some file to ignore
            for(let i = 0;i < this.files.length;++i) {
                let file = this.files[i];
                if(file.path.endsWith(".nii.gz")) {
                    console.log("ignoring", file.path);
                    file.ignore = true;
                    this.uploaded.push(i);
                }
            }

            //calculate total file size
            this.total_size = 0;
            for(let i = 0;i < this.files.length;++i) {
                let file = this.files[i];
                if(file.ignore) continue;
                this.total_size += file.size;
            }

            this.files.forEach(file=>{
                file.try = 0;
            });

            //create new session
            const res = await fetch(this.$root.apihost+'/session', {
                method: "POST",
                headers: {
                    'Content-Type': 'application/json'
                },
                //body: JSON.stringify(session_body),
            });
            this.$root.session = await res.json();
            this.processFiles();
        },

        processFiles() {
            console.log("running processFiles");

            //find next files to upload
            let data = new FormData();
            let fileidx = [];
            let batchSize = 0;
            for(let i = 0;i < this.files.length;++i) {
                if(this.uploaded.includes(i)) continue;

                let file = this.files[i];
                if(file.uploading) continue;
                if(file.ignore) continue;
                if(file.try > 5) {
                    if(!this.failed.includes(i)) this.failed.push(i);
                    continue; //TODO we should abort upload?
                }
                batchSize += file.size;

                //limit batch size (3000 files causes network error - probably too many?)
                if(fileidx.length >= 500 || batchSize > 1024*1014*300) break;

                //let's proceed!
                file.uploading = true;
                fileidx.push(i);
                data.append("files", file);
                data.append("paths", file.path); //file doesn't contains the real path to store files to..
            }
            if(fileidx.length == 0) {
                console.log("no more files to process.");
                return; //all done!
            } 

            //prepare a batch
            let batch = {fileidx, evt: null, status: "uploading", size: batchSize}
            this.batches.push(batch);

            function doSend() {
                axios.post(this.$root.apihost+'/upload-multi/'+this.$root.session._id, data, {
                    onUploadProgress: evt=>{
                        //now that we are batch uploading.. this isn't for each files but..
                        batch.evt = evt;
                    }
                }).then(res=>{
                    let msg = res.data;
                    if(msg == "ok") {
                        batch.status = "done";
                        fileidx.forEach(idx=>{
                            this.uploaded.push(idx);
                        });

                        if(this.uploaded.length == this.files.length) {
                            console.log("upload completed.. calling done_uploading");
                            this.done_uploading();
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
                        this.files[idx].uploading = false;
                    });
                    setTimeout(this.processFiles, 1000*13);
                });

                //see how many batches we are currently uploading
                let uploadingBatches = this.batches.filter(b=>b.status == "uploading");
                if(uploadingBatches.length < 6) {
                    setTimeout(this.processFiles, 1000*5);
                }
            }

            doSend.call(this);
         },

        async done_uploading() {
            //we have multiple files uploading concurrently, so the last files will could make this call back 
            if(this.doneUploading) return; 
            this.doneUploading = true;
            
            //finalize the session
            await fetch(this.$root.apihost+'/session/uploaded/'+this.$root.session._id, {
                method: "PATCH",
                headers: {'Content-Type': 'application/json'},
            });            
            
            location.hash = this.$root.session._id;

            console.log("done uploading --------- start polling");
            this.$root.pollSession();
        },
        
        loadedPercentage(file_id) {
            let file = this.files[file_id];
            return ((file.loaded / file.size)*100).toFixed(1);
        },
         
        next() {
            this.$root.changePage("description");
        },
    },
}
</script>
<style scoped>
.drop-area {
    background-color: #0002;
    color: #999;
    padding: 25px;
    padding-top: 100px;
    border-radius: 5px;
    height: 300px;
    box-sizing: border-box;
    text-align: center;
    font-size: 125%;
    position: relative;
    overflow: hidden;
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
}

.object-detail {
    background-color: #0001;
    border-radius: 10px;
    max-height: 400px;
    overflow: auto;
    white-space: pre-wrap;
    padding: 10px 20px;
    font-size: 80%;
}
pre.text {
    background-color: #f0f0f0;
    border-radius: 10px;
    height: 450px;
    overflow: auto;
    white-space: pre-wrap;
    padding: 10px;
    font-size: 80%;
}
</style>
