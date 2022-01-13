<template>
<splitpanes class="objectpage default-theme">
    <pane min-size="20" size="30" class="bids-structure">
        <div v-for="o_sub in ezbids._organized" :key="o_sub.sub" style="font-size: 90%; margin-bottom: 10px">
            <span v-if="o_sub.sub != ''" class="hierarchy">
                <i class="el-icon-user-solid" style="margin-right: 2px;"/>
                <small>sub-</small><b>{{o_sub.sub}}</b>
                &nbsp;
                <el-checkbox :value="o_sub.exclude" @change="excludeSubject(o_sub.sub.toString(), $event)">
                    <small>Exclude this subject</small>
                </el-checkbox>
            </span>
            <div v-for="o_ses in o_sub.sess" :key="o_ses.sess" :class="{'left-border': o_ses.sess != ''}">
                <span v-if="o_ses.sess" class="hierarchy">
                    <i class="el-icon-time" style="margin-right: 2px;"/>
                    <small>ses-</small><b>{{o_ses.sess}}</b>
                    &nbsp;
                    <small style="opacity: 0.5;">{{o_ses.AcquisitionDate}}</small>
                    &nbsp;
                    &nbsp;
                    <el-checkbox :value="o_ses.exclude" @change="excludeSession(o_sub.sub.toString(), o_ses.sess.toString(), $event)">
                        <small>Exclude this session</small>
                    </el-checkbox>
                </span>
                <div v-for="(section, sectionId) in groupSections(o_ses)" :key="sectionId" style="position: relative;">
                    <div v-if="section.length > 1" style="border-top: 1px dotted #bbb; width: 100%; margin: 9px 0;">
                        <span class="section-divider">section {{sectionId}}</span>
                    </div>
                    <div v-for="o in section" :key="o.idx"
                        class="clickable hierarchy-item" :class="{selected: so === o, excluded: isExcluded(o)}"
                        @click="select(o, o_ses)">

                        <el-tag type="info" size="mini" v-if="o.series_idx !== undefined" :title="'Series#'+o.series_idx+' '+o._SeriesDescription">#{{o.series_idx}}</el-tag>&nbsp;
                        <datatype :type="o._type" :series_idx="o.series_idx" :entities="o.entities"/>
                        <small v-if="o._type == 'exclude'">&nbsp;({{o._SeriesDescription}})</small>

                        <span v-if="!isExcluded(o)">
                            <!--show validation error as "error"-->
                            <el-badge v-if="o.validationErrors.length > 0" type="danger"
                                :value="o.validationErrors.length" style="margin-left: 5px;"/>

                            <!--show validation warning as "warning"-->
                            <el-badge v-if="o.validationWarnings.length > 0" type="warning"
                                :value="o.validationWarnings.length" style="margin-left: 5px;"/>

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
    </pane>

    <pane class="object-detail">
        <div v-if="!so" style="padding: 20px">
            <div class="hint">
                <p>Please make sure all subject/session/series mappings are correctly applied to your data.</p>
                <p>By default, entities specified in the <b>Series</b> page will be used as defaults for all objects. On this page you can override those entities.</p>
                <div style="background-color: white; padding: 10px; color: #666;">
                    <i class="el-icon-back"/> Please select an object to view/edit in the BIDS Structure list
                </div>
            </div>
        </div>

        <div v-if="so && sess">
            <el-form label-width="200px">
                <el-form-item>
                    <el-checkbox v-model="so.exclude" @change="update(so)">Exclude this object</el-checkbox>
                </el-form-item>
                <div style="margin-bottom: 5px;" v-if="isExcluded(so)">
                    <el-alert :closable="false" type="info">This object will be excluded from the BIDS output</el-alert>
                </div>
                <el-form-item label="Series Desc" v-if="so.series_idx">
                    {{so._SeriesDescription}}
                </el-form-item>

                <!--messagess-->
                <div style="margin-bottom: 5px;">
                    <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in so.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                 </div>
                <div style="margin-bottom: 5px;">
                    <el-alert show-icon :closable="false" type="warning" v-for="(warning, idx) in so.validationWarnings" :key="idx" :title="warning" style="margin-bottom: 4px;"/>
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
                        <el-popover :width="300" trigger="focus" placement="left-start"
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
                            <el-option v-for="(item, idx) in so.items" :key="idx" :label="item.path" :value="item.path"/>
                        </el-select>
                        <el-button size="small" type="info" v-if="item.path?.endsWith('.nii.gz')" @click="$emit('niivue', item.path)">
                            <font-awesome-icon :icon="['fas', 'eye']"/>
                            NiiVue
                        </el-button>
                    </el-form-item>
                    <el-form-item v-if="item.sidecar" label="sidecar">
                        <el-input type="textarea" rows="10" v-model="item.sidecar_json" @blur="update(so)"/>
                    </el-form-item>
                    <el-form-item v-if="item.headers" label="Nifti Headers (readonly)">
                        <pre class="headers">{{item.headers}}</pre>
                    </el-form-item>
                    <el-form-item v-if="item.eventsBIDS" label="eventsBIDS">
                        <el-table :data="item.eventsBIDS" size="mini" border style="width: 100%">
                            <el-table-column prop="onset" label="onset" />
                            <el-table-column prop="duration" label="duration" />
                            <el-table-column v-if="events.columns.sample" prop="sample" label="sample" />
                            <el-table-column v-if="events.columns.trialType" prop="trial_type" label="trial_type" />
                            <el-table-column v-if="events.columns.responseTime" prop="response_time" label="response_time" />
                            <el-table-column v-if="events.columns.value" prop="value" label="value" />
                            <el-table-column v-if="events.columns.HED" prop="HED" label="HED" />
                        </el-table>
                    </el-form-item>
                    <br>
                </div>

                <div style="margin-top: 5px; padding: 5px; background-color: #f0f0f0;" v-if="so.analysisResults.filesize">
                    <p style="font-size: 90%">
                        Volumes: <b>{{so.analysisResults.NumVolumes}}</b>
                        &nbsp;&nbsp;
                        Orientation: <b>{{so.analysisResults.orientation}}</b>
                        &nbsp;&nbsp;
                        File Size: <b>{{prettyBytes(so.analysisResults.filesize)}}</b>
                    </p>
                    <div v-for="(item, itemIdx) in ezbids.objects[so.idx].items" :key="itemIdx">
                        <div v-if="item.pngPaths">
                            <p v-for="(path, idx) in item.pngPaths" :key="idx">
                                <pre style="margin-bottom: 0">{{path}}</pre>
                                <a :href="getURL(path)">
                                    <img style="width: 100%" :src="getURL(path)"/>
                                </a>
                            </p>
                        </div>
                    </div>
                </div>
            </el-form>

            <pre v-if="config.debug">{{so}}</pre>
        </div><!--selected != null-->
        <br>
        <br>
        <br>
    </pane><!--object-->
</splitpanes>
</template>

<script lang="ts">

import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue'
import datatype from './components/datatype.vue'

import { IObject, Session, OrganizedSession, OrganizedSubject } from './store'
import { prettyBytes } from './filters'
import { validateEntities } from './libUnsafe'

// @ts-ignore
import { Splitpanes, Pane } from 'splitpanes'

import 'splitpanes/dist/splitpanes.css'

interface Section {
    [key: string]: IObject[];
}

export default defineComponent({
    components: {
        datatype,
        Splitpanes, Pane,
    },

    data() {
        return {
            so: null as IObject|null, //selected object
            sess: null as OrganizedSession|null, //selected session for IntendedFor handling
        }
    },

    mounted() {
        this.validateAll();
    },

    computed: {
        ...mapState(['ezbids', 'config', 'bidsSchema', 'events']),
        ...mapGetters(['getBIDSEntities', 'getURL', 'findSubject', 'findSession', 'findSubjectFromString']),

        totalIssues() {
            let count = 0;
            this.ezbids.objects.forEach((o:IObject)=>{
                if(this.isExcluded(o)) return;
                count += o.validationErrors.length;
            });
            return count;
        },
    },

    methods: {

        prettyBytes,

        //subject needs to be an object
        findSessionFromString(sub: string, ses: string) {
            const subject = this.findSubjectFromString(sub);
            return subject.sessions.find((s:Session)=>s.session == ses);
        },

        excludeSubject(sub: string, b: boolean) {
            if(this.findSubjectFromString(sub) !== undefined) {
                const subject = this.findSubjectFromString(sub);
                subject.exclude = b;
            } else {
                const o_subs = this.ezbids._organized.filter((e:OrganizedSubject)=>e.sub == sub)
                o_subs.forEach((o_sub:OrganizedSubject)=>{
                    o_sub.sess.forEach(ses=>{
                        ses.objects[0].exclude = b; //objects is always length of 1, so index first (i.e. only)
                    })
                })
            }

            this.$emit("mapObjects");
            this.validateAll();
        },

        isExcluded(o: IObject) {
            if(o.exclude) return true;
            if(o._type == "exclude") return true;
            return o._exclude;
        },

        excludeSession(sub: string, ses: string, b: boolean) {
            if(this.findSubjectFromString(sub) !== undefined && this.findSessionFromString(sub, ses) !== undefined) {
                const session = this.findSessionFromString(sub, ses);
                if(session) session.exclude = b;
            }else{
                const subject = this.ezbids._organized.filter(e=>e.sub == sub)
                subject.forEach(sub=>{
                    let session = sub.sess.filter(s=>s.sess == ses)
                    session.forEach(ses=>{
                        ses.objects[0].exclude = b; //objects is always length of 1, so index first (i.e. only)
                    })
                })
            }

            this.$emit("mapObjects");
            this.validateAll();
        },

        groupSections(sess: OrganizedSession) {
            let sections = {} as Section;
            sess.objects.forEach(o=>{
                let sectionId = o.analysisResults.section_id;
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

        isValid(cb: (err?: string)=>void) {
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

        getDefault(o: IObject, entity: string) : string {
            if(entity == "subject") {
                //default subject name only comes from subject
                const subject = this.findSubject(o);
                return subject.subject;
            } else if(entity == "session") {
                //default session name only comes from session
                const subject = this.findSubject(o);
                const session = this.findSession(subject, o);
                return session.session;
            } else {
                //all other entity default should come from series
                const series = this.ezbids.series[o.series_idx];
                if(!series) return ""; //no series. no default..
                return series.entities[entity];
            }
        },

        intendedForLabel(o: IObject) {
            const series = this.ezbids.series[o.series_idx];
            if(!series) return "no-series";
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

            let entities_requirement = this.getBIDSEntities(o._type);

            o.validationErrors = [];
            o.validationWarnings = [];

            //update validationWarnings
            if(o.analysisResults.warnings.length) {
                o.validationWarnings = o.analysisResults.warnings
            }

            if(this.isExcluded(o)) return;

            o.validationErrors = validateEntities(o.entities);

            if(o._type.startsWith("func/")) {
                const series = this.ezbids.series[o.series_idx];
                if(entities_requirement['task'] && !o.entities.task && !series?.entities.task) {
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
                        same = undefined;
                        break;
                    }
                }
                if(same) {
                    const sameseries = this.ezbids.series[same.series_idx];
                    let sameidx = undefined;
                    if(sameseries) sameidx = sameseries.series_idx;
                    o.validationErrors.push("This object looks exactly like another object with Series #"+sameidx+
                        ". We can not convert this object to BIDS as they will overwrite each other. "+
                        "Please set entities such as 'run' to make them all unique (across subjects/sessions).");
                    break;
                }
            }

            //for func/events object, update series_idx and ModifiedSeriesNumber to match corresponding func/bold object.
            //Also update validationWarnings if corresponding func/bold has been excluded
            if(o._type == "func/events") {
                /* before
                let funcBoldObjects = this.$store.state.ezbids.objects.filter(o=>o._type == "func/bold" && (o._entities.part == "" || o._entities.part == "mag"))
                funcBoldObjects.forEach(func=>{

                    //TODO - rewrite this. 
                    let funcEntities = Object.fromEntries(Object.entries(func._entities).filter(([_, v]) => v != "")); //remove empty entity labels
                    let objEntities = Object.fromEntries(Object.entries(o._entities).filter(([_, v]) => v != "")); //remove empty entity labels
                    if(deepEqual(funcEntities, objEntities)) {
                        o.ModifiedSeriesNumber = func.ModifiedSeriesNumber
                        o.analysisResults.section_id = func.analysisResults.section_id

                        //o.validationWarnings = [];

                        if(func._exclude === true || func._type == "exclude") {
                            o.validationWarnings.push("The corresponding func/bold #"+func.series_idx+" is currently set to exclude from BIDS conversion. We recommend this func/events also be excluded unless there is a reason for keeping it.")
                        }
                    }
                })
                */

                //find bold object with the same set of entities
                const matchingBold = this.$store.state.ezbids.objects
                    .filter(o=>o._type == "func/bold")
                    .filter(o=>(o._entities.part == "" || o._entities.part == "mag")) //TODO - explain why?
                    .find(func=>{
                        for(let k in o._entities) {
                            if(o._entities[k] != func._entities[k]) return false;
                        }
                        return true
                    });

                if(matchingBold) {
                    o.ModifiedSeriesNumber = matchingBold.ModifiedSeriesNumber;
                    o.analysisResults.section_id = matchingBold.analysisResults.section_id;
                    if(matchingBold._exclude) {
                        o.validationWarnings.push(`The corresponding func/bold #${matchingBold.series_idx} is currently set to exclude from BIDS conversion.
                            We recommend this func/events also be excluded unless there is a reason for keeping it.`)
                    }
                }
            }
        },

        validateAll() {
            this.ezbids.objects.forEach(this.validate);
        },
    },
});
</script>

<style lang="scss" scoped>
.objectpage {
    position: fixed;
    top: 0;
    bottom: 60px;
    left: 200px;
    right: 0;

    width: inherit;
    height: inherit;
}

.splitpanes.default-theme .splitpanes__pane {
    background-color: inherit;
}

.bids-structure {
    padding: 10px;
    font-size: 90%;
    box-sizing: border-box;
    overflow-y: scroll;
}
.object-detail {
    overflow-y: scroll;
}
.item {
    padding-bottom: 5px;
    margin-bottom: 5px;
}
.hierarchy {
    padding: 3px;
    display: block;
    line-height: 150%;
}
.hierarchy-item {
    padding: 2px;
    min-height: 20px;

    &.excluded {
        opacity: 0.5;
    }
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

.section-divider {
    float: right;
    top: -7px;
    position: relative;
    background-color: white;
    color: #999;
    padding: 0 10px;
    margin-right: 10px;
}
</style>

