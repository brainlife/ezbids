<template>
<splitpanes class="seriespage default-theme">
    <pane min-size="20" size="30" class="series-list">
        <div v-for="(s, series_idx) in ezbids.series" :key="series_idx"
            class="series-item" :class="{selected: ss === s, excluded: s.type == 'exclude'}"
            @click="ss = s">
            <el-tag type="info" size="mini" title="Series index">#{{series_idx}}</el-tag>
            &nbsp;
            <datatype :type="s.type" :series_idx="series_idx" :entities="s.entities"/>
            <small style="opacity: 0.7;">({{s.SeriesDescription}})</small>
            &nbsp;
            <el-tag type="info" effect="plain" size="mini" title="Number of objects">{{getObjectsFromSeries(s).length}} objs</el-tag>
            &nbsp;
            <el-badge v-if="s.validationErrors.length > 0" type="danger" :value="s.validationErrors.length" style="margin-left: 5px;">
                <small/>
            </el-badge>
            <el-badge v-if="s.validationWarnings.length > 0" type="warning" :value="s.validationWarnings.length" style="margin-left: 5px;">
                <small/>
            </el-badge>
        </div>
        <pre v-if="config.debug">{{ezbids.series}}</pre>
    </pane>

    <pane class="series-detail">
        <div v-if="!ss" style="padding: 20px;">
            <div class="hint">
                <p>Please update how you'd like to map each dicom SeriesDescription to BIDS datatype, suffix, entities.</p>
                <p>The information you specify here will be applied to all subjects that uses matching SeriesDescription. You can also override this information later for each subject.</p>
                <div style="background-color: white; padding: 10px; color: #666;">
                    <i class="el-icon-back"/> &lt; Please select a series to view/edit
                </div>
            </div>
        </div>
        <div v-if="ss">
            <h5>BIDS Datatype, Suffix, Entities</h5>
            {{ ss.series_idx }}
            <!-- <pre>{{ getFieldsMetaData(ss.type) }}</pre> -->
            <el-form label-width="150px">
                <el-alert v-if="ss.message" :title="ss.message" type="warning" style="margin-bottom: 4px;"/>
                <div style="margin-bottom: 10px;">
                    <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in ss.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                    <el-alert show-icon :closable="false" type="warning" v-for="(warn, idx) in ss.validationWarnings" :key="idx" :title="warn" style="margin-bottom: 4px;"/>
                </div>

                <el-form-item label="Datatype/Suffix">
                    <el-select v-model="ss.type" required filterable
                        placeholder="(exclude)" size="small" @change="validateAll()" style="width: 80%">
                        <el-option value="exclude">(Exclude from BIDS conversion)</el-option>
                        <el-option-group v-for="type in bidsSchema.datatypes" :key="type.label" :label="type.label">
                            <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                {{type.label}} / {{subtype.label}}
                            </el-option>
                        </el-option-group>
                    </el-select>
                    <br>
                </el-form-item>  

                <div v-if="ss.type">
                    <el-form-item v-for="(v, entity) in getSomeEntities(ss.type)" :key="entity"
                        :label="entity.toString()+'-'+(v=='required'?' *':'')" style="width: 350px">
                        <el-popover v-if="bidsSchema.entities[entity]" :width="350"
                            :title="bidsSchema.entities[entity].name"
                            :content="bidsSchema.entities[entity].description">
                            <template #reference>
                                <el-input v-model="ss.entities[entity]" size="small" :required="v == 'required'" @change="validateAll()"/>
                            </template>
                        </el-popover>
                    </el-form-item>
                    <!-- <p style="border-top: 1px solid #eee; padding: 10px 20px;">
                        <small>The following metadata fields are required, recommoneded, or optional for this datatype/suffix. Please enter missing required information.</small>
                        <el-form-item v-for="(v, md) in getSomeMetadata(ss.type)" :key="md"
                            :label="md.toString()+'-'+(v=='required'?' *':'')" label-width="350" style="width: 350px">
                            <el-popover v-if="bidsSchema.metadata[md]" :width="350"
                                :title="bidsSchema.metadata[md].name"
                                :content="bidsSchema.metadata[md].description">
                                <template #reference>
                                    <el-input v-model="ss.md" size="small" :required="v == 'required'" @change="validateAll()"/>
                                </template>
                            </el-popover>
                        </el-form-item>
                        <p style="border-top: 1px solid #eee; padding: 10px 20px;"></p>
                    </p> -->
                </div>

                <div v-if="ss.type && ss.type.startsWith('fmap/')">
                    <el-form-item label="IntendedFor">
                        <el-select v-model="ss.IntendedFor" required multiple filterable
                            placeholder="Please select Series" size="small"
                            @change="validateAll()" style="width: 80%">
                            <el-option v-for="(series, idx) in ezbids.series/*.filter(s=>s.type != 'exclude')*/" :key="idx"
                                :label="'(#'+idx.toString()+') '+series.type" :value="idx">
                                (#{{idx.toString()}}) {{series.type}}
                            </el-option>
                        </el-select>
                        <p style="margin-top: 0">
                            <small>* Optional/Recommended: select Series that this field map should be applied to. Helpful is planning on using BIDS-apps for processing (e.g., fMRIPrep).</small>
                        </p>
                    </el-form-item>
                </div>
                
                <div v-if="ss.type && !ss.type.includes('exclude')">
                    <el-form-item label="B0FieldIdentifier" prop="B0FieldIdentifier">
                        <el-select v-model="ss.B0FieldIdentifier" multiple filterable allow-create default-first-option
                            placeholder="Enter text string" size="small" 
                            @change="validateAll()" style="width: 80%">
                        </el-select>
                        <p style="margin-top: 0">
                            <small>* Optional/Recommended: If this sequence will be used for fieldmap/distortion correction, enter a text string of your choice. A good formatting suggestion is the "datatype_suffix[index]" format (e.g., <b>fmap_epi0</b>, <b>fmap_phasediff1</b>, etc). If another sequence will be used with this one for fieldmap/distortion correction, use the exact same text string there as well. Leave field blank if unclear.</small>
                        </p>
                    </el-form-item>
                    <el-form-item label="B0FieldSource" prop="B0FieldSource">
                        <el-select v-model="ss.B0FieldSource" multiple filterable allow-create default-first-option
                            placeholder="Enter text string" size="small" 
                            @change="validateAll()" style="width: 80%">
                        </el-select>
                        <p style="margin-top: 0">
                            <small>* Optional/Recommended: If fieldmap/distortion correction will be applied to this image, enter the identical text string from the B0FieldIdentifier field of the sequence(s) used to create the fieldmap/distortion estimation. Leave field blank if unclear.</small>
                        </p>
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
            <div v-if="ss.type=='perf/asl' || ss.type == 'pet/pet'">
                <el-button @click="initForm()">Edit Modality</el-button>
                <el-dialog v-model="showDialog" title="Edit Modalities" >
                    <el-form ref="form" :model="formData" label-position="top" label-width="200px" :inline="true" :rules="rules"> 
                        <div>
                            <el-row>
                                <el-col :span="8">
                                    <el-form-item class="editModalityInputItem" v-for="(item, index) in fields.required" :key="'required' + index" :label="`${item.details.display_name}`" :prop="item.field">
                                        <el-input :name="item.field" v-model="formData[item.field]" @input="this.$refs.form.validate()" ></el-input>
                                    </el-form-item>
                                </el-col>
                                <el-col :span="8">
                                    <el-form-item class="editModalityInputItem" v-for="(item, index) in fields.recommended" :key="'recommended' + index" :label="`${item.details.display_name} (recommended)`" :prop="item.field">
                                        <el-input :name="item.field" v-model="formData[item.field]" @input="this.$refs.form.validate()"></el-input>
                                    </el-form-item>
                                </el-col>

                                <el-col :span="8">
                                    <el-form-item class="editModalityInputItem" v-for="(item, index) in fields.optional" :key="'optional' + index" :label="`${item.details.display_name} (optional)`" :prop="item.field">
                                        <el-input :name="item.field"  v-model="formData[item.field]" @input="this.$refs.form.validate()"></el-input>
                                    </el-form-item>
                                    <el-form-item class="editModalityInputItem" v-for="(item, index) in fields.conditional" :key="'conditional' + index" :label="conditionalLabel(item)" :prop="item.field">
                                        <el-input :name="item.field" v-model="formData[item.field]" @input="this.$refs.form.validate()"></el-input>
                                    </el-form-item>
                                </el-col>
                        </el-row>
                        </div>
                    </el-form>
                    <br>
                    {{ formData  }}
                    <span slot="footer" class="dialog-footer">
                        <el-button @click="showDialog = false">Cancel</el-button>
                        <el-button type="primary" @click="submitForm">Submit</el-button>
                    </span>
                </el-dialog>
            </div>


            <p style="border-top: 1px solid #eee; padding: 10px 20px;">
                <small>The following objects belongs to this series.</small>
            </p>
            <div v-for="object in getObjectsFromSeries(ss)" :key="object.idx" class="object">
                <i class="el-icon-caret-right"/>&nbsp;
                <div v-for="(v, k) in object._entities" :key="object.idx+'.'+k.toString()" style="display: inline-block; font-size: 85%;">
                    <span v-if="v" style="margin-right: 10px;">
                        {{k}}-<b>{{v}}</b>
                    </span>
                </div>
                <div style="float: right">
                    <el-tag size="mini" type="info">volumes: {{ezbids.objects[object.idx].analysisResults.NumVolumes}}</el-tag>&nbsp;
                    <el-tag size="mini" type="info">filesize: {{prettyBytes(ezbids.objects[object.idx].analysisResults.filesize)}}</el-tag>&nbsp;
                    <el-tag size="mini" type="info">orientation: {{ezbids.objects[object.idx].analysisResults.orientation}}</el-tag>&nbsp;
                    <el-tag size="mini" type="info">direction: {{ezbids.objects[object.idx].PED}}</el-tag>&nbsp;

                </div>
                <div style="margin-left: 25px">
                    <div v-for="(item, itemIdx) in ezbids.objects[object.idx].items" :key="itemIdx">
                        <div v-if="item.pngPaths">
                            <p v-for="(path, idx) in item.pngPaths" :key="idx">
                                <pre style="margin-bottom: 0">{{path}}</pre>
                                <a :href="getURL(path)">
                                    <img style="width: 100%" :src="getURL(path)"/>
                                </a>
                            </p>
                            <el-button type="info" @click="$emit('niivue', item.path)" size="small">
                                <font-awesome-icon :icon="['fas', 'eye']"/>
                                NiiVue
                            </el-button>
                        </div>
                    </div>

                    <small><b>Files</b></small>
                    <div v-for="(item, idx) in ezbids.objects[object.idx].items" :key="idx">
                        <pre>{{item.path}}</pre>
                        <showfile v-if="['json', 'bval', 'bvec'].includes(item.path.split('.').pop())" :path="item.path"/>
                    </div>
                </div>
            </div>
        </div>
    </pane>
</splitpanes>
</template>

<script lang="ts">

import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue'

import showfile from './components/showfile.vue'
import datatype from './components/datatype.vue'

import { prettyBytes } from './filters'

import { Series, IObject } from './store'

import { validate_Entities_B0FieldIdentifier_B0FieldSource } from './libUnsafe'
import aslYaml from "../src/assets/schema/rules/sidecars/asl.yaml";
import petYaml from '../src/assets/schema/rules/sidecars/pet.yaml';
import metadata_types from '../src/assets/schema/rules/sidecars/metadata_types.yaml';

// @ts-ignore
import { Splitpanes, Pane } from 'splitpanes'

import 'splitpanes/dist/splitpanes.css'
import { inputEmits } from 'element-plus'

export default defineComponent({

    components: {
        datatype,
        showfile,
        Splitpanes, Pane,
    },

    data() {
        return {
            showInfo: {} as any,
            ss: null as Series|null, //selected series
            petYaml: petYaml,
            aslYaml: aslYaml,
            fields: {},
            showDialog: false,
            rules: {},
            formData: {
            },
        }
    },

    computed: {
        ...mapState(['ezbids', 'bidsSchema', 'config']),
        ...mapGetters(['getBIDSEntities', 'getBIDSMetadata', 'getURL', 'getMetaDataRule']), //doesn't work with ts?
    },

    mounted() {
        console.log("series mount completed");
        this.validateAll();
    },

    methods: {

        prettyBytes,

        getObjectsFromSeries(series: Series): IObject[] {
            const idx = this.ezbids.series.indexOf(series);
            return (this.ezbids.objects as IObject[]).filter(object=>object.series_idx == idx);
        },

        getSomeEntities(type: string): any {
            const entities = Object.assign({}, this.getBIDSEntities(type));
            delete entities.subject;
            delete entities.session;
            return entities;
        },

        // getSomeMetadata(type: string): any {
        //     const metadata = Object.assign({}, this.getBIDSMetadata(type));
        //     return metadata;
        // },

        toggleInfo(entity: string) {
            this.showInfo[entity] = !this.showInfo[entity];
        },

        validate(s: Series|null) {
            if(!s) return;

            s.validationErrors = [];
            s.validationWarnings = [];

            if(s.type != "exclude") {
                s.validationErrors = validate_Entities_B0FieldIdentifier_B0FieldSource(s.entities, s.B0FieldIdentifier, s.B0FieldSource);
            }

            //let user know if multiple series have same datatype and entity labels
            if(s.type != "exclude") {
                for(let s2 of this.ezbids.series) {
                    if(s == s2) continue;
                    if(s.type != s2.type) continue;
                    if(s2.type == "exclude") continue;

                    let same = s2;
                    for(let e in s.entities) {
                        if(s.entities[e] != s2.entities[e]) {
                            same = undefined;
                            break;
                        }
                    }
                    if(same) {
                        const sameseries = s2.series_idx;
                        s.validationWarnings.push("This series contains the same datatype, suffix and entity labels as series #"+sameseries+". We advise setting different entity label(s) to differentiate between the series.");
                        break;
                    }
                }
            }

            let entities = this.getBIDSEntities(s.type);
            for(let k in this.getSomeEntities(s.type)) {
                if(entities[k] == "required") {
                    if(!s.entities[k]) {
                        s.validationErrors.push("entity: "+k+" is required.");
                    }
                }
            }

            // let metadata = this.getBIDSMetadata(s.type);
            // for(const [key, value] of Object.entries(metadata)) {
            //     if(value == "required") {
            //         s.validationWarnings.push("json sidecar metadata: "+key+" is required.");

            //     }
            // }

            /* Ensure direction (dir) entity labels are capitalized (e.g. AP, not ap) and match ezBIDS internal PED checks.
            Can occur when user adds this themselves.
            */
            if(s.entities.direction != "") {
                if(s.entities.direction !== s.entities.direction.toUpperCase()) {
                    s.validationErrors.push("Please ensure that the direction entity label is fully capitalized")
                }
                if(s.entities.direction.toUpperCase() !== s.PED) {
                    s.validationWarnings.push(`ezBIDS detects that the direction shoula be ${s.PED}, not ${s.entities.direction}. Please be sure before continuing`)
                }
            }

            if(s.type.startsWith("fmap/")) {
                if(!s.IntendedFor) s.IntendedFor = [];
                if(s.IntendedFor.length == 0) {
                    s.validationWarnings.push("It is recommended that field map (fmap) images have IntendedFor set to at least 1 series ID. This is necessary if you plan on using processing BIDS-apps such as fMRIPrep");
                }
                //Ensure other fmap series aren't included in the IntendedFor mapping
                if(s.IntendedFor.length > 0) {
                    s.IntendedFor.forEach(i=>{
                        if(this.ezbids.series[i].type.startsWith("fmap/")) {
                            s.validationErrors.push("The selected series (#"+i+") appears to be a field map (fmap), which isn't allowed in the IntendedFor mapping. Please remove this series, or, if it isn't a field map, please correct it.")
                        }
                    })
                }
            }
        },

        isValid(cb: (v?: string)=>void) {
            this.validateAll();

            let err = undefined;
            this.ezbids.series.forEach((s: Series)=>{
                if(s.validationErrors.length > 0) err = "Please correct all issues";
            });
            return cb(err);
        },

        validateAll() {
            this.ezbids.series.forEach(this.validate);
        },
        initForm() {
            this.fields = this.getFieldsMetaData(this.ss.type);
            this.rules = this.generateValidationRules(this.fields);

            this.fields.required.forEach((item: any) => {
                this.formData[item.field] = item.details.type;
            });
            this.fields.recommended.forEach((item: any) => {
                this.formData[item.field] = item.details.type;
            });
            this.fields.optional.forEach((item: any) => {
                this.formData[item.field] = item.details.type;
            });
            this.fields.conditional.forEach((item: any) => {
                this.formData[item.field] = item.details.type;
            });
            //match the pos of type and series.idx inside the ezbids.objects[]

            //Task 1 , load the relevant file 

            console.log("initForm", this.ezbids.objects);

            this.ezbids.objects.forEach((file: any, idx: any) => {
                if (file.series_idx == this.ss.series_idx) {
                    //find the item in items with .json
                    file.items.forEach((item: any, idx: any) => {
                        if (item.name.includes("json") && item.sidecar_json) {
                            //load the json through sidecar_json
                            const json = JSON.parse(item.sidecar_json);
                            for (const [key, value] of Object.entries(json)) {
                                if(this.formData.hasOwnProperty(key)) this.formData[key] = value;
                            }
                        }
                    });
                }
            });

            //Task 3, make the validation real time 
            console.log("initForm", this.ezbids.object);
            this.showDialog = true;
            console.log("this.ref",this.$refs)
            this.$nextTick(() => {
                console.log("this.ref",this.$refs)
                this.$refs.form.validate();
            });
        },
        getFieldsMetaData(type: string) {
            console.log("getFieldsMetaData",type);
            let fileObject = {};
            if(type == 'pet/pet') fileObject = petYaml;
            if(type == 'perf/asl') fileObject = aslYaml;
            else return {};
            let result = {
                required: [],
                recommended: [],
                optional: [],
                conditional: []
            };

            for (const [section, data] of Object.entries(fileObject)) {
                const fields = data.fields || {};
                // fields with level 'required' or 'recommended' are included in the list
                for (const [field, metadata] of Object.entries(fields)) {
                    
                    // get the metadata from the metadata_types.yaml
                    const details = metadata_types[field] || {};
                    details.type = this.setTypeforField(details);

                    let fieldData = {field,details};

                    if (metadata === 'required') result.required.push(fieldData);

                    if (metadata === 'recommended') result.recommended.push(fieldData);

                    if(metadata === 'optional') result.optional.push(fieldData);

                    //fields with level
                    const level = metadata.level || '';
                    if (level === 'required') {
                        result.required.push(fieldData);
                    } else if (level === 'recommended') {
                        result.recommended.push(fieldData);
                    } else if (level === 'optional') {
                        result.optional.push(fieldData);  // Include optional fields in the recommended list
                    }

                    const levelAddendum = metadata.level_addendum || '';
                    if (levelAddendum.includes('required if') || levelAddendum.includes('required when')) {
                        result.conditional.push({...fieldData,level: 'required', condition: levelAddendum});
                    } else if (levelAddendum.includes('recommended if') || levelAddendum.includes('recommended when')) {
                        result.conditional.push({...fieldData, level: 'recommended', condition: levelAddendum});
                    }
                }
            }
        
            //remove required fields which are in conditional 

            result.required = result.required.filter((item: any) => {
                return !result.conditional.some((conditionalItem: any) => {
                    return conditionalItem.field === item.field;
                });
            });

            //remove recommended fields which are in conditional

            result.recommended = result.recommended.filter((item: any) => {
                return !result.conditional.some((conditionalItem: any) => {
                    return conditionalItem.field === item.field;
                });
            });

            // remove optional fields which are in conditional

            result.optional = result.optional.filter((item: any) => {
                return !result.conditional.some((conditionalItem: any) => {
                    return conditionalItem.field === item.field;
                });
            });


            return result;
        },
        submitForm() {
            // Here, you can do whatever you want with the form data
            // this.$refs.form.validate((valid) => {
            //     console.log("Form validation triggered. Result:", valid);
            //     if (valid) {
            //         // If the form is valid
            //         console.log(this.formData);
            //         this.showDialog = false;
            //     } else {
            //         // If the form has validation errors
            //         console.error("Validation failed.");
            //         // Optionally: Notify the user about validation errors
            //         // You can use Element UI's Notification or MessageBox to notify the user
            //         this.$notify.error({
            //             title: 'Error',
            //             message: 'There are validation errors in the form.'
            //         });

            //         alert('There are validation errors in the form.');
            //         return false; // Stop the form submission
            //     }
            // });

            //reupdate the rules based on if conditional fields which were dependent on other field have been updated and meet the requirement and then check the validation`
            this.$refs.form.validate((valid) => {
                if (valid) {
                alert("Valid");
                } else {
                alert("Not Valid");
                }
            });
        },
        conditionalLabel(item: any) {
            if(item.level === 'required') return `${item.details.display_name} (${item.condition})`;
            if(item.level === 'recommended') return `${item.details.display_name} (${item.condition})`;
            return `${item.field} (${item.condition})`;
        },
        generateValidationRules(fieldsMetadata) {
            const rules = {};
            // For required fields
            fieldsMetadata.required.forEach(item => {
                rules[item.field] = [
                    { required: true, message: `${item.field} is required`, trigger: 'change' } //change checks in real time
                ];
            });
            console.log("fieldsMetadata", fieldsMetadata)
             // For conditional fields
            fieldsMetadata.conditional.forEach(item => {
                if (item.level === 'required') {
                    rules[item.field] = [{
                        validator: (rule, value, callback) => {
                            // Condition: "`fieldName` is true|false"
                            // let matches = item.condition.match(/`(\w+)` is (true|false)/);
                            let matches = item.condition.match(/`(\w+)`\s+is\s+`(true|false)`/i);
                            if (matches) {
                                const fieldName = matches[1];
                                const expectedValue = matches[2] === 'true';                            
                                if (this.formData.hasOwnProperty(fieldName) && 
                                    Boolean(this.formData[fieldName]) == Boolean(expectedValue) && 
                                    (value == null || value === '')) {
                                    console.log("t/F",`Validation failed for field ${item.field}.`);
                                    callback(new Error('This field is required based on the condition'));
                                    return;
                                }

                            }
                            // Condition: "`fieldName` is defined as `value`"
                            // matches = item.condition.match(/`(\w+)` is defined as `(\w+)`/);
                            matches = item.condition.match(/`(\w+)`\s+is\s+defined\s+as\s+`(\w+)`/i);
                            if (matches) {
                                const fieldName = matches[1];
                                const expectedValue = matches[2];
                                // console.log("defined",`Field to check: ${fieldName}, Expected: ${expectedValue}, Current: ${this.formData[fieldName]}`);
                                if (this.formData.hasOwnProperty(fieldName) && String(this.formData[fieldName]) === expectedValue && !value) {
                                    console.log(`Validation failed for field ${item.field}.`);
                                    callback(new Error('This field is required based on the condition'));
                                    return;
                                }
                            }
                            callback();
                        },
                        trigger: 'change'
                    }];
                }
            });

            // No special rules for recommended as they are optional, but you can add if needed
            console.log('Generated Rules:', rules);
            return rules;

        },
        setTypeforField(details) {
            console.log("details", details);
            if(details.type != null) return this.parseType(details.type);
            if(details.anyOf.length > 0) {
                if(details.anyOf[0].type) return this.parseType(details.anyOf[0].type);
                else {
                    details.anyOf.forEach((item: any) => {
                        if(item.type) return this.parseType(item.type);
                    });
                    return "";
                }
            }
        },
        parseType(type) {
            if(type == 'string') return "";
            if(type == 'number') return 0;
            if(type == 'boolean') return false;
            if(type == 'array') return [];
            if(type == 'object') return {};
            return "";
        }
},
})

</script>

<style lang="scss" scoped>
.seriespage {
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

.series-list {
    padding: 10px;
    font-size: 90%;
    box-sizing: border-box;
    overflow-y: scroll;
}
.series-detail {
    overflow-y: scroll;
}
.el-form-item {
    margin-bottom: 0;
}
.series-item {
    transition: background-color 0.3s;
    padding: 2px;

    &.excluded {
        opacity: 0.5;
    }
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
h5 {
    padding: 0 20px;
}
.condition-text {
    color: #999;
    font-size: 0.8rem;
}

.dialog-footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
}
.editModalityInputItem {
    margin-top: 10px;
}
</style>
