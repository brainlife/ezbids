<template>
<div v-if="$root.currentPage.id == 'object'">
    <div class="bids-structure">
        <h4 style="padding-top: 20px;">BIDS Structure</h4>
        <div v-for="(o_sub, sub) in $root.subs" :key="sub" style="font-size: 90%;">
            <span v-if="sub != ''" class="hierarchy" style="opacity: 0.8;">
                <i class="el-icon-user-solid"/> 
                <small>sub</small> {{sub}}
                <small>({{o_sub.objects.length}})</small>
            </span>
            <div v-for="(o_ses, ses) in o_sub.sess" :key="ses" :class="{'left-border': ses != ''}" class="left-border">
                <span class="hierarchy" style="opacity: 0.8;"><i class="el-icon-time"/> <small v-if="ses">ses</small> {{ses}} <small>{{o_ses.AcquisitionDate}}</small></span>
                <div v-for="(section, sectionId) in groupSections(o_ses)" :key="sectionId" style="border-top: 1px dotted #bbb; margin-top: 3px; padding-top: 3px; position: relative;">
                    <span style="position: absolute; right: 10px; top: -7px; background-color: white; font-size: 70%; color: #999; padding: 0px 5px;">section {{sectionId}}</span>
                    <div v-for="o in section" :key="o.idx" class="clickable hierarchy-item" :class="{'selected': so === o}" @click="select(o, o_ses)">
                        <!--<el-tag type="info" size="mini"><small>{{o.series_id}}</small></el-tag>-->
                        <el-tag type="info" size="mini">sn {{o.seriesNumber}}</el-tag>
                        &nbsp;
                        <datatype :type="o._type" :series_id="o.series_id" :entities="o.entities"/>
                        <el-badge v-if="o.validationErrors.length > 0" type="danger" 
                            :value="o.validationErrors.length" 
                            style="margin-left: 5px;"/>
                        <el-badge v-if="o._type != 'exclude' && o.analysisResults && o.analysisResults.errors && o.analysisResults.errors.length > 0" type="warning"
                :value="o.analysisResults.errors.length" style="margin-left: 5px"/>
                    </div>
                </div>
            </div>
        </div>
        <br>
        <br>
        <br>
        <br>
    </div>

    <div v-if="!so" style="margin-left: 350px; padding: 20px; background-color: #eee;">
        <p>Please make sure all subject/session/series mappings are correctly applied to your data.</p>
        <p>By default, entities specified in the <b>Series</b> page will be used as defaults for all objects. On this page you can override those entities.</p>
        <el-alert type="secondary" :closable="false">
            <i class="el-icon-back"/> Please select an object to view/edit in the BIDS Structure list
        </el-alert>
    </div>
    <div class="object" ref="object-detail">
        <div v-if="so">
            <div style="margin-bottom: 10px;">
                <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in so.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
             </div>
            <div style="margin-bottom: 10px;">
                <el-alert show-icon :closable="false" type="warning" v-for="(error, idx) in so.analysisResults.errors" :key="idx" :title="error"/>
            </div>    
            <el-form label-width="150px">
                <!--
                <el-form-item label="Include">
                    <el-checkbox v-model="so.include" title="Include this object in the BIDS output" @change="update(so)">Include this object in BIDS output</el-checkbox>
                </el-form-item>
                -->
                <div :class="{'exclude': so._type == 'exclude'}">
                    <el-form-item label="Series Desc.">
                        <el-tag type="info" size="mini">sn {{so.SeriesNumber}}</el-tag>
                        {{$root.findSeries(so).SeriesDescription}}
                        <!--<el-tag type="info" size="mini"><small>series_id {{so.series_id}}</small></el-tag>-->
                    </el-form-item>
                    <el-form-item label="Datatype">
                        <el-select v-model="so.type" clearable :placeholder="so._type" size="small" style="width: 100%" @change="update(so)">
                            <el-option value="">(Use series level datatype)</el-option>
                            <el-option value="exclude">(Exclude from BIDS conversion)</el-option>
                            <el-option-group v-for="type in $root.datatypes" :key="type.label" :label="type.label">
                                <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                    {{type.label}} / {{subtype.label}}
                                </el-option>
                            </el-option-group>
                        </el-select>
                    </el-form-item>

                    <div style="width: 350px;">
                        <el-form-item v-for="(v, entity) in $root.getEntities(so._type)" :key="entity" 
                            :label="entity+'-'+(v=='required'?' *':'')">
                            <el-popover width="300" trigger="focus" placement="right-start"
                                :title="$root.bids_entities[entity].name" 
                                :content="$root.bids_entities[entity].description">
                                <el-input slot="reference" v-model="so.entities[entity]" size="small" @blur="update(so)" :placeholder="getDefault(so, entity)"/>
                            </el-popover>
                        </el-form-item>
                    </div>

                    <div v-if="so._type.startsWith('fmap/')" class="border-top">
                        <br>
                        <el-form-item label="IntendedFor">
                            <el-select v-model="so.IntendedFor" multiple placeholder="Select Object" style="width: 100%" @change="update(so)">

                                <el-option v-for="o in this.sess.objects.filter(o=>o._type != 'exclude')" :key="o.idx"
                                    :label="intendedForLabel(o)" :value="o.idx">
                                </el-option>
                            </el-select>
                        </el-form-item>
                        <p style="margin-left: 150px;">
                            <small>* IntendedFor information is used to specify which epi image this fieldmap is intended for. This is an important information required by BIDS specification.</small>
                        </p>
                    </div>

                    <div v-for="(item, idx) in so.items" :key="idx" class="border-top">
                        <el-form-item :label="item.name||'noname'">
                            <el-select v-model="item.path" placeholder="Source path" size="small" style="width: 100%">
                                <el-option v-for="(path, idx) in so.paths" :key="idx" :label="path" :value="path"/>
                            </el-select>
                        </el-form-item>
                        <el-form-item v-if="item.sidecar" label="Sidecar">
                            <el-input type="textarea" rows="10" v-model="item.sidecar_json" @blur="update(so)"/>
                        </el-form-item>
                        <el-form-item v-if="item.headers" label="Nifti Headers (readonly)">
                            <pre class="headers">{{item.headers}}</pre>
                        </el-form-item>
                        <br>
                    </div>

                </div>
                <div style="margin-top: 5px; padding: 5px; background-color: #f0f0f0;">
                    <el-form-item label="Volumes">
                        {{so.analysisResults.NumVolumes}}
                    </el-form-item>
                    <el-form-item label="File Size">
                        {{so.analysisResults.filesize|prettyBytes}}
                    </el-form-item>
                    <div v-if="so.pngPath">
                        <a :href="$root.getURL(so.pngPath)">
                            <img width="100%" :src="$root.getURL(so.pngPath)"/>
                        </a>
                    </div>
                </div>
            </el-form>
        </div><!--selected != null-->
        <br>
        <br>
        <br>
    </div><!--object-->

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
            so: null, //selected object
            sses: [], //selected session
            config: Vue.config,
        }
    },

    watch: {
        '$root.currentPage'(v) {
            if(v.id == 'object') {
                //I have to map all objects at least once before I can validate any object
                this.$root.objects.forEach(this.$root.mapObject);
                this.$root.objects.forEach(this.validate);
                this.$root.organizeObjects();
            }
        },
    },
    
    computed: {
    },
    
    methods: {
        groupSections(sess) {
            let sections = {};
            sess.objects.forEach(o=>{
                let sectionId = o.analysisResults.section_ID;
                if(!sections[sectionId]) sections[sectionId] = [];
                sections[sectionId].push(o);
            });
            return sections;
        },

        /*
        isSectionTop(o) {
            if(o.idx == 0) return false;
            let prev = this.$root.objects[o.idx-1];
            if(prev.analysisResults.section_ID != o.analysisResults.section_ID) return true;
            return false;
        },
        */

        select(o, sess) {
            this.sess = sess;
            this.so = o;
            window.scrollTo(0, 0);
        },

        update(o) {
            this.$root.mapObject(o);

            //I need to validate the entire list.. so I can detect collision
            this.$root.objects.forEach(this.validate);

            this.$root.organizeObjects();
        },

        getDefault(o, entity) {
            if(entity == "sub") {
                const subject = this.$root.findSubject(o);
                return subject.sub;
            } else if(entity == "ses") {
                const session = this.$root.findSession(o);
                return session.ses;
            } else {
                //rest should come from series
                const series = this.$root.findSeries(o);
                return series.entities[entity];
            }
        },

        intendedForLabel(o) {
            let l = "[sn"+o.SeriesNumber+"] ";
            l += o._type;
            /*
            if(o._entities.task) l += " task-"+o._entities.task;
            if(o._entities.run) l += " run-"+o._entities.run;
            if(o._entities.dir) l += " dir-"+o._entities.dir;
            */
            for(let k in o._entities) {
                if(k == "sub" || k == "ses") continue;
                if(!o._entities[k]) continue;
                l += " "+k+"-"+o._entities[k];
            }
            return l;
        },

        validate(o) {
            Vue.set(o, 'validationErrors', []);

            //if not included, don't need to validate
            //if(!o.include) return;
            if(o._type == "exclude") return;

            //make sure all required entities are set
            let series = this.$root.findSeries(o);
            let entities_requirement = this.$root.getEntities(o._type);

            if(o._type.startsWith("func/")) {
                if(entities_requirement['task'] && !o.entities.task && !series.entities.task) {
                    o.validationErrors.push("Task Name is required for func/bold but not set in series nor overridden.");
                }
            }
            if(o._type.startsWith("fmap/")) {
                if(!o.IntendedFor) o.IntendedFor = []; //TODO can't think of a better place to do this
                if(o.IntendedFor.length == 0) {
                    o.validationErrors.push("fmap should have IntendedFor set to at least 1 object");
                }
            }

            //try parsing items
            o.items.forEach(item=>{
                if(item.sidecar) {
                    try {
                        item.sidecar = JSON.parse(item.sidecar_json);
                    } catch (err) {
                        o.validationErrors.push(err);
                    }
                }
            });

            //make sure no 2 objects are exactly alike
            for(let o2 of this.$root.objects) {
                if(o == o2) continue;
                if(o2._type == "exclude") continue;
                if(o._type != o2._type) continue;
                let same = o2;
                for(let k in o._entities) {
                    if(o._entities[k] != o2._entities[k]) {
                        same = null;
                        break;
                    }
                }
                if(same) {
                    o.validationErrors.push("This object looks exactly like another object with sn:"+same.SeriesNumber);
                    break;
                }
            }
        },

        next() {
            let valid = true;
            this.$root.objects.forEach(s=>{
                if(s.validationErrors.length > 0) valid = false;
            });
            if(valid) {
                this.$root.finalize();
                this.$root.changePage("finalize");
            } else {
                alert('Please correct all issues');
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
.bids-structure {
    position: fixed;
    top: 0;
    bottom: 60px;
    left: 210px;
    width: 340px;
    overflow: auto;
}
.object {
    position: fixed;
    top: 0;
    bottom: 60px;
    overflow-y: auto;
    left: 550px;
    right: 0;
    padding-right: 30px;
    box-shadow: -4px -2px 4px #0001;
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
.el-form-item {
    margin-bottom: 0;
}
.border-top {
    border-top: 1px solid #d9d9d9; 
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
</style>

