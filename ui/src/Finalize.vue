<template>
<div style="padding: 20px;">
    <!--
    <div v-if="!session.finalize_begin_date && !submitting && session.status != 'finalized'">
        <p>Your data is ready to be converted to BIDS!</p>
        <el-form>
            <el-form-item>
                <el-button @click="finalize" type="primary">Finalize</el-button>
            </el-form-item>
        </el-form>
    </div>
    -->

    <div v-if="session.status == 'analyzed'">
        <h3>Finalizing ...</h3>
    </div>


    <div v-if="session.status == 'finalized' || (session.finalize_begin_date && !session.finalize_finish_date)">
        <h3>Converting to BIDS ...</h3>
        <p><small><i>{{session.status_msg}}</i></small></p>
    </div>

    <div v-if="session.finalize_finish_date">
        <div class="download">
            <br>
            <h3 style="margin-top: 0;">All Done!</h3>
            <p>
            Please download the BIDS formatted data to your local computer, or send the data to other cloud resources.
            </p>
            <p>
                <!--<el-button @click="rerun" type="success" style="float: right" size="small">Rerun Finalize Step</el-button>-->
                <el-button @click="download" type="primary">Download BIDS</el-button>
                <el-button @click="sendBrainlife">Send to <b>brainlife.io</b></el-button>
                <el-button @click="sendOpenneuro">Send to <b>OpenNeuro</b></el-button>
            </p>
            <p @click="downloadSubjectMapping" class="btn">
                <i class="el-icon-download"></i> PatientName to Subject/Session Mapping
                <small>* may contain sensitive PHI data. Please make sure to store in a secure location.</small>
            </p>
        </div>

        <br>
        <el-row>
            <el-col :span="12">
                <h4>BIDS Structure</h4>
                <showfile path="tree.log" style="margin-right: 15px;" :tall="true"/>
            </el-col>
            <el-col :span="12">
                <h4>bids-validator output</h4>
                <showfile path="validator.log" :tall="true"/>
            </el-col>
        </el-row>
    </div>

    <div v-if="session.status == 'failed'">
        <p>Failed to convert to BIDS...</p>
        <el-button @click="rerun" type="success" style="float: right" size="small">Rerun Finalize Step</el-button>
        <p><small><i>{{session.status_msg}}</i></small></p>
    </div>

    <br>
    <br>
    <h4>Debugging</h4>
    <el-collapse v-model="activeLogs">
        <el-collapse-item title="BIDS Conversion Log" name="bids.log" v-if="session.status == 'finished'">
            <showfile path="bids.log" />
        </el-collapse-item>
        <el-collapse-item title="BIDS Conversion Error Log" name="bids.err" v-if="session.status == 'finished'">
            <showfile path="bids.err"/>
        </el-collapse-item>
        <el-collapse-item title="Session" name="session">
            <pre class="text">{{session}}</pre>
        </el-collapse-item>
        <el-collapse-item title="Files" name="files">
            <a :href="config.apihost+'/download/'+session._id+'/finalized.json'">finalized.json</a>
        </el-collapse-item>
    </el-collapse>
    <br>
    <br>

    <!--
    <div class="page-action">
        <el-button type="secondary" @click="back">Back</el-button>
    </div>
    -->
</div>
</template>

<script lang="ts">

import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue'                                                                                                                                                  
import showfile from './components/showfile.vue' 

import { ElNotification } from 'element-plus'

export default defineComponent({

    components: { 
        showfile 
    },

    data() {
        return {
            submitting: false, //prevent double submit
            activeLogs: [],
            //defacingStats: null,
        }
    },

    computed: {
        ...mapState(['ezbids', 'config', 'bidsSchema', 'session', 'events']),
        ...mapGetters(['getBIDSEntities', 'getURL', 'findSubject', 'findSession']),
    },

    mounted() {
        //I don't think user knows they have to rerun finalize step to update bids structure after they go back and do other things..
        //let's just force it
        this.rerun(); 
        this.finalize();
    },

    methods: {

        finalize() {
            this.submitting = true;
            this.dofinalize((err:string|null)=>{
                if(err) ElNotification({ title: 'Failed', message: 'Failed to finalize:'+err});
                if(err) console.error(err);
                this.submitting = false;
                this.$store.dispatch("loadSession", this.session._id);
            });
        },

        dofinalize(cb: (err: string|null)=>void) {
            //TODO - why can't server just look up the bids schema by itself!?
            //mapping between things like like "subject" to "sub"                                                       
            const entityMappings = {} as {[key: string]: string};                                                                                  
            for(const key in this.bidsSchema.entities) {                                                                      
                entityMappings[key] = this.bidsSchema.entities[key].entity;                                                   
            }                                                                                                           
                                                                                                                        
            fetch(this.config.apihost+'/session/'+this.session._id+'/finalize', {                                              
                method: "POST",                                                                                         
                headers: {'Content-Type': 'application/json; charset=UTF-8'},                                           
                body: JSON.stringify({                                                                                  
                    datasetDescription: this.ezbids.datasetDescription,                                                        
                    readme: this.ezbids.readme,                                                                                
                    participantsColumn: this.ezbids.participantsColumn,                                                        
                    subjects: this.ezbids.subjects, //for phenotype                                                            
                    objects: this.ezbids.objects,                                                                                                                                    
                    entityMappings,  
                    events: this.events,                                                                                
                }),                                                                                                     
            }).then(res=>res.text()).then(status=>{                                                                     
                   if(cb) cb((status=="ok")?null:status);                                                                                                       
            });  
        },

        rerun() {
            //fake it to make it looks like we haven't finalized yet.
            this.session.status = "analyzed";
            delete this.session.finalize_begin_date;
            delete this.session.finalize_finish_date;
        },

        download() {
            document.location.href = this.config.apihost+'/download/'+this.session._id+'/bids/'+this.ezbids.datasetDescription.Name;
        },

        downloadSubjectMapping() {
            this.downloadMapping(JSON.stringify(this.ezbids.subjects, null, 2), "subject_mappings.json");
        },

        //un-refactor this?
        downloadMapping(data: any, name: string) {
            const blob = new Blob([data], { type: 'application/json' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = name;
            link.click()
            URL.revokeObjectURL(link.href)
        },

        sendBrainlife() {
            window.open("../projects#ezbids:"+this.session._id, "_brainlife");
        },

        sendOpenneuro() {
            ElNotification({ title: 'Failed', message: 'This functionality is yet to be implemented'});
        },

        /*
        logChange() {
            if(this.activeLogs.includes("out")) {
                if(!this.out) fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/bids.log').then(res=>res.text()).then(data=>{
                        this.stdout = data;
                });
            } else this.out = "";

            if(this.activeLogs.includes("err")) {
                if(!this.err) fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/bids.err').then(res=>res.text()).then(data=>{
                        this.stderr = data;
                });
            } else this.err = "";
        },
        */
        /*
        back() {
            this.$root.changePage("deface");
        },
        */
    },
});
</script>

<style scoped>
.download {
    border-radius: 10px;
    background-color: #eee;
    padding: 20px;
    font-size: 85%;
}
.mappings p {
    cursor: pointer;
    color: #409EFF;
}
.mappings p:hover {
    text-decoration: underline;
}
p.btn {
    background-color: white; padding: 5px; border-radius: 4px; display: inline-block;
    transition: background-color 0.3s;
    padding: 5px 10px;
}
p.btn:hover {
    background-color: rgb(103, 194, 58);
    color: white;
    cursor: pointer;
}
</style>


