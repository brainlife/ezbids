<template>
<div v-if="$root.currentPage.id == 'upload'">
    <div v-if="!$root.session">
        <p>
            Welcome to the <b><span style="letter-spacing: -2px; opacity: 0.5">ez</span>BIDS</b> - an online DICOM to BIDS conversion / organizing tool. 
        </p>

        <div class="drop-area" :class="{dragging}" 
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
    </div>

    <div v-if="$root.session">

        <div v-if="$root.session.status == 'created'">
            <h3>Uploading ...</h3>
            <el-progress status="success" 
                :text-inside="true" 
                :stroke-width="24" 
                :percentage="parseFloat(((uploaded.length/files.length)*100).toFixed(1))"/>

            <div class="stats">
                <p>
                    <small>Total size {{(total_size/(1024*1024))|formatNumber}} MB</small>
                    <small> | {{files.length}} Files </small>
                </p>
                <ul>
                    <li v-for="idx in uploading" :key="idx">
                        <small>{{idx}}.</small>
                        {{files[idx].path}} ({{loadedPercentage(idx)}}%)
                        <span v-if="files[idx].retry > 0">retry:{{files[idx].retry}}</span>
                    </li>
                </ul>
            </div>
        </div>

        <div v-if="$root.session.status == 'preprocessing'">
            <p v-if="$root.session.dicomDone && $root.session.dicomDone < $root.session.dicomCount">
                Converting dicoms to nifti ...
                <el-progress status="success" 
                    :text-inside="true" 
                    :stroke-width="24" 
                    :percentage="($root.session.dicomDone / $root.session.dicomCount)*100"/>
            </p>
            <p v-else>Analyzing...</p>
            <p><small><i>{{$root.session.status_msg}}</i></small></p>
        </div>

        <div v-if="$root.session.status == 'failed'">
            <p>ezBIDS failed.. Please check the log and/or contact ezBIDS team.</p>
            <p>{{$root.session.status_msg}}</p>
            <h4>Debugging</h4>
            <el-collapse v-model="activeLogs" @change="logChange">
                <el-collapse-item title="Preprocess/Analyzer Log" name="out">
                    <pre class="text">{{out}}</pre>
                </el-collapse-item>
                <el-collapse-item title="Preprocess/Analyzer Error Log" name="err">
                    <pre class="text">{{err}}</pre>
                </el-collapse-item>
                <el-collapse-item title="BIDS Conversion Log" name="bidsOut" v-if="$root.finalized">
                    <pre class="text">{{bidsOut}}</pre>
                </el-collapse-item>
                <el-collapse-item title="BIDS Conversion Error Log" name="bidsErr" v-if="$root.finalized">
                    <pre class="text">{{bidsErr}}</pre>
                </el-collapse-item>
                <el-collapse-item title="Objects" name="list" v-if="$root.analyzed">
                    <pre class="text">{{list}}</pre>
                    <div>
                        <h3>Subjects</h3>
                        <pre>{{this.$root.subjects}}</pre>
                        <h3>Sessions</h3>
                        <pre>{{this.$root.sessions}}</pre>
                        <h3>Series</h3>
                        <pre>{{this.$root.series}}</pre>
                        <h3>Objects</h3>
                        <pre>{{this.$root.objects}}</pre>
                    </div>
                </el-collapse-item>
            </el-collapse>
        </div>

        <div v-if="$root.session.status == 'analyzed'">
            <p>Analysis complete! Please proceed to the next tab.</p>
            <div class="page-action">
                <el-button type="primary" @click="next">Next</el-button>
                <el-button type="secondary" @click="$root.reset()">Re-Upload</el-button>
            </div>
        </div>
    </div>
</div>
</template>

<script>

import axios from 'axios';

export default {
    //store,
    components: {
    },
    data() {
        return {
            dragging: false,
            total_size: null,
            files: [], //files to be uploaded (html5 file object)

            reload_t: null,

            uploading: [], //index of files that are currently being uploaded
            uploaded: [], //index of files that are successfully uploaded
            doneUploading: false,
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
        //HTML5 drop event doesn't work unless dragover is handled
        dragover(e) {
            e.preventDefault();
            this.dragging = true;
        },

        async dropit(e) {
            e.preventDefault();
            this.dragging = false;
            await this.listDropFiles(e.dataTransfer.items);
            this.upload();
        },

        selectit(e) {
            this.files = e.target.files;
            for(let file of e.target.files) {
                file.path = file.webkitRelativePath;
            }
            this.upload();
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
            
            clearTimeout(this.reload_t);
            this.doneUploading = false;

            //calculate total file size
            this.total_size = 0;
            for(let i = 0;i < this.files.length;++i) {
                let file = this.files[i];
                this.total_size += file.size;
            }

            //create new session
            const res = await fetch(this.$root.apihost+'/session', {
                method: "POST",
                headers: {
                    'Content-Type': 'application/json'
                },
                //body: JSON.stringify(session_body),
            });
            this.$root.session = await res.json();
            location.hash = this.$root.session._id;

            //reset some extra information for each file
            for(let i = 0;i < this.files.length;++i) {
                let file = this.files[i];
                file.retry = 0; 
                file.loaded = 0; //for progress
            }           

            //start uploading files
            this.process_files();
        },

        async process_files() {
            if(this.uploaded.length == this.files.length) {
                return this.done_uploading();
            }
            if(this.uploading.length >= 6) return; //don't upload more than 4 files concurrently
        
            //find next file to upload
            let file;
            let idx;
            for(let i = 0;i < this.files.length;++i) {
                if(this.uploaded.includes(i)) continue;
                if(this.uploading.includes(i)) continue;
                file = this.files[i];
                idx = i;
                break;
            }
            if(!file) return; //no more file
            this.uploading.push(idx);

            if(file.retry == 3) {
                this.$root.uploadFailed = true;
                return;
            }
            
            try {
                let data = new FormData();
                data.append("file", file);
                data.append("path", this.files[idx].path);
                await axios.post(this.$root.apihost+'/upload/'+this.$root.session._id, data, {
                    onUploadProgress: evt=>{
                        //this.$forceUpdate(); //I don't think we need it?
                        file.loaded = evt.loaded;
                    }
                });

                this.uploaded.push(idx);
                let pos = this.uploading.indexOf(idx);
                this.uploading.splice(pos, 1);
                this.process_files();
            } catch(err) {
                console.error(err);
                file.retry++;

                //fail.. retry again?
                let pos = this.uploading.indexOf(idx);
                this.uploading.splice(pos, 1);
                setTimeout(this.process_files, 1000*5); //give a bit of time between try..
            }

            this.process_files();
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
    font-size: 30vh;
    opacity: 0.1;
    top: 0;
    left: 0;
    right: 0;
    z-index: -1;
    padding: 30px 0;
    filter: blur(0.3vh);
/*
    text-shadow: 1vh 1vh 0.5vh #0009;
*/
}
.stats {
padding: 15px;
}
.stats ul {
list-style: none;
margin: 0;
padding: 0;
}
.stats ul li {
font-family: monospace;
}
</style>
