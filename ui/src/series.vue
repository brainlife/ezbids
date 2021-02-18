<template>
    <div v-if="$root.currentPage.id == 'series'">
    <div class="series-list">
        <h4 style="padding-top: 20px;">Series Description / Datatype Mappings</h4>
        <div v-for="s in $root.series" :key="s.series_id" class="clickable" :class="{'selected': ss === s}" @click="ss = s" style="padding: 2px;">
            <el-tag type="info" size="mini" title="SeriesNumber">Series# {{s.SeriesNumber}}</el-tag>
            &nbsp;
            <el-tag type="plain" size="mini" title="Number of objects">{{s.object_indices.length}} obj</el-tag>
            &nbsp;
            <datatype :type="s.type" :series_id="s.series_id" :entities="s.entities" :class="{excluded: s.type == 'exclude'}"/>
            &nbsp;
            <small style="opacity: 0.7;">({{s.SeriesDescription}})</small>
            &nbsp;
            &nbsp;
            &nbsp;
            <el-badge v-if="s.validationErrors.length > 0" type="danger" :value="s.validationErrors.length" style="margin-left: 5px;">
                <small/>
            </el-badge>
        </div>
        <pre v-if="$root.config.debug">{{$root.series}}</pre>
    </div>

    <div v-if="!ss" style="margin-left: 450px; padding: 20px; background-color: #eee;">
        <p>Please update how you'd like to map each dicom SeriesDescription to BIDS datatype/entities.</p>
        <p>The information you specify here will be applied to all subjects that uses matching SeriesDescription. You can also override this information later for each subject.</p>
        <el-alert type="info" :closable="false">
            <i class="el-icon-back"/> Please select a series to view/edit
        </el-alert>
    </div>
    <div class="series-detail">
        <div v-if="ss">
            <h5>BIDS Datatype / Entities</h5>
            <el-form label-width="150px">
                <el-alert v-if="ss.message" :title="ss.message" type="info"/>
                <el-form-item label="Datatype">
                    <el-select v-model="ss.type" reqiured placeholder="(exclude)" size="small" @change="validate(ss)">
                        <el-option value="exclude">(Exclude from BIDS conversion)</el-option>
                        <el-option-group v-for="type in $root.datatypes" :key="type.label" :label="type.label">
                            <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                {{type.label}} / {{subtype.label}}
                            </el-option>
                        </el-option-group>
                    </el-select>
                    <br>
                </el-form-item>
                <!--<p style="margin-left: 100px; font-size: 80%;" v-if="ss.message">{{ss.message}}</p>-->
                <div v-if="ss.type">
                    <el-form-item v-for="(v, entity) in getSomeEntities(ss.type)" :key="entity" 
                        :label="entity+'-'+(v=='required'?' *':'')" style="width: 350px">
                        <el-popover v-if="$root.bids_entities[entity]" width="300" trigger="focus" placement="right-start"
                            :title="$root.bids_entities[entity].name" 
                            :content="$root.bids_entities[entity].description">
                            <el-input slot="reference" v-model="ss.entities[entity]" size="small" :required="v == 'required'" @change="validate(ss)"/>
                        </el-popover>
                    </el-form-item>
                </div>
                <div style="margin-bottom: 10px;">
                    <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in ss.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                </div>
            </el-form>
            <div style="background-color: #eee; padding: 10px 20px;">
                <small>All objects under this series contain the following common metadata</small>
                <p style="margin-top: 0; margin-bottom: 0;"> 
                    <el-tag type="info" size="mini"><small>EchoTime: {{ss.EchoTime}}</small></el-tag>&nbsp;
                    <el-tag type="info" size="mini"><small>ImageType: {{ss.ImageType}}</small></el-tag>&nbsp;
                    <el-tag type="info" size="mini"><small>MultibandAccelerationFactor: {{ss.MultibandAccelerationFactor}}</small></el-tag>&nbsp;
                </p>
            </div>
            <p style="border-top: 1px solid #eee; padding: 10px 20px;">
                <small>The following subjects contains objects for this series.</small>
            </p>
            <div v-for="object_idx in ss.object_indices" :key="object_idx" class="object">
                <i class="el-icon-caret-right"/>&nbsp;
                <div v-for="(v, k) in $root.objects[object_idx]._entities" :key="object_idx+'.'+k" style="display: inline-block; font-size: 85%;">
                    <span v-if="v" style="margin-right: 10px;">
                        {{k}}-<b>{{v}}</b>
                    </span>
                </div>
                <div style="float: right">
                    <el-tag size="mini" type="info">filesize: {{$root.objects[object_idx].analysisResults.filesize|prettyBytes}}</el-tag>&nbsp;
                    <el-tag size="mini" type="info">volumes: {{$root.objects[object_idx].analysisResults.NumVolumes}}</el-tag>&nbsp;
                </div>
                <div style="margin-left: 50px">
                    <a :href="$root.getURL($root.objects[object_idx].pngPath)" v-if="$root.objects[object_idx].pngPath">
                        <img width="100%" :src="$root.getURL($root.objects[object_idx].pngPath)"/>
                    </a>
                    <small><b>Files</b></small>
                    <div v-for="(item, idx) in $root.objects[object_idx].items" :key="idx">
                        <pre>{{item.path}}</pre>
                        <pre class="sidecar" v-if="item.sidecar">{{item.sidecar}}</pre>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <br>
    <br>
    <br>
    <el-form>
        <el-form-item class="page-action">
            <el-button @click="back">Back</el-button>
            <el-button type="primary" @click="next" style="float: right;">Next</el-button>
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
            showInfo: {},
            ss: null, //selected series
        }
    },
    watch: {
        '$root.currentPage'(v) {
            if(v.id == 'series') {
                this.$root.objects.forEach(this.$root.mapObject); //for _entities
                this.$root.series.forEach(this.validate);
                this.$root.series.forEach(s=>{
                    Vue.set(s, "_show", false);
                });
            }
        },
    },
    methods: {
        getSomeEntities(type) {
            let entities = this.$root.getEntities(type);
            console.log("getting entities for", type);
            console.dir(entities);

            //we don't want user set sub/ses through series
            //delete entities.sub;
            //delete entities.ses;
            delete entities.subject;
            delete entities.session;

            return entities;
        },

        toggleInfo(entity) {
            this.$set(this.showInfo, entity, !this.showInfo[entity]);
        },

        validate(s) {
            Vue.set(s, 'validationErrors', []);
            let entities = this.$root.getEntities(s.type);

            for(let k in this.getSomeEntities(s.type)) {
                console.log("validating", k)
                if(entities[k] == "required") {
                    if(!s.entities[k]) {
                        s.validationErrors.push("entity: "+k+" is required.");
                    }
                }
            }
        },

        next() {
            let valid = true;
            this.$root.series.forEach(s=>{
                if(s.validationErrors.length > 0) valid = false;
            });
            if(valid) {
                this.$root.changePage("object");
            } else {
                alert('Please correct all issues, or update datatype to exclude');
                return false;
            }
        },

        back() {
            this.$root.changePage("participant");
        },

    },
}
</script>

<style scoped>
.series-list {
    font-size: 90%;
    position: fixed;
    top: 0;
    bottom: 60px;
    left: 210px;
    width: 440px;
    overflow: auto;
}
.series-detail {
    position: fixed;
    top: 0;
    bottom: 60px;
    overflow-y: auto;
    right: 0;
    left: 650px;
    box-shadow: -4px -2px 4px #0001;
    z-index: 1;
}
.el-form-item {
    margin-bottom: 0;
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
.object {
    padding: 0 20px;
    margin-bottom: 20px;
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
