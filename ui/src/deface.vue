<template>
<div v-if="$root.currentPage.id == 'deface'" style="padding: 20px;">
    <el-form v-if="
        $root.session.status == 'analyzed' || 
        $root.session.status == 'finished'">
        <p>
            If you'd like to deface all T1 anatomical images, please select a defacing method and click <b>Deface</b> button. 
        </p>
        <p>
            Otherwise, you can skip this page.
        </p>

        <el-form-item>
            <el-select v-model="$root.defacingMethod" placeholder="Select a defacing method" style="width: 300px;">
                <el-option value="" label="Don't Deface"/>
                <el-option value="quickshear" label="quickshear"/>
                <el-option value="pydeface" label="pydeface"/>
            </el-select>

            <!--sub options-->
            <div v-if="$root.defacingMethod == 'quickshear'">
                <small>Use ROBEX and QuickShear Average processing time. 1min per image</small>
            </div>
            <div v-if="$root.defacingMethod == 'pydeface'">
                <small>pydeface uses fsl to align facial mask template. 5min per image</small>
            </div>
            <div v-if="$root.defacingMethod && !defacing">
                <el-button @click="submit" type="success">Run Deface!</el-button>
            </div>
        </el-form-item>
    </el-form>

    <div v-if="$root.session.status == 'deface' || $root.session.status == 'defacing'">
        <el-button @click="reset" size="small" style="float: right;">Reset Deface</el-button>
        Defacing..
        <pre>{{$root.session.status_msg}}</pre>

        <!--debug-->
    </div>
    <div v-if="$root.session.status == 'defaced'">
        <el-button @click="reset" size="small" style="float: right;">Reset Deface</el-button>
        Defacing completed! Please proceed to the next page.
        <pre>{{$root.session.status_msg}}</pre>
    </div>
    <div v-if="$root.session.status == 'failed'">
        <el-button @click="reset" size="small" style="float: right;">Reset Deface</el-button>
        Failed!
        <pre>{{$root.session.status_msg}}</pre>
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
                <div style="margin-bottom: 0; font-sisze: 90%; line-height: 200%;">
                    <span><small>sub</small> {{anat._entities.subject}} </span>
                    <span v-if="anat._entities.session">/ <small>ses</small> {{anat._entities.session}} </span>
                </div>
                <el-tag type="info" size="mini">Series# {{anat.SeriesNumber}}</el-tag>
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
            </td>
        </tr>
    </table>
         
    <el-form>
        <el-form-item class="page-action">
            <el-button @click="back">Back</el-button>
            <el-button type="primary" @click="next" :disabled="$root.session.status == 'deface' || $root.session.status == 'defacing'" style="float: right;">Next</el-button>
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
            console.dir(this.$root.objects);
            return this.$root.objects.filter(o=>o._type == 'anat/T1w' && !o._exclude)
        }
    },

    watch: {

        '$root.currentPage'(v) {
            clearTimeout(this.tm);
            if(v.id == 'deface') {
                console.log("deface page");

                this.$root.objects.filter(o=>o._type == 'anat/T1w').forEach(anat=>{
                    if(!anat.defaced) Vue.set(anat, "defaced", false);
                    if(!anat.defaceSelection) Vue.set(anat, "defaceSelection", "defaced");
                });

                this.startLogLoader();
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
            this.defacing = false;
            this.$root.objects.filter(o=>o._type == 'anat/T1w').forEach(anat=>{
                Vue.set(anat, "defaced", false);
                Vue.set(anat, "defaceSelection", "defaced");
            });
            this.$root.session.status = "analyzed";
        },

        startLogLoader() {
            fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/deface.finished').then(res=>res.text()).then(data=>{
                let idxs = data.trim().split("\n");
                idxs.forEach(idx=>{
                    let o = this.$root.objects.find(o=>o.idx == idx);
                    if(!o) console.error("can't find", idx);
                    o.defaced = true;
                });
            });

            //load next
            this.tm = setTimeout(this.startLogLoader, 5*1000);
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
                this.defacing = false;
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
    width: 500px;
    height: 185px;
    box-sizing: border-box;
    margin: 0;
}
.el-form-item {
    margin-bottom: 0;
}
</style>
