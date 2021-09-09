<template>
<div style="padding: 20px">
    <div class="bids-structure">
        <div v-for="(o_sub, sub) in ezbids._organized" :key="sub" style="font-size: 90%; margin-bottom: 10px">
            <span v-if="sub != ''" class="hierarchy">
                <i class="el-icon-user-solid" style="margin-right: 2px;"/> 
                <!--<small>sub</small> -->{{sub}} 
                &nbsp;
                &nbsp;
                <el-checkbox :value="o_sub.exclude" @change="excludeSubject(sub.toString(), $event)">
                    <small>Exclude this subject</small>
                </el-checkbox>
            </span>
            <div v-for="(o_ses, ses) in o_sub.sess" :key="ses" :class="{'left-border': ses != ''}">
                <span v-if="ses != ''" class="hierarchy">
	   	            <i class="el-icon-time" style="margin-right: 2px;"/>
                    <!--<small v-if="ses">ses</small> -->{{ses}} 
                    <small style="opacity: 0.5;">{{o_ses.AcquisitionDate}}</small>
                    &nbsp;
                    &nbsp;
                    <el-checkbox :value="o_ses.exclude" @change="excludeSession(sub.toString(), ses.toString(), $event)">
                        <small>Exclude this session</small>
                    </el-checkbox>
                </span>
                <div v-for="(section, sectionId) in groupSections(o_ses)" :key="sectionId" style="position: relative;">
                    <div v-if="section.length > 1" style="border-top: 1px dotted #bbb; width: 100%; margin: 9px 0;">
                        <span style="float: right; top: -7px; position: relative; background-color: white; font-size: 70%; color: #999; padding: 0 10px; margin-right: 10px;">section {{sectionId}}</span>
                    </div>
                    <div v-for="o in section" :key="o.idx" class="clickable hierarchy-item" :class="{selected: so === o, exclude: isExcluded(o)}" @click="select(o, o_ses)">
                        <el-tag type="info" size="mini">#{{o.series_idx}}</el-tag>&nbsp;<datatype :type="o._type" :series_idx="o.series_idx" :entities="o.entities"/> 
                        <small v-if="o._type == 'exclude'">&nbsp;({{o._SeriesDescription}})</small>
                        
                        <span v-if="!isExcluded(o)">
                            <!--show validation error as "error"-->
                            <el-badge v-if="o.validationErrors.length > 0" type="danger" 
                                :value="o.validationErrors.length" style="margin-left: 5px;"/>

                            <!-- show "QC errors" as warnings-->
                            <el-badge v-if="o._type != 'exclude' && o.analysisResults && o.analysisResults.errors && o.analysisResults.errors.length > 0" type="warning"
                                :value="o.analysisResults.errors.length" style="margin-left: 5px"/>
                        </span>
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
        <div style="background-color: white; padding: 10px; color: #666;">
            <i class="el-icon-back"/> Please select an object to view/edit in the BIDS Structure list
        </div>
    </div>
    <div class="object" ref="object-detail">
        <div v-if="so && sess">
   
            <el-form label-width="200px">
                <div :class="{'exclude': isExcluded(so)}">
                    <el-form-item label="Series Desc">
                        {{so._SeriesDescription}}
                    </el-form-item>
                    <el-form-item>
                        <el-checkbox v-model="so.exclude" @change="validate(so)">Exclude this object</el-checkbox>
                    </el-form-item>

                    <!--messagess-->
                    <div style="margin-bottom: 5px;" v-if="isExcluded(so)">
                        <el-alert :closable="false" type="info">This object will be excluded from the BIDS output</el-alert>
                    </div>
                    <div style="margin-bottom: 5px;">
                        <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in so.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                     </div>
                    <div style="margin-bottom: 5px;">
                        <el-alert show-icon :closable="false" type="warning" v-for="(error, idx) in so.analysisResults.errors" :key="idx" :title="error"/>
                    </div> 

                    <el-form-item label="Datatype">
                        <el-select v-model="so.type" clearable :placeholder="so._type" size="small" style="width: 100%" @change="update(so)">
                            <el-option value="">(Use Series Default)</el-option>
                            <el-option-group v-for="type in bidsSchema.datatypes" :key="type.label" :label="type.label">
                                <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                    {{type.label}} / {{subtype.label}}
                                </el-option>
                            </el-option-group>
                        </el-select>
                    </el-form-item>

                    <div style="width: 350px;">
                        
                        <el-form-item v-for="(v, entity) in getBIDSEntities(so._type)" :key="entity" 
                            :label="bidsSchema.entities[entity].name+(v=='required'?'- *':'-')">
                            <el-popover width="300" trigger="focus" placement="right-start"
                                :title="bidsSchema.entities[entity].name" 
                                :content="bidsSchema.entities[entity].description">
                                <template #reference>
                                    <el-input v-model="so.entities[entity]" size="small" @blur="update(so)" 
                                        :placeholder="getDefault(so, entity.toString())" style="width: 200px;"/>
                                </template>
                            </el-popover>
                        </el-form-item>
                    </div>

                    <div v-if="so._type.startsWith('fmap/')" class="border-top">
                        <br>
                        <el-form-item label="IntendedFor">
                            <el-select v-model="so.IntendedFor" multiple placeholder="Select Object" style="width: 100%" @change="update(so)">
                                <el-option v-for="o in sess.objects.filter(o=>!isExcluded(o))" :key="o.idx"
                                    :label="intendedForLabel(o)" :value="o.idx">
                                </el-option>
                            </el-select>
                        </el-form-item>
                        <p style="margin-left: 200px;">
                            <small>* IntendedFor information is used to specify which epi image this fieldmap is intended for. This is an important information required by BIDS specification.</small>
                        </p>
                    </div>

                    <div v-for="(item, idx) in so.items" :key="idx" class="border-top">
                        <el-form-item :label="item.name||'noname'">
                            <el-select v-model="item.path" placeholder="Source path" size="small" style="width: 100%">
                                <el-option v-for="(path, idx) in so.paths" :key="idx" :label="path" :value="path"/>
                            </el-select>
                        </el-form-item>
                        <el-form-item v-if="item.sidecar" label="sidecar">
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
                        {{prettyBytes(so.analysisResults.filesize)}}
                    </el-form-item>
                    <div v-if="so.pngPath">
                        <a :href="getURL(so.pngPath)">
                            <img style="width: 100%" :src="getURL(so.pngPath)"/>
                        </a>
                    </div>
                </div>
            </el-form>

            <pre v-if="config.debug">{{so}}</pre>
        </div><!--selected != null-->
        <br>
        <br>
        <br>
    </div><!--object-->

    <!--
    <el-form>
        <el-form-item class="page-action">
            <el-button @click="back">Back</el-button>
            <el-button type="primary" @click="next" style="float: right;" :disabled="!!totalIssues">Next </el-button>
            <span style="padding: 0 10px; float: right;" v-if="totalIssues"><b>{{totalIssues}}</b> issues remaining</span>
        </el-form-item>
    </el-form>
    -->
</div>
</template>

<script lang="ts">

import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue'                                                                                                                                                  
import datatype from './components/datatype.vue' 

import { IObject, Subject, Session, OrganizedSession } from './store'

import { prettyBytes } from './filters'

import { validateEntities, funcQA, fmapQA, setRun, updateErrors, setIntendedFor } from './lib'

interface Section {
    [key: string]: IObject[];
}

export default defineComponent({
    components: {
        datatype,
    },

    data() {
        return {
            so: null as IObject|null, //selected object
            sess: null as OrganizedSession|null, //selected session for IntendedFor handling
        }
    },

    mounted() {
        console.log("mounting object...");
        //assume mapObject/organizeObjects are already done

        //TODO - I really don't like these here.. 
        funcQA(this.ezbids);
        fmapQA(this.ezbids);
        setRun(this.ezbids);
        updateErrors(this.ezbids);
        setIntendedFor(this.ezbids);

        this.$emit("mapObjects");
        this.validateAll();

        console.log("object mount completed");
   },

    computed: {
        ...mapState(['ezbids', 'config', 'bidsSchema']),
        ...mapGetters(['getBIDSEntities', 'getURL', 'findSubject', 'findSession']),

        totalIssues() {
            let count = 0;

            console.log("totalIssues");
            this.ezbids.objects.forEach((o:IObject)=>{
                if(this.isExcluded(o)) return;
                count += o.validationErrors.length;
            });
            return count;
        },
    },
    
    methods: {

        prettyBytes,

        findSubjectFromString(sub: string) {
            return this.ezbids.subjects.find((s:Subject)=>s.subject == sub);
        },

        //subject needs to be an object 
        findSessionFromString(sub: string, ses: string) {
            const subject = this.findSubjectFromString(sub);
            return subject.sessions.find((s:Session)=>s.session == ses);
        },

        excludeSubject(sub: string, b: boolean) {
            const subject = this.findSubjectFromString(sub);
            console.dir(sub, subject);
            subject.exclude = b;

            this.$emit("mapObjects");
            this.validateAll();
        },

        isExcluded(o: IObject) {
            if(o.exclude) return true;
            if(o._type == "exclude") return true;
            return o._exclude; 
        },

        excludeSession(sub: string, ses: string, b: boolean) {
            //const subject = this.findSubjectFromString(sub);
            const session = this.findSessionFromString(sub, ses);
            if(session) session.exclude = b;

            this.$emit("mapObjects");
            this.validateAll();
        },

        groupSections(sess: OrganizedSession) {
            let sections = {} as Section;
            sess.objects.forEach(o=>{
                let sectionId = o.analysisResults.section_ID;
                if(!sections[sectionId]) sections[sectionId] = [];
                sections[sectionId].push(o);
            });
            return sections;
        },

        select(o: IObject, sess: OrganizedSession) {
            this.sess = sess; //for IntendedFor
            this.so = o;
            window.scrollTo(0, 0);
        },

        update(o: IObject|null) {
            if(!o) return;
            this.$emit("updateObject", o);
        },

        isValid(cb: (v?: string)=>void) {
            this.$emit("mapObjects");
            this.validateAll();

            let err = undefined;
            this.ezbids.objects.forEach((o:IObject)=>{
                if(o.validationErrors.length > 0) err = "Please correct all issues.";
            });

            //make sure there is at least 1 object to output
            let one = this.ezbids.objects.find((o:IObject)=>!o._exclude);
            if(!one) {
                err = "All objects are excluded. Please update so that there is at least 1 object to output to BIDS";
            }

            return cb(err);
        },

        getDefault(o: IObject, entity: string) {
            if(entity == "subject") {
                //default subject name only comes from subject
                const subject = this.findSubject(o);
                return subject.subject;
            } else if(entity == "session") {
                //default session name only comes from session
                const subject = this.findSubject(o);
                const session = this.findSession(subject, o.AcquisitionDate);
                return session.session;
            } else {
                //all other entity default should come from series
                const series = this.ezbids.series[o.series_idx];
                return series.entities[entity];
            }
        },

        intendedForLabel(o: IObject) {
            const series = this.ezbids.series[o.series_idx];
            let l = "#"+series.series_idx+" ";
            l += o._type;
            for(let k in o._entities) {
                if(k == "subject" || k == "session") continue;
                if(!o._entities[k]) continue;
                l += " "+k+"-"+o._entities[k];
            }
            return l;
        },

        validate(o: IObject|null) {
            if(!o) return;

            //console.log("validaing", o);

            //make sure all required entities are set
            const series = this.ezbids.series[o.series_idx];
            let entities_requirement = this.getBIDSEntities(o._type);

            o.validationErrors = [];
            if(!this.isExcluded(o)) {
                o.validationErrors = validateEntities(o.entities);
            }

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
                        console.error(err);
                        o.validationErrors.push("Failed to parse sidecar_json. Please check the syntax");
                    }
                }
            });

            //make sure no 2 objects are exactly alike
            for(let o2 of this.ezbids.objects) {
                if(o.idx == o2.idx) continue;
                if(this.isExcluded(o2)) continue;
                if(o._type != o2._type) continue;

                let same = o2;
                for(let k in o._entities) {
                    if(o._entities[k] != o2._entities[k]) {
                        same = null;
                        break;
                    }
                }
                if(same) {
                    const sameseries = this.ezbids.series[same.series_idx];
                    o.validationErrors.push("This object looks exactly like another object with Series #"+sameseries.series_idx+". We can not convert this object to BIDS as they will overwrite each other. Please set entities such as 'run' to make them all unique.");
                   console.log("---same detected");
                   break;
                }
            }
        },

        validateAll() {
            this.ezbids.objects.forEach(this.validate);
        },
    },
});
</script>

<style scoped>
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
</style>

