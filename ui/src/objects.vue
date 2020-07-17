<template>
<div class="objects">
    <el-row :gutter="10">
    <el-col :span="8">
        <h4>BIDS Structure</h4>
        <div v-for="(o_sub, sub) in $root.subs" :key="sub" style="font-size: 90%;">
            <span v-if="sub != ''" class="hierarchy" style="opacity: 0.8;"><i class="el-icon-user-solid"/> <small>sub</small> {{sub}} <small>({{o_sub.objects.length}})</small></span>
            <div v-for="(o_ses, ses) in o_sub.sess" :key="ses" :class="{'left-border': ses != ''}">
                <span v-if="ses != ''" class="hierarchy" style="opacity: 0.8;"><i class="el-icon-time"/> <small>ses</small> {{ses}} <!--<small>({{o_ses.objects.length}})</small>--></span>
                <div v-for="(o_run, run) in o_ses.runs" :key="run" class="hierarchy">
                    <span v-if="run != ''" style="opacity: 0.8; padding-left: 8px;"><small>run</small> {{run}} <!--({{o_run.objects.length}})--></span>
                    <div class="left-border clickable" :class="{'selected': selected === o_run.objects}" @click="select(o_run.objects, sub, ses, run)">
                        <div v-for="(o, idx) in o_run.objects" :key="idx" style="padding: 2px;">
                            <datatype :o="o"/>
                            <el-badge v-if="o.validationErrors.length > 0" type="danger" 
                                :value="o.validationErrors.length" 
                                style="margin-left: 5px;"/>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </el-col>
    <el-col :span="16">
        <p v-if="!selected"><small>Please select data objects on the left menu.</small></p>
        <div v-if="selected">
            <div>
                <el-form label-width="100px">
                    <el-form-item label="Hierarchy">
                        <el-row :gutter="10">
                            <el-col :span="8">
                                <!--
                                <div class="sub-title">Subject</div>
                                -->
                                <el-input v-model="selected_sub" @change="changeSelectedH" size="small">
                                    <template slot="prepend">Subject</template>
                                </el-input>
                            </el-col>
                            <el-col :span="8">
                                <el-input v-model="selected_ses" @change="changeSelectedH" size="small">
                                    <template slot="prepend">Session</template>
                                </el-input>
                            </el-col>
                            <el-col :span="6">
                                <el-input v-model="selected_run" @change="changeSelectedH" size="small">
                                    <template slot="prepend">Run</template>
                                </el-input>
                            </el-col>
                        </el-row>
                    </el-form-item>
                </el-form>
            </div>
            <div v-for="(o, idx) in selected" :key="idx" class="object">
                <div style="margin-bottom: 10px;">
                    <el-alert type="error" v-for="(error, idx) in o.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                </div>

                <el-form label-width="100px">
                    <div style="float: right;">
                        <el-checkbox v-model="o.include" title="Include this object in the BIDS output" @change="validateAndCheck(o)">Include</el-checkbox>
                    </div>
                    <br clear="both">
                    <div :class="{'object-exclude': !o.include}">
                        <el-form-item label="Series" style="clear: both">
                            {{o.SeriesDescription}}
                            <el-tag type="info" size="mini"><small>{{o.SeriesNumber}}</small></el-tag>
                        </el-form-item>
                        <el-form-item label="Datatype" style="clear: both">
                            <el-select v-model="o.type" placeholder="Modality" size="small" style="width: 100%">
                                <el-option-group v-for="type in $root.datatypes" :key="type.label" :label="type.label">
                                    <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                        {{type.label}} / {{subtype.label}}
                                    </el-option>
                                </el-option-group>
                            </el-select>
                        </el-form-item>

                        <!-- datatype specific fields-->
                        <el-form-item v-if="o.type.startsWith('func/')" label="Task Name">
                            <el-input v-model="o.labels.task" size="small" @change="validateAndCheck(o)" required/>
                        </el-form-item>

                        <el-form-item v-for="(item, idx) in o.items" :key="idx" :label="item.id">
                            <el-select v-model="item.path" placeholder="Source path" size="small" style="width: 100%">
                                <el-option v-for="(path, idx) in o.paths" :key="idx" :label="path" :value="path"/>
                            </el-select>
                            <div v-if="item.sidecar" style="box-shadow: 1px 1px 3px #0002; border-radius: 5px; padding: 10px; background-color: #fcfcfc;">
                                <b style="opacity: 0.5;">Sidecar</b>
                                <kveditor :kv="item.sidecar"/>
                            </div>
                         </el-form-item>
                    </div>
                 </el-form>
            </div>
        </div><!--selected != null-->
    </el-col>
    </el-row>
</div>
</template>

<script>

//import Vue from 'vue'

import kveditor from '@/components/kveditor'
import datatype from '@/components/datatype'

export default {
    //props: [ 'objects' ], 
    //store,
    components: {
        kveditor,
        datatype,
    },
    data() {
        return {
            //deprecated by $root.datatypes
            /*
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
            */

            //organize objects by hierarchy
            selected: null,
            selected_sub: "",
            selected_ses: "",
            selected_run: "",
        }
    },

    /*
    watch: {
        '$root.objects': {
            deep: true,
            handler(v, ov) {
                if(v.length == 0) return; //prevent infinite loop in case objects is empty
                if(ov.length == 0) { 
                    this.analyzeH();
                    console.log("validing all");
                    this.$root.objects.forEach(o=>{
                        this.$root.validateObject(o);
                    });
                    this.$root.validated = this.isAllValid();
                }
            },
        },
    },
    */

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
            this.$root.organizeObjects();
            
            //find the selected objects again
            this.selected = this.$root.subs[this.selected_sub].sess[this.selected_ses].runs[this.selected_run].objects;
        },

        validateAndCheck(o) { 
            this.$root.validateObject(o);
            this.$root.validated = this.isAllValid(); 
        },

        isAllValid() {
            console.log("checking valid");
            for(let o of this.$root.objects) {
                if(!o.include) continue;
                if(o.validationErrors.length > 0) {
                    console.log("no good");
                    return false;
                }
            }
            console.log("all good");
            return true;
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
line-height: 100%;
}
.clickable {
transition: background-color 0.3s;
}
.selected {
background-color: #d9ecff;
}
.clickable:hover {
background-color: #ddd;
cursor: pointer;
}
.left-border {
margin-left: 8.5px; 
padding-left: 4px; 
border-left: 2px solid #3331;
padding-top: 4px;
}
.exclude {
opacity: 0.5;
}
.object {
margin: 5px 0;
padding: 5px;
border-top: 1px solid #0001;
}
.object-exclude {
opacity: 0.5;
}
.sub-title {
font-size: 85%;
margin-bottom: 5px;
}
.el-form-item {
margin-bottom: 0;
}
</style>

