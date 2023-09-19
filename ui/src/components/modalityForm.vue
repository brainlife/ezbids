<template>
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
                        <el-form-item class="editModalityInputItem" v-for="(item, index) in fields.conditional" :key="'conditional' + index" :label="`${item.details.display_name}`" :prop="item.field">
                            <el-input :name="item.field" v-model="formData[item.field]" @input="this.$refs.form.validate()"></el-input>
                        </el-form-item>
                    </el-col>
            </el-row>
            </div>
        </el-form>
        <br>
        <span slot="footer" class="dialog-footer">
            <el-button @click="showDialog = false">Cancel</el-button>
            <el-button type="primary" @click="submitForm">Submit</el-button>
        </span>
    </el-dialog>
</template>

<script lang="ts">
import aslYaml from "../../src/assets/schema/rules/sidecars/asl.yaml";
import petYaml from '../../src/assets/schema/rules/sidecars/pet.yaml';

import metadata_types from '../../src/assets/schema/rules/sidecars/metadata_types.yaml';
import { ElMessageBox, ElMessage } from 'element-plus'
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ModalityForm',
  props: [
    'ss', 'ezbids'
    ],
  mounted() {
  },
  data () {
    return {
        formData: {},
        fields: {
            required: [],
            recommended: [],
            optional: [],
            conditional: []
        },
        rules: {},
      showDialog: false
    }
  },
  methods: {
    submitForm() {
        this.$refs.form.validate((valid: any) => {
            if (valid) {
                this.ezbids.objects.forEach((file: any, idx: any) => {
                    if (file.series_idx == this.ss.series_idx) {
                        //find the item in items with .json
                        file.items.forEach((item: any, idx: any) => {
                            if (item.name.includes("json") && item.sidecar_json) {
                                //create a item.sidecar to keep the new json with update old values
                                const json = JSON.parse(item.sidecar_json);
                                for (const [key, value] of Object.entries(this.formData)) {
                                    json[key] = value;
                                }
                                item.sidecar = JSON.stringify(json);
                            }
                        });
                    }
                });
            } else {
                ElMessageBox.alert('Please fill all the required fields', 'Warning', {
                    confirmButtonText: 'OK',
                    type: 'warning'
                });
            }
                
        });
        this.$emit('form-submitted', this.ezbids);
    },
    conditionalLabel(item: any) {
        if(item.level === 'required') return `${item.details.display_name} (${item.condition})`;
        if(item.level === 'recommended') return `${item.details.display_name} (${item.condition})`;
        return `${item.field} (${item.condition})`;
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
        this.loadInitFormValues();
        //Task validate form on load
        this.showDialog = true;
        console.log("this.ref",this.$refs)
        this.$nextTick(() => {
            console.log("this.ref",this.$refs)
            this.$refs.form.validate();
        });
    },
    loadInitFormValues() {
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
    },
    getFieldsMetaData(type: string) {
        console.log("getFieldsMetaData",type);
        let fileObject = {};
        if(type == 'pet/pet') {
            console.log("petYaml", petYaml);
            fileObject = petYaml;
        }
        if(type == 'perf/asl') fileObject = aslYaml;
        
        let result = {
            required: [],
            recommended: [],
            optional: [],
            conditional: []
        };

        console.log("fileObject", fileObject);

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

                //fields with level_addendum
                const levelAddendum = metadata.level_addendum || '';
                if (levelAddendum.includes('required if') || levelAddendum.includes('required when')) {
                    result.conditional.push({...fieldData,level: 'required', condition: levelAddendum});
                } else if (levelAddendum.includes('recommended if') || levelAddendum.includes('recommended when')) {
                    result.conditional.push({...fieldData, level: 'recommended', condition: levelAddendum});
                }
            }
        }

        console.log("result", result);
    
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

        // remove duplicate conditional fields Ex:(required if `LookLocker` is `true`)

        result.conditional = result.conditional.filter((item: any, index: number, self: { findIndex: (arg0: (conditionalItem: any) => boolean) => number; }) => {
            return index === self.findIndex((conditionalItem: any) => {
                return conditionalItem.field === item.field;
            });
        });

        return result;
    },
    generateValidationRules(fieldsMetadata: { required: never[]; recommended: never[]; optional: never[]; conditional: never[]; }) {
            console.log("fieldsMetadata", fieldsMetadata);
            const rules = {};   
            // For required fields
            fieldsMetadata.required.forEach((item: { field: string | number; }) => {
                rules[item.field] = [
                    { required: true, message: `${item.field} is required`, trigger: 'change' } //change checks in real time
                ];
            });
             // For conditional fields
            fieldsMetadata.conditional.forEach((item: { level: string; field: string | number; condition: string; }) => {
                if (item.level === 'required') {
                    rules[item.field] = [{
                        validator: (rule: any, value: string | null, callback: (arg0: Error | undefined) => void) => {
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
                                    callback(new Error('This field is required based on the condition '+fieldName+' == '+expectedValue));
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
                                    // console.log(`Validation failed for field ${item.field}.`);
                                    callback(new Error('This field is required based on the condition '+fieldName+' == '+expectedValue));
                                    return;
                                }
                            }

                            // Condition: "`fieldName` is `value`"
                            // matches = item.condition.match(/`(\w+)` is `(\w+)`/);
                            matches = item.condition.match(/`(\w+)`\s+is\s+`(\w+)`/i);
                            if (matches) {
                                const fieldName = matches[1];
                                const expectedValue = matches[2];
                                // console.log("isValue",`Field to check: ${fieldName}, Expected: ${expectedValue}, Current: ${this.formData[fieldName]}`);
                                if (this.formData.hasOwnProperty(fieldName) && String(this.formData[fieldName]) === expectedValue && !value) {
                                    // console.log(`Validation failed for field ${item.field}.`);
                                    callback(new Error('This field is required based on the condition '+fieldName+' == '+expectedValue));
                                    return;
                                }
                            }

                            // required if PETRadioChemistry.fields.ModeOfAdministration == 'bolus-infusion' 
                            // with pet/pet the bids yaml file follows structure of section.fields.field
                            //lets extract the field name from the condition

                            matches = item.condition.match(/(\w+)\.fields\.(\w+)\s+==\s+['"]([\w-]+)['"]/i);
                            if (matches) {
                                // const section = matches[1];
                                const fieldName = matches[2];
                                const expectedValue = matches[3];
                                // console.log("section",`Section: ${section}, Field to check: ${fieldName}, Expected: ${expectedValue}, Current: ${this.formData[fieldName]}`);
                                if (this.formData.hasOwnProperty(fieldName) && String(this.formData[fieldName]) === expectedValue && !value) {
                                    // console.log(`Validation failed for field ${item.field}.`);
                                    callback(new Error('This field is required based on the condition '+fieldName+' == '+expectedValue));
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
            // console.log('Generated Rules:', rules);
            return rules;

        },
        setTypeforField(details: { type: null; anyOf: any[]; }) {
            if(details.type != null) return this.parseType(details.type);
            if(details?.anyOf?.length > 0) {
                if(details.anyOf[0].type) return this.parseType(details.anyOf[0].type);
                else {
                    details.anyOf.forEach((item: any) => {
                        if(item.type) return this.parseType(item.type);
                    });
                    return "";
                }
            }
            return "";
        },
        parseType(type: string) {
            if(type == 'string') return "";
            if(type == 'number') return null;
            if(type == 'boolean') return false;
            if(type == 'array') return [];
            if(type == 'object') return {};
            return "";
        }
    }
});
</script>
<style scoped>
.editModalityInputItem {
    margin-top: 20px;
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
</style>
```