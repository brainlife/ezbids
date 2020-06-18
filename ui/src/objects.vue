<template>
<div class="objects">
    <div class="side">
        <h4>BIDS Structure</h4>
        <div v-for="(o_sub, sub) in subs" :key="sub" style="font-size: 90%;">
            <span v-if="sub != ''" class="hierarchy" style="opacity: 0.8;"><i class="el-icon-user-solid"/> <small>sub</small> {{sub}} <small>({{o_sub.objects.length}})</small></span>
            <div v-for="(o_ses, ses) in o_sub.sess" :key="ses" :class="{'left-border': ses != ''}">
                <span v-if="ses != ''" class="hierarchy" style="opacity: 0.8;"><i class="el-icon-time"/> <small>ses</small> {{ses}} <!--<small>({{o_ses.objects.length}})</small>--></span>
                <div v-for="(o_run, run) in o_ses.runs" :key="run" @click="select(o_run.objects, sub, ses, run)" 
                    class="hierarchy clickable" :class="{'selected': selected === o_run.objects}">
                    <span v-if="run != ''" style="opacity: 0.8;"><small>run</small> {{run}} <!--({{o_run.objects.length}})--></span>
                    <div class="left-border">
                        <div v-for="(o, idx) in o_run.objects" :key="idx" style="padding-left: 6px; padding: 2px;">
                            <datatype :o="o"/>
                            <el-badge v-if="o.validationErrors.length > 0" type="danger" 
                                :value="o.validationErrors.length" 
                                style="margin-left: 5px;"/>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="main">
        <p v-if="!selected"><small>Please select data objects on the left menu.</small></p>
        <div v-if="selected">
            <div>
                <el-row :gutter="10">
                    <el-col :span="4">
                        <div class="sub-title">Subject</div>
                        <el-input v-model="selected_sub" @change="changeSelectedH" size="small"/>
                    </el-col>
                    <el-col :span="4">
                        <div class="sub-title">Session</div>
                        <el-input v-model="selected_ses" @change="changeSelectedH" size="small"/>
                    </el-col>
                    <el-col :span="4">
                        <div class="sub-title">Run</div>
                        <el-input v-model="selected_run" @change="changeSelectedH" size="small"/>
                    </el-col>
                </el-row>
            </div>
            <div v-for="(o, idx) in selected" :key="idx" class="object" :class="{'object-exclude': !o.include}">
                <div style="margin-bottom: 10px;">
                    <el-alert type="error" v-for="(error, idx) in o.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                </div>

                <el-form label-width="100px">
                    <div style="float: right;">
                        <el-checkbox v-model="o.include" title="Include this object in the BIDS output">Include</el-checkbox>
                    </div>
                    <el-form-item label="Datatype" style="clear: both">
                        <el-select v-model="o.type" placeholder="Modality" size="small" style="width: 100%">
                            <el-option-group v-for="type in types" :key="type.label" :label="type.label">
                                <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                    {{type.label}} / {{subtype.label}}
                                </el-option>
                            </el-option-group>
                        </el-select>
                    </el-form-item>

                    <!-- datatype specific fields-->
                    <el-form-item v-if="o.type.startsWith('func/')" label="Task Name">
                        <el-input v-model="o.hierarchy.task" size="small" @change="validate(o)" required/>
                    </el-form-item>

                    <el-form-item v-for="(item, idx) in o.items" :key="idx" :label="item.id">
                        <el-select v-model="item.path" placeholder="Source path" size="small" style="width: 100%">
                            <el-option v-for="(path, idx) in o.paths" :key="idx" :label="path" :value="path"/>
                        </el-select>
                        <div v-if="item.sidecar" style="background-color: #eee; padding: 10px;">
                            <b style="opacity: 0.5;">Sidecar</b>
                            <kveditor :kv="item.sidecar"/>
                        </div>
                     </el-form-item>
                 </el-form>
            </div>
        </div><!--selected != null-->
    </div>
</div>
</template>

<script>

import Vue from 'vue'

import kveditor from '@/components/kveditor'
import datatype from '@/components/datatype'

export default {
    //store,
    components: {
        kveditor,
        datatype,
    },
    data() {
        return {
            types: [
                {label: 'Anatomical', 
                    options: [
                        {value: 'anat/t1w', label: "t1w"},
                        {value: 'anat/t2w', label: "t2w"},
                        {value: 'anat/flair', label: "Flair"},
                    ]
                },
                {value: 'dwi', label: 'Diffusion', 
                    options: [
                        {value: 'dwi', label: "DWI"},
                    ]
                },
                {value: 'func', label: 'Functional',  
                    options: [
                        {value: 'func/bold', label: "Bold"}, 
                        {value: 'func/cbv', label: "Cerebral Blood Volume"},
                    ]
                },
                {value: 'fmap', label: 'Field Map', 
                    options: [
                        {value: 'fmap/2phasemag', label: "2 Phase images"},
                        {value: 'fmap/phasediff', label: "Phase Difference"},
                        {value: 'fmap/single', label: "single(real) image"},
                        {value: 'fmap/pepolar', label: "Multiple phase encoded"},
                    ]
                },
            ],

            //organize objects by hierarchy
            subs: {},
            selected: null,
            selected_sub: "",
            selected_ses: "",
            selected_run: "",
        }
    },
    watch: {
        '$root.objects'(v, ov) {
            if(ov.length == 0) {
                this.analyzeH();
                this.$root.objects.forEach(o=>{
                    this.validate(o);
                });
            }
        }
    },
    created() {
    },
    methods: {
        select(objects, sub, ses, run) {
            this.selected = objects;
            this.selected_sub = sub;
            this.selected_ses = ses;
            this.selected_run = run;
        },

        changeSelectedH() {
            this.selected.forEach(o=>{
                o.hierarchy.subject = this.selected_sub;
                o.hierarchy.session = this.selected_ses;
                o.hierarchy.run = this.selected_run;
            }); 
            this.analyzeH();
            
            //find the selected objects again
            this.selected = this.subs[this.selected_sub].sess[this.selected_ses].runs[this.selected_run].objects;
        },

        analyzeH() {
            this.subs = {}; 
            this.sess = {};
            this.runs = {};
            this.$root.objects.forEach(o=>{
                let sub = o.hierarchy.subject||"";
                let ses = o.hierarchy.session||"";
                let run = o.hierarchy.run||"";

                if(!this.subs[sub]) this.subs[sub] = { sess: {}, objects: []}; 
                this.subs[sub].objects.push(o);

                if(!this.subs[sub].sess[ses]) this.subs[sub].sess[ses] = { runs: {}, objects: [] };
                this.subs[sub].sess[ses].objects.push(o);

                if(!this.subs[sub].sess[ses].runs[run]) this.subs[sub].sess[ses].runs[run] = { objects: [] };
                this.subs[sub].sess[ses].runs[run].objects.push(o);
            });

            this.$root.objects.sort((a,b)=>{
                if(a.hierarchy.subject > b.hierarchy.subject) return 1;
                if(a.hierarchy.subject < b.hierarchy.subject) return -1;
                if(a.hierarchy.session > b.hierarchy.session) return 1;
                if(a.hierarchy.session < b.hierarchy.session) return -1;
                if(a.hierarchy.run > b.hierarchy.run) return 1;
                if(a.hierarchy.run < b.hierarchy.run) return -1;
                return 0;
            });
        },

        validate(o) {
            Vue.set(o, 'validationErrors', []);
            
            switch(o.type) {
            case "func/bold":
                if(!o.hierarchy.task) o.validationErrors.push("Task Name is required for func/bold");
            }
        },
    },
    computed: {

    },
}
</script>

<style scoped>
.item {
padding-bottom: 5px;
margin-bottom: 5px;
}
.hierarchy {
padding: 3px;
display: block;
}
.hierarchy.clickable {
transition: background-color 0.3s;
}
.hierarchy.selected {
background-color: #d9ecff;
}
.hierarchy.clickable:hover {
background-color: #ddd;
cursor: pointer;
}
.left-border {
margin-left: 8.5px; 
padding-left: 4px; 
border-left: 2px solid #3331;
}
.exclude {
opacity: 0.5;
}
.object {
margin: 5px 0;
padding: 5px;
border-top: 1px solid #0001;
}
.object.object-exclude {
opacity: 0.7;
background-color: #eee;
}
.sub-title {
font-size: 85%;
margin-bottom: 5px;
}
.el-form-item {
margin-bottom: 0;
}
.side {
    position: fixed;
    top: 110px;
    left: 10px;
    width: 250px;
    bottom: 0;
    overflow: auto;
}
.main {
    margin-left: 240px;
}
</style>

