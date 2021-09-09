<template>
<div style="padding: 20px;">

    <div class="series-list">
        <div v-for="(s, series_idx) in ezbids.series" :key="s.series_idx" 
            class="series-item" 
            :class="{'selected': ss === s}" 
            @click="ss = s">
            <el-tag type="info" size="mini" title="Series index">#{{series_idx}}</el-tag>
            &nbsp;
            <datatype :type="s.type" :series_idx="series_idx" :entities="s.entities" :class="{excluded: s.type == 'exclude'}"/>
            <small style="opacity: 0.7;">({{s.SeriesDescription}})</small>
            &nbsp;
            <el-tag type="info" effect="plain" size="mini" title="Number of objects">{{s.object_indices.length}} objs</el-tag>
            &nbsp;
            <el-badge v-if="s.validationErrors.length > 0" type="danger" :value="s.validationErrors.length" style="margin-left: 5px;">
                <small/>
            </el-badge>
        </div>
        <pre v-if="config.debug">{{ezbids.series}}</pre>
    </div>

    <div v-if="!ss" style="margin-left: 450px; padding: 20px; background-color: #eee;">
        <p>Please update how you'd like to map each dicom SeriesDescription to BIDS datatype/entities.</p>
        <p>The information you specify here will be applied to all subjects that uses matching SeriesDescription. You can also override this information later for each subject.</p>
       <div style="background-color: white; padding: 10px; color: #666;">
            <i class="el-icon-back"/> Please select a series to view/edit
        </div>
    </div>
    <div class="series-detail">
        <div v-if="ss">
            <h5>BIDS Datatype / Entities</h5>
            <el-form label-width="150px">
                <el-alert v-if="ss.message" :title="ss.message" type="warning"/>
                <div style="margin-bottom: 10px;">
                    <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in ss.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                </div>

                <el-form-item label="Datatype">
                    <el-select v-model="ss.type" reqiured placeholder="(exclude)" size="small" @change="validate(ss)" style="width: 100%">
                        <el-option value="exclude">(Exclude from BIDS conversion)</el-option>
                        <el-option-group v-for="type in bidsSchema.datatypes" :key="type.label" :label="type.label">
                            <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                {{type.label}} / {{subtype.label}}
                            </el-option>
                        </el-option-group>
                    </el-select>
                    <br>
                </el-form-item>

                <div v-if="ss.type && ss.type.startsWith('fmap/')">
                    <el-form-item label="FieldMap For">
                        <el-select v-model="ss.forType" reqiured placeholder="(unknown)" size="small" @change="validate(ss)">
                            <el-option value="dwi/dwi">Diffusion</el-option>
                            <el-option value="func/bold">Functional/Bold</el-option>
                        </el-select>
                        <br>
                        <small style="position: relative; top: -8px;">* Datatype that this fmap is intended for. Used to help assining correct IntendedFor field</small>
                    </el-form-item>
                </div>
            
                <div v-if="ss.type">
                    <el-form-item v-for="(v, entity) in getSomeEntities(ss.type)" :key="entity" 
                        :label="entity.toString()+'-'+(v=='required'?' *':'')" style="width: 350px">
                        <el-popover v-if="bidsSchema.entities[entity]" width="300" trigger="focus" placement="right-start"
                            :title="bidsSchema.entities[entity].name" 
                            :content="bidsSchema.entities[entity].description">
                            <template #reference>
                                <el-input v-model="ss.entities[entity]" size="small" :required="v == 'required'" @change="validate(ss)"/>
                            </template>
                        </el-popover>
                    </el-form-item>
                </div>

                <el-form-item label="Common Metadata">
                    <small>All objects under this series contain the following common metadata.</small>
                    <p style="margin-top: 0; margin-bottom: 0;"> 
                        <el-tag type="info" size="mini"><small>SeriesDescription: 
                        {{ss.SeriesDescription}}</small></el-tag>&nbsp;
                        <el-tag type="info" size="mini"><small>EchoTime: {{ss.EchoTime}}</small></el-tag>&nbsp;
                        <el-tag type="info" size="mini"><small>ImageType: {{ss.ImageType}}</small></el-tag>&nbsp;
                        <el-tag type="info" size="mini"><small>RepetitionTime: 
                        {{ss.RepetitionTime}}</small></el-tag>&nbsp;
                    </p>
                </el-form-item>
            </el-form>

            <p style="border-top: 1px solid #eee; padding: 10px 20px;">
                <small>The following objects belongs to this series.</small>
            </p>
            <div v-for="object_idx in ss.object_indices" :key="object_idx" class="object">
                <i class="el-icon-caret-right"/>&nbsp;
                <div v-for="(v, k) in ezbids.objects[object_idx]._entities" :key="object_idx+'.'+k.toString()" style="display: inline-block; font-size: 85%;">
                    <span v-if="v" style="margin-right: 10px;">
                        {{k}}-<b>{{v}}</b>
                    </span>
                </div>
                <div style="float: right">
                    <el-tag size="mini" type="info">filesize: {{prettyBytes(ezbids.objects[object_idx].analysisResults.filesize)}}</el-tag>&nbsp;
                    <el-tag size="mini" type="info">volumes: {{ezbids.objects[object_idx].analysisResults.NumVolumes}}</el-tag>&nbsp;
                </div>
                <div style="margin-left: 25px">
                    <p v-if="ezbids.objects[object_idx].pngPath">
                        <small><b>Preview</b></small>
                        <a :href="getURL(ezbids.objects[object_idx].pngPath)">
                            <img style="width: 100%" :src="getURL(ezbids.objects[object_idx].pngPath)"/>
                        </a>
                    </p>

                    <small><b>Files</b></small>
                    <div v-for="(item, idx) in ezbids.objects[object_idx].items" :key="idx">
                        <pre>{{item.path}}</pre>
                        <showfile v-if="['json', 'bval', 'bvec'].includes(item.path.split('.').pop())" :path="item.path"/>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
</template>

<script lang="ts">

import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue'

import showfile from './components/showfile.vue'                                                                                                                                                     
import datatype from './components/datatype.vue'   

import { prettyBytes } from './filters'

import { Series } from './store'

import { validateEntities } from './lib'

export default defineComponent({

    
    components: {
        datatype,
        showfile,
    },
    

    data() {
        return {
            showInfo: {} as any,
            ss: null as Series|null, //selected series
        }
    },
    
    computed: {
        ...mapState(['ezbids', 'bidsSchema', 'config']),
        ...mapGetters(['getBIDSEntities', 'getURL']), //doesn't work with ts?
    },

    mounted() {
        console.log("mounting series")
        this.validateAll();
        console.log("done mounting series");
    },
    

    methods: {
        
        prettyBytes,

        getSomeEntities(type: string): any {
            let entities = this.getBIDSEntities(type);

            //we don't want user set sub/ses through series
            delete entities.subject;
            delete entities.session;

            return entities;
        },

        toggleInfo(entity: string) {
            this.showInfo[entity] = !this.showInfo[entity];
        },   

        validateAll() {
            this.ezbids.series.forEach(this.validate);
        },

        validate(s: Series|null) {
            if(!s) return;

            s.validationErrors = [];
            if(s.type != "exclude") {
                s.validationErrors = validateEntities(s.entities);
            }

            let entities = this.getBIDSEntities(s.type);
            for(let k in this.getSomeEntities(s.type)) {
                if(entities[k] == "required") {
                    if(!s.entities[k]) {
                        s.validationErrors.push("entity: "+k+" is required.");
                    }
                }
            }
        },

        isValid(cb: (v?: string)=>void) {
            console.log("series page validation");
            this.validateAll();

            let err = undefined;
            this.ezbids.series.forEach((s: Series)=>{
                if(s.validationErrors.length > 0) err = "Please correct all issues";
            });
            return cb(err);
        }
    },
});

</script>

<style scoped>
.series-list {
    font-size: 90%;
    position: fixed;
    top: 0;
    bottom: 60px;
    left: 200px;
    width: 450px;
    overflow: auto;
    padding: 5px 10px;
    overflow-y: scroll;
    box-sizing: border-box;
}
.series-detail {
    position: fixed;
    top: 0;
    bottom: 60px;
    overflow-y: auto;
    right: 0;
    left: 650px;
    padding: 10px;
    z-index: 1;
}
.el-form-item {
    margin-bottom: 0;
}
.series-item {
    transition: background-color 0.3s;
    padding: 2px;
}
.series-item:hover {
    background-color: #ddd;
    cursor: pointer;
}
.selected {
    background-color: #d9ecff;
}
.object {
    padding: 0 20px;
    margin-bottom: 20px;
}
.object p {
    margin: 0;
}
.sidecar {
    height: 300px;
    overflow: auto;
    box-shadow: 2px 2px 4px #0005;
}
.excluded {
    opacity: 0.4;
}
h5 {
    padding: 0 20px;
}
</style>