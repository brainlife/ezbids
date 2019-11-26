const apihost = "https://dev1.soichi.us/api/easybids";

const Upload = {

    mounted() {
        console.log("mounted");
    },

    data() {
        return {
            dragging: false,
            mode: 'accept',
            total_size: null,
            files: [], //files to be uploaded (html5 file object)

            session_id: null, //session id to upload files to
            uploading: [], //index of files that are currently being uploaded
            uploaded: [], //index of files that are successfully uploaded
        }
    },

    methods: {
        //HTML5 drop event doesn't work unless dragover is handled
        dragover(e : DragEvent) {
            e.preventDefault();
            this.dragging = true;
        },

        async dropit(e : DragEvent) {
            console.dir(e);
            e.preventDefault();
            this.dragging = false;
            await this.listDropFiles(e.dataTransfer.items);
            this.upload();
        },

        selectit(e : Event) {
            this.mode = 'listing';
            this.files = e.target.files;
            for(let file of e.target.files) {
                file.path = file.webkitRelativePath;
            }
            this.upload();
        },

        //Unlike file input(directory) selecter, I have to do some convoluted thing to get all the files that user drops...
        async listDropFiles(items : DataTransferItemList) {
            this.mode = 'listing';
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
                    console.dir(entry);
                    let file = await getFile(entry);
                    file.path = entry.fullPath.substring(1); //remove / prefix
                    //file.that = entry.fullPath;
                    this.files.push(file);
                } else if (entry.isDirectory) {
                    queue.push(...await readAllDirectoryEntries(entry.createReader()));
                }
            }
        },

        async upload(files) {
            //console.dir(files);
            this.mode = "upload";

            //calculate total file size
            this.total_size = 0;
            for(let i = 0;i < this.files.length;++i) {
                let file = this.files[i];
                this.total_size += file.size;
            }

            //construct session request body
            let session_body = {files: []};
            for(let i = 0;i < this.files.length;++i) {
                let file = this.files[i];
                session_body.files.push({
                    idx: i,
                    name: file.name,
                    size: file.size,
                    path: file.path,
                });
            }

            //create new session
            const res = await fetch(apihost+'/session', {
                method: "POST",
                /*
                mode: "cors",
                cache: "no-cache",
                credentials: 'same-origin',
                redirect: 'follow',
                referrer: 'autobids-ui',
                */
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(session_body),
            });
            const ret = await res.json();
            this.session_id = ret._id;

            //reset some extra information for each file
            for(let i = 0;i < this.files.length;++i) {
                let file = this.files[i];
                file.retry = 0; 
                file.loaded = 0; //for progress
            }           

            //start uploading files
            this.process_files();

                /*
                var reader = new FileReader();
                reader.onload = function(e) {
                    console.log("loaded");
                    console.dir(e);
                }
                reader.readAsDataURL(file);
                */

                /* one way to upload the file
                function uploadFile(file){
                    var url = 'server/index.php';
                    var xhr = new XMLHttpRequest();
                    var fd = new FormData();
                    xhr.open("POST", url, true);
                    xhr.onreadystatechange = function() {
                        if (xhr.readyState == 4 && xhr.status == 200) {
                            // Every thing ok, file uploaded
                            console.log(xhr.responseText); // handle response.
                        }
                    };
                    fd.append("upload_file", file);
                    xhr.send(fd);
                }
                */
        },

        process_files() {
            if(this.uploaded.length == this.files.length) {
                return this.done_uploading();
            }
            if(this.uploading.length > 3) return; //don't upload more than 3 files concurrently
        
            //find next file to upload
            let file;
            let idx: number;
            for(let i = 0;i < this.files.length;++i) {
                if(this.uploaded.includes(i)) continue;
                if(this.uploading.includes(i)) continue;
                file = this.files[i];
                idx = i;
                break;
            }
            if(!file) {
                console.log("no more files to upload");
                console.log(this.uploaded);
                console.log(this.files);
                return;
            }
            this.uploading.push(idx);

            if(file.retry == 3) {
                this.mode = "failed";
                return;
            }
            
            //console.dir(file);
            let data = new FormData();
            data.append("file", file);
            axios.post(apihost+'/upload/'+this.session_id+'/'+idx, data, {
                onUploadProgress: evt=>{
                    this.$forceUpdate();
                    file.loaded = evt.loaded;
                }
            }).then(res=>{
                //success
                this.uploaded.push(idx);
                let pos = this.uploading.indexOf(idx);
                this.uploading.splice(pos, 1);
                this.process_files();
            }).catch(err=>{
                console.error(err);
                file.retry++;
                //fail.. retry again?
                let pos = this.uploading.indexOf(idx);
                this.uploading.splice(pos, 1);
                setTimeout(this.process_files, 1000*5); //give a bit of time between try..
            });

            this.process_files();
        },

        async done_uploading() {
            console.log("done uploading");
            
            const res = await fetch(apihost+'/session/uploaded/'+this.session_id, {
                method: "PATCH",
                headers: {'Content-Type': 'application/json'},
            });            
            
            this.$router.push('/session/'+this.session_id);
        },
        
        loadedPercentage(file_id) {
            let file = this.files[file_id];
            return ((file.loaded / file.size)*100).toFixed(1);
        }

    },

    template: `
    <div>
        <div v-if="mode == 'accept'" class="drop-area" :class="{dragging}" @drop="dropit" @dragleave="dragging = false" @dragover="dragover">
            <h2>Drag & Drop a DICOM folder to convert to BIDS</h2>
            or <input type="file" webkitdirectory mozdirectory msdirectory odirectory directory multiple @change="selectit"/>
        </div>
        <div v-if="mode != 'accept'">
            <p v-if="mode == 'listing'" class="drop-text"><i class="fa fa-cog fa-spin"></i> Listing files {{files.length}}...</p>
            <div v-if="mode == 'upload'">
                <h3>Uploading..</h3>
                <p v-for="idx in uploading" :key="idx">
                    <!--{{files[idx].loaded}} / {{files[idx].size}}-->
                     {{loadedPercentage(idx)}}%
                    <!--{{files[idx].name}}-->
                    {{files[idx].path}} idx:{{idx}} retry:{{files[idx].retry}}
                </p>

                total size: {{total_size}}
                files: {{files.length}}
                uploaded: {{uploaded.length}}
                <!--
                <div class="file" v-for="(file, idx) in files" :key="idx">
                    {{file}}
                </div>
                -->
            </div>
            <p v-if="mode == 'uploaded'" class="drop-text">Uploaded!!</p>
        </div>
        <div v-if="mode == 'failed'">
            Sorry.. something went wrong while uploading files. Please contact the developer. (session id: {{session_id}})
        </div>
        <br>
        <!--<center style="opacity: 0.5;">Please contact <a href="mailto:hayashis@iu.edu">hayashis@iu.edu</a> for comments / questions / bug report.</center>-->
    </div>
    `,
}

const Session = { 
    data() {
        return {
            session_id: this.$route.params.session_id,
            session: null, //to-be-loaded
            reload_int: null,
            apihost,
        }
    },

    watch: {
        '$route.params.session_id': function (id) {
            this.session_id = id;
            this.load_session();
        }
    },

    async mounted() {
        //load session detail
        this.reload_int = setInterval(this.load_session, 1000);
        this.load_session();
    },

    destroyed() {
        clearInterval(this.reload_int);
    },

    methods: {
        async load_session() {
            const res = await fetch(apihost+'/session/'+this.session_id, {
                method: "GET",
                headers: {
                    'Content-Type': 'application/json'
                },
            });
            this.session = await res.json();

            //DEBUG don't reload anymore if we reached the final state
            //if(this.session.pre_finish_date) clearInterval(this.reload_int);
        },
    },

    template: `<div v-if="session">
        <h3>{{session._id}}</h3>
        <b>{{session.status}}</b>
        <span v-if="session.status == 'uploaded'">Waiting to be processed..</span>
        <p>{{session.status_msg}}</p>
        <p>
            debug..
            <a :href="apihost+'/session/processlog/'+this.session_id">process.log</a>
            <a :href="apihost+'/session/processerr/'+this.session_id">process.err</a>
            <a :href="apihost+'/session/list/'+this.session_id">list</a>
        </p>
        {{session}}
    </div>` 
}

const app = new Vue({
    el: '#app',
    router: new VueRouter({
        routes: [
            { path: '/', component: Upload },
            { path: '/session/:session_id', component: Session }
        ]
    }),
    template: `
    <router-view class="app"></router-view>
    `,
});

