<template>
    <splitpanes class="objectpage default-theme">
        <pane min-size="20" size="30" class="bids-structure">
            <div v-for="o_sub in ezbids._organized" :key="o_sub.sub" style="font-size: 90%; margin-bottom: 10px">
                <span v-if="o_sub.sub != ''" class="hierarchy">
                    <i class="el-icon-user-solid" style="margin-right: 2px;"/>
                    <small>sub-</small><b>{{o_sub.sub}}</b>
                    <!-- <el-form-item label="Volume Threshold" prop="Volume Threshold">
                        <el-input v-model="ezbids._organized.setVolumeThreshold"
                            placeholder="Specify a volume threshold for all 4D dataset sequences" size="small" 
                            @change="validateAll()" style="width: 80%">
                        </el-input>
                        <p style="margin-top: 0">
                            <small>* Recommended/Optional: You can specify a volume threshold where any sequences in this series will be set to "exclude" if they don't reach the threshold. Useful in instances where a sequence needed to be restated. If no threshold is specified, ezBIDS will default to the expected number of volumes collected in a 1-min period.</small>
                        </p>
                    </el-form-item> -->
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
                            <datatype :type="o._type" :series_idx="o.series_idx" :entities="o._entities"/>
                            <small v-if="o._type == 'exclude'">&nbsp;({{o._SeriesDescription}})</small>
    
                            <span v-if="!isExcluded(o)">
                                <!--show validation error(s) as "error"-->
                                <el-badge v-if="o.validationErrors.length > 0" type="danger"
                                    :value="o.validationErrors.length" style="margin-left: 5px;"/>
    
                                <!--show validation warning(s) as "warning"-->
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
    
                    <el-form-item label="Datatype/Suffix">
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
                            <small>* IntendedFor information is used to specify which image this fieldmap is intended for. This is recommended information according to the BIDS specification.</small>
                        </p>
                    </div>
                    <div v-if="so._type && !so._type.includes('exclude')" class="border-top">
                        <br>
                        <div v-if="!so._type.includes('events')" class="border-top">
                            <el-form-item label="B0FieldIdentifier">
                                <el-select v-model="so.B0FieldIdentifier" multiple filterable allow-create default-first-option
                                    placeholder="Enter text string" size="small" style="width: 100%" @change="update(so)">
                                </el-select>
                            </el-form-item>
                            <p style="margin-left: 200px;">
                                <small>* Optional/Recommended: If this sequence will be used for fieldmap correction, enter a text string of your choice. A good formatting suggestion is the "datatype_suffix[index]" format (e.g., <b>fmap_epi0</b>, <b>fmap_phasediff1</b>, etc). If another sequence will be used with this one for fieldmap correction, use the exact same text string there as well. Leave field blank if unclear.</small>
                            </p>
                        </div>
                       
                        <br>
                        <div v-if="!so._type.includes('events')" class="border-top">
                            <el-form-item label="B0FieldSource">
                                <el-select v-model="so.B0FieldSource" multiple filterable allow-create default-first-option
                                    placeholder="Enter text string" size="small" style="width: 100%" @change="update(so)">
                                </el-select>
                            </el-form-item>
                            <p style="margin-left: 200px;">
                                <small>* Optional/Recommended: If this sequence will be used for fieldmap correction, enter a text string of your choice. A good formatting suggestion is the "datatype_suffix" format (e.g., fmap_epi, fmap_phasediff). If another sequence will be used with this one for fieldmap correction, use the exact same text string there as well. Leave field blank if unclear.</small>
                            </p>
                        </div>
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
                                <el-table-column v-if="item.eventsBIDS[0].sample" prop="sample" label="sample" />
                                <el-table-column v-if="item.eventsBIDS[0].trial_type" prop="trial_type" label="trial_type" />
                                <el-table-column v-if="item.eventsBIDS[0].response_time" prop="response_time" label="response_time" />
                                <el-table-column v-if="item.eventsBIDS[0].value" prop="value" label="value" />
                                <el-table-column v-if="item.eventsBIDS[0].HED" prop="HED" label="HED" />
                                <el-table-column v-if="item.eventsBIDS[0].stim_file" prop="stim_file" label="stim_file" />
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
    import { deepEqual, setRun, setIntendedFor, align_entities, validateEntities, validate_B0FieldIdentifier_B0FieldSource } from './libUnsafe'
    
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
                            ses.objects.forEach(obj=>{
                                obj.exclude = b;
                            })
                        })
                    })
                }
    
                this.$emit("mapObjects");
                this.validateAll();
            },

            setVolumeThreshold(root:OrganizedSubject) {
                /*
                Determine volume threshold for all func/bold acquisitions in dataset and set
                to exclude if the number of volumes does not meet the volume threshold. Threshold 
                calculated based on the expected number of volumes collected in a 1-minute time frame,
                with the formula (60-sec / tr), where tr == RepetitionTime
                */
                root.sess.forEach(sessGroup=>{
                    sessGroup.objects.forEach(o=>{
                        //update analysisResults.warnings in case user went back to Series and adjusted things
                        if(["func/bold", "func/cbv", "dwi/dwi"].includes(o._type)) {
                            let tr = o.items[0].sidecar.RepetitionTime
                            let numVolumes = o.analysisResults.NumVolumes
                            let numVolumes1min = Math.floor(60 / tr)
                            if(numVolumes <= numVolumes1min) {
                                o.exclude = true
                                o.analysisResults.warnings = [`This 4D sequence contains ${numVolumes} volumes, which is \
                                less than the threshold value of ${numVolumes1min} volumes, calculated by the expected number of \
                                volumes in a 1 min time frame. This acquisition will thus be excluded from BIDS conversion unless \
                                unexcluded. Please modify if incorrect.`]
                            }
                        }
                    });
                });
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
                } else {
                    const o_subs = this.ezbids._organized.filter((e:OrganizedSubject)=>e.sub == sub)
                    o_subs.forEach((o_sub:OrganizedSubject)=>{
                        const o_ses = o_sub.sess.filter(s=>s.sess == ses)
                        o_ses.forEach(ses=>{
                            ses.objects.forEach(obj=>{
                                obj.exclude = b;
                            });
                        });
                    });
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
                    // //all other entity defaults should come from series
                    // const series = this.ezbids.series[o.series_idx];
                    // if(!series) return ""; //no series. no default..
                    // return series.entities[entity];

                    //all other entity defaults should come from objects
                    const objects = this.ezbids.objects[o.idx];
                    if(!objects) return ""; //no object. no default..
                    return objects._entities[entity];
                }
            },
    
            intendedForLabel(o: IObject) {
                const series = this.ezbids.series[o.series_idx];
                if(!series) return "no-series";
                // if(!series && o._type != "func/events") return "no-series";
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

                o.validationErrors = [];
                o.validationWarnings = [];

                setRun(this.ezbids)

                setIntendedFor(this.ezbids)
                
                align_entities(this.ezbids)

                validateEntities("Objects", o)

                validate_B0FieldIdentifier_B0FieldSource(o)
    
                let entities_requirement = this.getBIDSEntities(o._type);
    
                //update validationWarnings
                if(o.analysisResults.warnings?.length) {
                    o.validationWarnings = o.analysisResults.warnings
                }
    
                // if(this.isExcluded(o)) return; // might return to this, but need to check if previously excluded sequences are un-excluded
        
                if(o._type.startsWith("func/")) {
                    const series = this.ezbids.series[o.series_idx];
                    if(entities_requirement['task'] && !o.entities.task && !series?.entities.task) {
                        o.validationErrors.push("task entity label is required for func/bold but not set on Series Mapping page, nor overridden.");
                    }
                }
    
                if(o._type.startsWith("fmap/")) {
                    if(!o.IntendedFor) o.IntendedFor = []; //TODO can't think of a better place to do this
                    if(o.IntendedFor.length == 0) {
                        o.validationWarnings.push("It is recommended that field map (fmap) images have IntendedFor set to at least 1 object. \
                        This is necessary if you plan on using processing BIDS-apps such as fMRIPrep");
                    }
                    //Ensure other fmap series aren't included in the IntendedFor mapping
                    if(o.IntendedFor.length > 0) {
                        o.IntendedFor.forEach(i=>{
                            let series_idx = this.ezbids.objects[i].series_idx
                            if(this.ezbids.objects[i]._type.startsWith("fmap/")) {
                                o.validationErrors.push("The selected series (#"+series_idx+") appears to be a field map (fmap), \
                                which isn't allowed in the IntendedFor mapping. Please remove this series, or, if it \
                                isn't a field map, please correct it.")
                            }
                        })
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

                /* Imaging data implictly has a part-mag (magnitude), though this doesn't need to be explictly stated. 
                Any phase data (part-phase) is linked to the magnitude. If part entity is specified, make sure it's
                properly linked and has same entities (except for part) and exclusion criteria.
                */
                if(o._entities.part && !["", "mag"].includes(o._entities.part)) {
                    let correspondingFuncMag = this.ezbids.objects.filter((object:IObject)=>object._type == o._type &&
                        object._entities.part === "mag" &&
                        parseInt(o.SeriesNumber) === parseInt(object.SeriesNumber) + 1 &&
                        deepEqual(Object.fromEntries(Object.entries(object._entities).filter(([key])=>key !== "part")), Object.fromEntries(Object.entries(o._entities).filter(([key])=>key !== "part"))))
                    
                    if(correspondingFuncMag) { // should be no more than one
                        correspondingFuncMag.forEach((boldMag:IObject)=>{
                            // o.analysisResults.section_id = boldObj.analysisResults.section_id
                            for(let k in boldMag._entities) {
                                if(boldMag._entities[k] !== "" && k !== "part") {
                                    o._entities[k] = boldMag._entities[k]
                                } else if(boldMag._entities[k] === "" && k !== "part") {
                                    o._entities[k] = ""
                                }
                                o.entities[k] = o._entities[k]
                            }
                            if(boldMag._exclude === true) {
                                o.exclude = true
                                o._exclude = true
                                o.validationWarnings = [`The corresponding magnitude (part-mag) #${boldMag.series_idx} is currently set to exclude from BIDS conversion. \
                                    Since this phase (part-phase) sequence is linked, it will also be excluded from conversion unless the corresponding
                                    magnitude (part-mag) is unexcluded. If incorrect, please modify corresponding magnitude (part-mag) (#${boldMag.series_idx}).`]
                            }
                            if(boldMag._exclude === false) {
                                o.exclude = false
                                o._exclude = false
                                o.validationWarnings = []
                            }
                        })
                    }
                }

                // func/sbref are implicitly linked to a func/bold; make sure these have same entities and exclusion criteria
                if(o._type == "func/sbref") {
                    let correspondingFuncBold = this.ezbids.objects.filter((object:IObject)=>object._type === "func/bold" &&
                        parseInt(object.ModifiedSeriesNumber) === parseInt(o.ModifiedSeriesNumber) + 1) //func/sbref [should] always come right before their func/bold
                    if(correspondingFuncBold) { // should be no more than one
                        correspondingFuncBold.forEach((boldObj:IObject)=>{
                            o.analysisResults.section_id = boldObj.analysisResults.section_id
                            for(let k in boldObj._entities) {
                                if(boldObj._entities[k] !== "" && k !== "echo") {
                                    if(k === "part" && boldObj._entities[k] === "phase") {
                                        //pass
                                    } else {
                                        o._entities[k] = boldObj._entities[k]
                                    }
                                } else if (boldObj._entities[k] === "") {
                                    o._entities[k] = ""
                                }
                                o.entities[k] = o._entities[k]
                            }
                            if(boldObj._exclude === true || correspondingFuncBold._type === "exclude") {
                                o.exclude = true
                                o._exclude = true
                                o.validationWarnings = [`The corresponding func/bold #${boldObj.series_idx} is currently set to exclude from BIDS conversion. \
                                    Since this func/sbref is linked, it will also be excluded from conversion unless the corresponding
                                    func/bold is unexcluded. If incorrect, please modify corresponding func/bold (#${boldObj.series_idx}).`]
                            }
                            if(boldObj._exclude === false) {
                                o.exclude = false
                                o._exclude = false
                                o.validationWarnings = []
                            }
                        })
                    }
                }
    
                //func/events are implicitly linked to a func/bold; make sure these have same entities and exclusion criteria
                if(o._type == "func/events") {
                    let correspondingFuncBold:any = undefined

                    if(o.ModifiedSeriesNumber !== "00" && o.analysisResults.section_id !== 0) { // placeholder for when match with corresponding func/bold isn't yet known
                        correspondingFuncBold = this.ezbids.objects.filter((object:IObject)=>object._type == "func/bold" &&
                            object._entities.subject == o._entities.subject &&
                            object._entities.session == o._entities.session &&
                            object._entities.task == o._entities.task &&
                            object.ModifiedSeriesNumber == o.ModifiedSeriesNumber &&
                            object.analysisResults.section_id == o.analysisResults.section_id
                        )
                    } else {
                        correspondingFuncBold = this.ezbids.objects.filter((object:IObject)=>object._type == "func/bold" &&
                            object._entities.subject == o._entities.subject &&
                            object._entities.session == o._entities.session &&
                            object._entities.task == o._entities.task &&
                            object._entities.run == o._entities.run
                        )
                    }

                    if(correspondingFuncBold) { // should be no more than one instance
                        correspondingFuncBold.forEach((boldObj:IObject)=>{
                            o.ModifiedSeriesNumber = boldObj.ModifiedSeriesNumber
                            o.analysisResults.section_id = boldObj.analysisResults.section_id
                            for(let k in boldObj._entities) {
                                if(boldObj._entities[k] !== "" && k !== "echo") {
                                    if(k === "part" && boldObj._entities[k] === "phase") {
                                        //pass
                                    } else {
                                        o._entities[k] = boldObj._entities[k]
                                    }
                                } else if (boldObj._entities[k] === "") {
                                    o._entities[k] = ""
                                }
                                o.entities[k] = o._entities[k]
                            }
                            if(boldObj._exclude === true || correspondingFuncBold._type === "exclude") {
                                o.exclude = true
                                o._exclude = true
                                o._entities.run = ""
                                o.entities.run = ""
                                o.validationWarnings = [`The corresponding func/bold #${boldObj.series_idx} is currently set to exclude from BIDS conversion. \
                                    Since this func/events is linked, it will also be excluded from conversion unless the corresponding
                                    func/bold is unexcluded. If incorrect, please modify corresponding func/bold (#${boldObj.series_idx}).`]
                            }
                            if(boldObj._exclude === false) {
                                o.exclude = false
                                o._exclude = false
                                o.validationWarnings = []
                            }
                        })
                    }
                }
                
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
            },
    
            validateAll() {
                this.ezbids.objects.forEach(this.validate);
                // this.ezbids.objects.forEach(this.validate); // not ideal, but need to re-validate when run entities are being updated
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
    