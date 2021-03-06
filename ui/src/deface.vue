<template>
<div v-if="$root.currentPage.id == 'deface'" style="padding: 20px;">
    <el-form v-if="$root.session.status == 'analyzed' || $root.session.status == 'finished'">
        <p>
            If you'd like to deface all anatomical images, please select a defacing method and click <b>Run Deface</b> button. 
        </p>
        <p>
            Otherwise, you can skip this page.
        </p>

        <el-alert v-if="anats.length == 0" type="warning">No anatomy files to deface</el-alert>
        <el-form-item v-if="anats.length">
            <el-select v-model="$root.defacingMethod" placeholder="Select a defacing method" style="width: 300px;">
                <el-option value="" label="Don't Deface"/>
                <el-option value="quickshear" label="Quickshear (recommended)"/>
                <el-option value="pydeface" label="pyDeface"/>
            </el-select>

            <!--sub options-->
            <div v-if="$root.defacingMethod == 'quickshear'">
                <small>Use ROBEX and QuickShear Average processing time. 1min per image</small>
            </div>
            <div v-if="$root.defacingMethod == 'pydeface'">
                <small>pydeface uses fsl to align facial mask template. 5min per image</small>
            </div>
        </el-form-item>
    </el-form>

    <div v-if="defacing">
        Defacing ... 
        <pre class="status">{{$root.session.status_msg}}</pre>
        <!--debug-->
    </div>
    <div v-if="$root.session.status == 'defaced'">
        Defacing completed! Please check the defacing results and proceed to the next page.
        <!--
        <pre class="status">{{$root.session.status_msg}}</pre>
        -->
    </div>
    <div v-if="$root.session.status == 'failed'">
        Failed!
        <pre class="status">{{$root.session.status_msg}}</pre>
    </div>

    <table class="table table-sm" v-if="$root.defacingMethod">
        <thead>
            <tr>
                <th></th>
                <th>Original</th>
                <th>Defaced</th>
            </tr>
        </thead>
        <tr v-for="anat in anats" :key="anat.idx">
            <td>
                <div style="margin-bottom: 0; font-size: 85%; line-height: 200%;">
                    <span><small>sub</small> {{anat._entities.subject}} </span>
                    <span v-if="anat._entities.session">/ <small>ses</small> {{anat._entities.session}} </span>
                </div>
                <el-tag type="info" size="mini">sn {{anat.SeriesNumber}}</el-tag>
                &nbsp;
                <datatype :type="anat._type" :series_id="anat.series_id" :entities="anat.entities"/> 
            </td>
            <td width="40%">
                <el-radio v-model="anat.defaceSelection" label="original">Use Original</el-radio>
                <a :href="$root.getURL(anat.pngPath)">
                    <img width="100%" :src="$root.getURL(anat.pngPath)"/>
                </a>
            </td>
            <td width="40%">
                <el-radio v-model="anat.defaceSelection" label="defaced">Use Defaced</el-radio>
                <a :href="getDefacedThumbURL(anat)" v-if="anat.defaced">
                    <img width="100%" :src="getDefacedThumbURL(anat)"/>
                </a>
                <p v-if="!anat.defaced" class="missingThumb"><small>Not yet defaced</small></p>
                <p v-if="anat.defaceFailed" class="missingThumb fail"><small>Defacing Failed</small></p>
            </td>
        </tr>
    </table>
         
    <el-form>
        <el-form-item class="page-action">
            <el-button @click="back">Back</el-button>
            <el-button @click="reset" v-if="defacing || $root.session.status == 'defaced'">Reset Deface</el-button>
            <el-button type="primary" @click="next" :disabled="defacing" v-if="($root.session.status != 'analyzed' || $root.defacingMethod == '')" 
                style="float: right;">Next</el-button>
            <el-button v-if="$root.session.status != 'defaced' && ($root.defacingMethod && !defacing)"
                @click="submit" type="success" style="float: right;">Run Deface</el-button>
        </el-form-item>
    </el-form>
</div>
</template>

<script>

import Vue from 'vue'

import datatype from '@/components/datatype'

export default {
    components: {
        datatype,
    },
    data() {
        return {
            defacing: false,

            tm: null, //timeout for reloading deface.log
        }
    },

    computed: {
        anats() {
            return this.$root.objects.filter(o=>o._type.startsWith('anat') && !o._exclude)
        }
    },

    watch: {

        /*
        '$root.session.status'() {
            this.defacing = (this.$root.session.status == 'defacing');
            console.log(this.$root.session.status, this.defacing);
        },
        */

        '$root.currentPage'(v) {
            clearTimeout(this.tm);
            if(v.id == 'deface') {
                this.$root.objects/*filter(o=>o._type == 'anat/T1w')*/.forEach(anat=>{
                    if(!anat.defaced) Vue.set(anat, "defaced", false);
                    if(!anat.defaceSelection) Vue.set(anat, "defaceSelection", "defaced");
                });

                this.loadLogAndRepeat();
            }
        },
    },
    
    methods: {
        getDefacedThumbURL(anat) {
            //find the image path first
            let path = anat.paths.find(p=>p.endsWith(".nii.gz"));
            //guess the image path
            path += ".defaced.nii.gz.png";
            return this.$root.getURL(path)
        },

        reset() {
            //TODO - make an API call to stop the defacing job (doesn't exist yet)

            this.defacing = false;
            this.$root.objects/*.filter(o=>o._type == 'anat/T1w')*/.forEach(anat=>{
                Vue.set(anat, "defaced", false);
                Vue.set(anat, "defaceFailed", false);
                Vue.set(anat, "defaceSelection", "defaced");
            });
            this.$root.session.status = "analyzed";
        },

        loadLogAndRepeat() {
            if(this.$root.session.status == "defacing" || this.$root.session.status == "defaced") {
                fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/deface.finished').then(res=>res.text()).then(data=>{
                    if(!data) return;
                    let idxs = data.trim().split("\n");
                    idxs.forEach(idx=>{
                        let o = this.$root.objects.find(o=>o.idx == idx);
                        if(!o) console.error("can't find", idx);
                        o.defaced = true;
                    });
                }).catch(console.error);

                fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/deface.failed').then(res=>res.text()).then(data=>{
                    if(!data) return;
                    let idxs = data.trim().split("\n");
                    idxs.forEach(idx=>{
                        let o = this.$root.objects.find(o=>o.idx === idx);
                        if(!o) console.error("can't find", idx);
                        o.defaceFailed = true;
                    });
                }).catch(console.error);    
            }
            if(["defaced", "failed", "analyzed"].includes(this.$root.session.status)) this.defacing = false;

            //load next
            this.tm = setTimeout(this.loadLogAndRepeat, 5*1000);
        },

        next() {
            this.$root.changePage("finalize");
        },

        back() {
            this.$root.changePage("object");
        },

        submit() {
            this.defacing = true;

            const list = this.anats.map(o=>{
                return {idx: o.idx, path: o.paths.find(p=>p.endsWith(".nii.gz"))};
            });

            fetch(this.$root.apihost+'/session/'+this.$root.session._id+'/deface', {
                method: "POST", 
                headers: {'Content-Type': 'application/json; charset=UTF-8'},
                body: JSON.stringify({
                    list,
                    method: this.$root.defacingMethod,
                }),
            }).then(res=>res.text()).then(status=>{
                if(status != "ok") {
                    this.$notify({ title: 'Failed', message: 'Failed to submit deface request'});
                }
                this.$root.pollSession();
            }); 
        },
    },

}
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
    background-color: #eee;
    padding: 30px;
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

