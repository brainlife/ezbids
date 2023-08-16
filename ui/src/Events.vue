<template>
<div style="padding: 20px">
    <div v-if="!events.loaded">
        <p>If you'd like to include task events/timing data with your BIDS datasets, you can upload them here.</p>
        <p>Please skip this page if you do not have events data, or if your events data is not set up where each row pertains to an individual trial. An exception is E-Prime txt files, which are allowed.</p>
        <p>Only the following file extensions will be accepted by ezBIDS: <b>.csv</b>, <b>.tsv</b>, <b>.txt</b>, <b>.out</b>, and <b>.xlsx</b>. Uploaded files with other extensions will be ignored.</p>
        <br>

        <!-- <el-button @click="open">Select Directory</el-button> -->
        <input type="file"
            webkitdirectory
            mozdirectory
            msdirectory
            odirectory
            directory
            placeholder="Select Directory"
            @change="open"/>

        <br>
        <br>
        <br>
        <div class="hint">
            <h2>Hint</h2>
            <p>To ensure proper mapping of events to their imaging files, please have subject, (session), task, and run information in the event file columns, or have the information in the file paths. An example of the latter can be found below.</p>
            <div class="clearfix">
                <img src="./assets/images/events_directoryUpload_example.png" width="600"/>
            </div>
        </div>
        <br>
        <br>
        <br>
    </div>
    <div v-if="events.loaded">
        <el-button type="warning" @click="reset" style="float: right;">Reset</el-button>
        <h3>Column Mapping</h3>
        <p>Please correct the column mappings.</p>

        <table class="mapping-table">
        <tr>
            <th>Onset*</th>
            <td>
                <el-select v-model="columns.onsetLogic" size="small" style="width: 100px;">
                    <el-option label="=" value="eq"/>
                    <el-option label="Subtract" value="subtract"/>
                    <el-option label="Add" value="add"/>
                </el-select>
                &nbsp;
                <columnSelecter v-model="columns.onset" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>
                <span v-if="columns.onsetLogic == 'subtract'">&nbsp;-&nbsp;</span>
                <span v-if="columns.onsetLogic == 'add'">&nbsp;+&nbsp;</span>
                <div v-if="['subtract', 'add'].includes(columns.onsetLogic)" style="display: inline">
                    <columnSelecter v-model="columns.onset2" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>
                </div>
                &nbsp;
                <el-select v-model="columns.onsetUnit" size="small" style="width: 120px">
                    <el-option label="millisecond" value="ms"/>
                </el-select>

                <p>
                    Onset of the event measured from the beginning of the acquisition of the first volume in the corresponding task imaging data file.
                    If any acquired scans have been discarded before forming the imaging data file, ensure that a time of 0 corresponds to the first
                    image stored. In other words negative numbers in "onset" are allowed.
                </p>
                <br>
            </td>
        </tr>

        <tr>
            <th>Duration*</th>
            <td>
                <el-select v-model="columns.durationLogic" size="small" style="width: 100px;">
                    <el-option label="=" value="eq"/>
                    <el-option label="Subtract" value="subtract"/>
                    <el-option label="Add" value="add"/>
                </el-select>
                &nbsp;
                <columnSelecter v-model="columns.duration" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>
                <span v-if="columns.durationLogic == 'subtract'">&nbsp;-&nbsp;</span>
                <span v-if="columns.durationLogic == 'add'">&nbsp;+&nbsp;</span>
                <div v-if="['subtract', 'add'].includes(columns.durationLogic)" style="display: inline">
                    <columnSelecter v-model="columns.duration2" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>
                </div>
                &nbsp;
                <el-select v-model="columns.durationUnit" size="small" style="width: 120px">
                    <el-option label="millisecond" value="ms"/>
                </el-select>

                <p>
                    Duration of the event (measured from onset). Must always be either zero or positive. A "duration" value of zero implies that
                    the delta function or event is so short as to be effectively modeled as an impulse.
                </p>
                <br>
            </td>
        </tr>

        <tr>
            <th>Sample</th>
            <td>
                <el-select v-model="columns.sampleLogic" size="small" style="width: 100px;">
                    <el-option label="=" value="eq"/>
                    <el-option label="Subtract" value="subtract"/>
                    <el-option label="Add" value="add"/>
                </el-select>
                &nbsp;
                <columnSelecter v-model="columns.sample" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>
                <span v-if="columns.sampleLogic == 'subtract'">&nbsp;-&nbsp;</span>
                <span v-if="columns.sampleLogic == 'add'">&nbsp;+&nbsp;</span>
                <div v-if="['subtract', 'add'].includes(columns.sampleLogic)" style="display: inline">
                    <columnSelecter v-model="columns.sample2" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>
                </div>
                &nbsp;
                <p>
                    Onset of the event according to the sampling scheme of the recorded modality (that is, referring to the raw data file
                    that the events.tsv file accompanies).
                </p>
                <br>
            </td>
        </tr>

        <tr>
            <th>Response Time</th>
            <td>
                <el-select v-model="columns.responseTimeLogic" size="small" style="width: 100px;">
                    <el-option label="=" value="eq"/>
                    <el-option label="Subtract" value="subtract"/>
                    <el-option label="Add" value="add"/>
                </el-select>
                &nbsp;
                <columnSelecter v-model="columns.responseTime" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>
                <span v-if="columns.responseTimeLogic == 'subtract'">&nbsp;-&nbsp;</span>
                <span v-if="columns.responseTimeLogic == 'add'">&nbsp;+&nbsp;</span>
                <div v-if="['subtract', 'add'].includes(columns.responseTimeLogic)" style="display: inline">
                    <columnSelecter v-model="columns.responseTime2" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>
                </div>
                &nbsp;
                <el-select v-model="columns.responseTimeUnit" size="small" style="width: 120px">
                    <el-option label="millisecond" value="ms"/>
                </el-select>

                <p>
                    Response time measured in seconds. A negative response time can be used to represent preemptive responses and "n/a"
                    denotes a missed response.
                </p>
                <br>
            </td>
        </tr>

        <tr>
            <th>Trial Type</th>
            <td>
                <columnSelecter v-model="columns.trialType" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>

                <p>
                    Primary categorisation of each trial to identify them as instances of the experimental conditions.
                    For example: for a response inhibition task, it could take on values "go" and "no-go" to refer to response initiation
                    and response inhibition experimental conditions.
                </p>

                <div v-if="columns.trialType">
                    <el-input v-model="trialTypes.longName" size="small">
                        <template #prepend>longName</template>
                    </el-input>
                    <br>
                    <br>
                    <el-input v-model="trialTypes.desc" size="small">
                        <template #prepend>Description</template>
                    </el-input>
                    <br><br>

                    <span>Levels</span>
                    <!--TODO - I need to let user edit the values themselves and add/remove them-->
                    <div v-for="value in events.sampleValues[columns.trialType]" :key="value" style="margin-top: 3px;">
                        <el-input v-model="trialTypes.levels[value]" placeholder="desc" size="small">
                            <template #prepend>{{value}}</template>
                        </el-input>
                    </div>
                </div>
                <br>
            </td>
        </tr>

        <tr>
            <th>Value</th>
            <td>
                <columnSelecter v-model="columns.value" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>

                <p>
                    Marker value associated with the event (for example, the value of a TTL trigger that was recorded at the onset of the event).
                </p>
                <br>
            </td>
        </tr>

        <tr>
            <th>HED</th>
            <td>
                <columnSelecter v-model="columns.HED" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>

                <p>
                    Hierarchical Event Descriptor (HED) Tag. See <a href="https://bids-specification.readthedocs.io/en/stable/99-appendices/03-hed.html">BIDS Specification / Appendix 3</a>
                </p>
                <br>
            </td>
        </tr>

        <tr>
            <th>stim_file</th>
            <td>
                <columnSelecter v-model="columns.stim_file" :columnKeys="ezbids.columnKeys" :sampleValues="events.sampleValues"/>

                <p>
                    Represents the location of the stimulus file (such as an image, video, or audio file) presented at the given onset time. There are no restrictions on the file formats of the stimuli files, but they should be stored in the /stimuli directory (under the root directory of the dataset; with OPTIONAL subdirectories). The values under the stim_file column correspond to a path relative to /stimuli. For example images/cat03.jpg will be translated to /stimuli/images/cat03.jpg. See <a href="https://bids-specification.readthedocs.io/en/stable/99-appendices/03-hed.html">BIDS Specification / Appendix 3</a>
                </p>
                <br>
            </td>
        </tr>        

        </table>

        <!--
        <h3>Debug</h3>
        <pre>{{columns}}</pre>
        <pre>{{trialTypes}}</pre>
        -->
        <br>
        <br>
        <br>
    </div>
</div>
</template>

<script lang="ts">

import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue'
import datatype from './components/datatype.vue'
import columnSelecter from './components/columnselecter.vue'

import { IObject } from './store'

import { createEventObjects, mapEventColumns } from './libUnsafe'

interface Section {
    [key: string]: IObject[]
}

interface IPathAndData {
    path: string
    data: string
}

interface TrialType {
    longName: string
    desc: string
    levels: [{[key:string]: string}]
}

interface Column {
    key: string,
    unit: string|null, //sec, millisecond, etc..
}

export default defineComponent({
    components: {
        datatype,
        columnSelecter,
    },

    data() {
        return {
            dragging: false,
            starting: false, //wait for browser to handle all files
        }
    },

    mounted() {

    },

    computed: {
        ...mapState(['ezbids', 'config', 'bidsSchema', 'events']),
        ...mapGetters(['getBIDSEntities', 'getURL', 'findSubject']),

        columns() {
            return this.ezbids.events.columns;
            // return this.$store.state.events.columns;
        },
        trialTypes() {
            return this.ezbids.events.trialTypes;
            // return this.$store.state.events.trialTypes;
        },
    },

    methods: {
        isValid(cb: (err?: string)=>void) {
            let err = undefined;
            if(this.events.loaded) {
                if(!this.columns.onset) err = "Please specify onset column";
                if(this.columns.onsetLogic != "eq" && !this.columns.onset2) err = "Please specify 2nd operand for onset";

                if(!this.columns.duration) err = "Please specify duration column";
                if(this.columns.durationLogic != "eq" && !this.columns.duration2) err = "Please specify 2nd operand for duration";

            }
            cb(err);
        },

        reset() {
            //remove existing func/events
            this.ezbids.objects = this.ezbids.objects.filter((o:IObject)=>o._type != "func/events");
            this.events.loaded = false;
        },

        async open(event: Event) {
            const element = event.currentTarget as HTMLInputElement;
            const files = [] as IPathAndData[];
            const filesIgnore = [];
            if(!element.files) return;

            // @ts-ignore
            for await (let file of element.files) {
                const fileExt = file.webkitRelativePath.split(".").pop();
                if((fileExt != "tsv") && (fileExt != "csv") && (fileExt != "txt") && (fileExt != "out") && (fileExt != "xlsx")) {
                    filesIgnore.push(file.webkitRelativePath)
                }else{
                    files.push({
                        path: file.webkitRelativePath,
                        data: await file.text(),
                    });
                }
            }

            this.reset();

            try {

                if(filesIgnore.length) {
                    alert("The following files contain an unsupported extension and will be ignored:\n\n"+filesIgnore.join("\n"));
                }

                //create new event objects
                const eventObjects = createEventObjects(this.ezbids, files);

                //adjust eventObjects error message based on exclusion of corresponding func/bold
                this.ezbids.objects.forEach((o:IObject)=>{
                    let correspondingFuncBoldEvents = eventObjects.filter(object=>object.ModifiedSeriesNumber == o.ModifiedSeriesNumber && o._type == "func/bold")
                    if(correspondingFuncBoldEvents.length > 0) {
                        correspondingFuncBoldEvents.forEach(object=>{
                            object.analysisResults.errors = []

                            if(o._exclude == true) {
                                object.analysisResults.errors = [`The corresponding func/bold (#${o.series_idx}) to this acquisition has been set (or was set) to exclude from BIDS conversion. Recommendation is to also exclude this acquisition from BIDS conversion (assuming the func/bold is still set for exclusion), unless you have good reason for keeping it.`]
                            }
                        })
                    }
                })

                eventObjects.forEach(object=>{
                    this.$store.commit("addObject", object);
                });

                this.$emit("mapObjects");

                //enumerate all possible column headers (from the 1st example)
                const example = this.ezbids.objects.find((o:IObject)=>o._type == "func/events");
                if(!example) return; //no event file uploaded
                const tsvItem = eventObjects[0].items.find((i: any) => i.name == "csv" || i.name == "out" || i.name == "txt" || i.name == "tsv" || i.name == "xlsx")
                if(!tsvItem) return; //should never happen

                const firstEvent = tsvItem.events[0];
                this.ezbids.columnKeys = Object.keys(firstEvent);

                //construct samples
                this.ezbids.columnKeys.forEach((key:string)=>{
                    const samples = [] as string[];
                    tsvItem.events.forEach((rec:any)=>{
                        //limit number of samples under 30 values.. and unique
                        if(!samples.includes(rec[key]) && samples.length < 30) samples.push(rec[key]);
                    });
                    this.events.sampleValues[key] = samples;
                })

                const columnMappings = mapEventColumns(this.ezbids.events, tsvItem.events);
                Object.assign(this.columns, columnMappings);

                console.log("successfully processed event files");
                this.events.loaded = true;
            } catch (err){
                console.error(err);
                alert("failed to parse/map event files: "+err);
            }
        },
    },
});
</script>

<style lang="scss" scoped>
.bids-structure {
    font-size: 90%;
    position: fixed;
    top: 0;
    bottom: 60px;
    left: 200px;
    width: 350px;
    overflow: auto;
    padding: 5px 10px;
    overflow-y: scroll;
    box-sizing: border-box;
}
.object {
    position: fixed;
    top: 0;
    bottom: 60px;
    overflow-y: auto;
    left: 550px;
    right: 0;
    z-index: 1;
}
.item {
    padding-bottom: 5px;
    margin-bottom: 5px;
}
.hierarchy {
    padding: 3px;
    display: block;
    line-height: 100%;
}
.hierarchy-item {
    padding: 2px;
}
.clickable {
    transition: background-color 0.3s;
}
.clickable:hover {
    background-color: #ddd;
    cursor: pointer;
}
.selected {
    background-color: #d9ecff;
}
.exclude {
    opacity: 0.2;
}
.left-border {
    margin-left: 8.5px;
    padding-left: 4px;
    border-left: 2px solid #3331;
    padding-top: 4px;
}
.exclude {
    opacity: 0.6;
}
.sub-title {
    font-size: 85%;
    margin-bottom: 5px;
}

.border-top {
    border-top: 1px solid #f6f6f6;
    padding-top: 2px;
    margin-top: 2px;
}

pre.headers {
    height: 200px;
    overflow: auto;
    line-height: 1.5;
    border-radius: 5px;
    padding: 5px 15px;
    font-family: Avenir, Helvetica, Arial, sans-serif;
    font-size: inherit;
    background-color: #eee;
    color: #999;
}

.el-form-item {
    margin-bottom: 0;
    padding-right: 30px;
}

.mapping-table {
    td, th {
        vertical-align: top;
    }
    th {
        padding: 6px;
        padding-right: 20px;
        min-width: 170px;
        text-align: right;
        opacity: 0.7;
    }
    p {

        font-size: 90%;
        opacity: 0.8;
    }
}

.image {
    display: inline-block;
    width: 300px;
    padding: 10px;
    margin-bottom: 20px;
    img {
        border-radius: 50%;
        margin-bottom: 20px;
    }
    text-align: center;
    font-size: 125%;
    color: #0009;

}
</style>

