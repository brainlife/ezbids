<template>
<div style="padding: 20px;">
    <el-form v-if="getAnatObjects.length && !isDefacing">
        <p>
            If you'd like to deface all anatomical images, please select a defacing method and click <b>Run Deface</b> button. 
        </p>
        <p>
            Otherwise, you can skip this page.
        </p>

        <el-row>
            <el-col :span="12">
                <el-form-item>
                    <b>Defacing Method </b>
                    &nbsp;
                    <el-select v-model="ezbids.defacingMethod" placeholder="Select a defacing method" style="width: 300px;" @change="changeMethod">
                        <el-option value="" label="Don't Deface (use original)"/>
                        <el-option value="quickshear" label="Quickshear (recommended)"/>
                        <el-option value="pydeface" label="pyDeface (more common but takes much longer time)"/>
                    </el-select>
                </el-form-item>
            </el-col>
            <el-col :span="12">
                <!--sub options-->
                <div v-if="ezbids.defacingMethod == 'quickshear'">
                    <small>* Use ROBEX and QuickShear Average processing time. 1min per image</small>
                </div>
                <div v-if="ezbids.defacingMethod == 'pydeface'">
                    <small>* pydeface uses fsl to align facial mask template. 5min per image</small>
                </div>
                <br>
            </el-col>
        </el-row>
    </el-form>

    <el-alert v-if="getAnatObjects.length == 0" type="warning">No anatomy files to deface. Please skip this step.</el-alert>
    <div v-if="getAnatObjects.length && ezbids.defacingMethod">
        <div v-if="session.status == 'deface' || session.status == 'defacing'">
            <h3>Running <b>{{ezbids.defacingMethod}}</b> ...</h3>
            <pre class="status">{{session.status_msg}}</pre>
        </div>
        <div v-if="session.deface_finish_date">
            <br>
            <el-alert type="success" show-icon>
                Defacing completed! Please check the defacing results and proceed to the next page.
            </el-alert>
        </div>
        <div v-if="session.status == 'failed'">
            Failed!
            <pre class="status">{{session.status_msg}}</pre>
        </div>
    </div>

    <br>
    <el-form>
        <el-form-item>
            <el-button v-if="!isDefacing && ezbids.defacingMethod && !session.deface_finish_date" @click="submit" type="success">Run Deface</el-button>
            <el-button @click="cancel" v-if="isDefacing" type="warning">Cancel Defacing</el-button>
            <el-button @click="reset" v-if="session.deface_begin_date && session.deface_finish_date">Reset Deface</el-button>
        </el-form-item>
    </el-form>

    <table class="table table-sm" v-if="ezbids.defacingMethod">
        <thead>
            <tr>
                <th></th>
                <th>Original</th>
                <th>Defaced</th>
            </tr>
        </thead>
        <tr v-for="anat in getAnatObjects" :key="anat.idx">
            <td>
                <div style="margin-bottom: 0; font-size: 85%; line-height: 200%;">
                    <span><small>sub</small> {{anat._entities.subject}} </span>
                    <span v-if="anat._entities.session">/ <small>ses</small> {{anat._entities.session}} </span>
                </div>
                <el-tag type="info" size="mini">#{{anat.series_idx}}</el-tag>
                &nbsp;
                <datatype :type="anat._type" :series_idx="anat.series_idx" :entities="anat.entities"/> 
            </td>
            <td width="40%">
                <el-radio v-model="anat.defaceSelection" label="original">Use Original</el-radio>
                <a :href="getURL(anat.pngPath)">
                    <img style="width: 100%" :src="getURL(anat.pngPath)"/>
                </a>
            </td>
            <td width="40%">
                <el-radio v-model="anat.defaceSelection" label="defaced">Use Defaced (when finish defacing)</el-radio>
                <a :href="getDefacedThumbURL(anat)" v-if="anat.defaced">
                    <img style="width: 100%" :src="getDefacedThumbURL(anat)+'?nocache='+Date.now()"/>
                </a>
                <p v-if="session.status == 'defacing' && !anat.defaced" class="missingThumb"><small>Defacing ...</small></p>
                <p v-if="anat.defaceFailed" class="missingThumb fail"><small>Defacing Failed</small></p>
            </td>
        </tr>
    </table>

</div>
</template>

<script lang="ts">

import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue'                                                                                                                                                  
import datatype from './components/datatype.vue' 

import { IObject } from './store'

import { ElNotification } from 'element-plus'

export default defineComponent({
    components: {
        datatype,
    },
    data() {
        return {
            //tm: null, //timeout for reloading deface.log
            //defacingMethod: "",
        }
    },

    computed: {
        ...mapState(['ezbids', 'config', 'session', 'bidsSchema']),
        ...mapGetters(['getBIDSEntities', 'getURL', 'findSubject', 'findSession', 'getAnatObjects']),
        
        isDefacing() {
            // @ts-ignore
            return ["deface", "defacing"].includes(this.session.status);
        }
    },

    mounted() {
        //initialize all anat to use defaced image by default
        this.getAnatObjects.forEach((o:IObject)=>{
            if(!o.defaceSelection) o.defaceSelection = "defaced";
        });
    },
    
    methods: {
        changeMethod() {
            if(this.ezbids.defacingMethod) {
                console.log("switching to defaced for all anat");
                this.getAnatObjects.forEach((o:IObject)=>{
                    o.defaceSelection = "defaced";
                });
            } else {
                console.log("switching to original for all anat");
                this.getAnatObjects.forEach((o:IObject)=>{
                    o.defaceSelection = "original";
                });   
            }
        },

        getDefacedThumbURL(anat: IObject) {
            //find the image path first
            let path = anat.paths.find(p=>p.endsWith(".nii.gz"));
            //guess the image path
            path += ".defaced.nii.gz.png";
            return this.getURL(path)
        },

        cancel() {
            fetch(this.config.apihost+'/session/'+this.session._id+'/canceldeface', {
                method: "POST", 
                headers: {'Content-Type': 'application/json; charset=UTF-8'},
            }).then(res=>res.text()).then(status=>{
                if(status != "ok") {
                    ElNotification({ title: 'Failed', message: 'Failed to cancel defacing'});
                } else {
                    ElNotification({ title: 'Success', message: 'Requested to cancel defacing..'});
                }
                this.$store.dispatch("loadSession", this.session._id);
            });
        },

        reset() {
            fetch(this.config.apihost+'/session/'+this.session._id+'/resetdeface', {
                method: "POST", 
                headers: {'Content-Type': 'application/json; charset=UTF-8'},
            }).then(res=>res.text()).then(status=>{
                if(status != "ok") {
                    ElNotification({ title: 'Failed', message: 'Failed to reset defacing'});
                }
                this.getAnatObjects.forEach((anat: IObject)=>{
                    delete anat.defaced;
                    delete anat.defaceFailed;
                    anat.defaceSelection = "defaced"; 
                });
                this.$store.dispatch("loadSession", this.session._id);
            });
        },

        submit() {
            const list = this.getAnatObjects.map((o:IObject)=>{
                return {idx: o.idx, path: o.paths.find(p=>p.endsWith(".nii.gz"))};
            });

            //reset current status for all stats (in case it's ran previously)
            this.getAnatObjects.forEach((o:IObject)=>{
                delete o.defaced;
            });

            console.log("sending deface reque3st", list);
            fetch(this.config.apihost+'/session/'+this.session._id+'/deface', {
                method: "POST", 
                headers: {'Content-Type': 'application/json; charset=UTF-8'},
                body: JSON.stringify({
                    list,
                    method: this.ezbids.defacingMethod,
                }),
            }).then(res=>res.text()).then(status=>{
                if(status != "ok") {
                    ElNotification({ title: 'Failed', message: 'Failed to submit deface request'});
                }
                this.$store.dispatch("loadSession", this.session._id);
                //this.$root.pollSession();
            }); 
        },

        isValid(cb: (v?: string)=>void) {
            if(!this.ezbids.defacingMethod) return cb();
            if(!this.session.deface_begin_date) {
                return cb("Please run deface");
            }
            if(this.session.deface_begin_date && this.session.status == "failed") {
                //let's assume it's the defacing that failed
                let err = undefined;
                this.getAnatObjects.forEach((o:IObject)=>{
                    if(o.defaceSelection == "defaced" && !o.defaced) err = "Please set to use original image for deface-failed images";
                });
                return cb(err);
            }
            if(!this.session.deface_finish_date) {
                return cb("Please wait for defacing to finish");
            }
            cb();
        },

    },
});
</script>

<style scoped>
.deface {
    position: fixed;
    top: 0;
    bottom: 60px;
    left: 210px;
    right: 0;
    overflow: auto;
}
.table td {
    border-top: 1px solid #eee;
    padding-top: 5px;
}
.table th {
    text-align: left;
    padding: 10px 0;
}
.table td {
    vertical-align: top;
}
.missingThumb {
    background-color: #f0f0f0;
    padding: 10px 20px;
    box-sizing: border-box;
    margin: 0;
}
.missingThumb.fail {
    background-color: #c44;
    color: white;
}
.el-form-item {
    margin-bottom: 0;
}
pre.status {
    background-color: #666;
    color: white;
    height: 125px;
    overflow: auto;
    padding: 10px;
    margin-bottom: 5px;
}
</style>

