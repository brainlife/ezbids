<template>
    <el-button @click="initForm()">Edit Modality</el-button>
    <el-dialog v-model="showDialog" title="Edit Modalities">
        <el-form ref="form" :model="formData" label-position="top" label-width="500px" :inline="true" :rules="rules"> 
            <div>
                <el-row>
                    <el-col :span="8">
                        <!-- // make the label recommended below and show example for boolean types, also try to enforce the types in the form -->
                        <h3>Required</h3>
                        <el-form-item class="editModalityInputItem" v-for="(item, index) in fields.required" :key="'required' + index" :label="`${item.details.display_name} ${item.details.type}`" :prop="item.field">
                            <template #label>
                                <span>
                                    {{ item.details.display_name }} 
                                    <el-tooltip placement="top">
                                        <template #content> {{ item.details.description }}</template>
                                        <!-- show question mark button-->
                                        <font-awesome-icon :icon="['fas', 'info-circle']" />
                                    </el-tooltip>
                                </span>
                            </template>
                            <el-input v-if="(item.details.type == 'string' || item.details.type == 'object' || item.details.type=='array') && item.details.enum == undefined"
                            :name="item.field" v-model="formData[item.field]" @input="this.$refs.form.validate()" :placeholder="getPlaceholderByType(item.details.type)"></el-input>
                            
                            <el-select v-if="item.details.enum" v-model="formData[item.field]" @change="this.$refs.form.validate()">
                                <el-option
                                    v-for="option in parseOptionsEnum(item?.details?.enum)"
                                    :key="option.value"
                                    :label="option.label"
                                    :value="option.value"
                                />
                            </el-select>

                            <el-input v-else-if="item.details.type == 'number'" type="text" inputmode="decimal" :name="item.field" :placeholder="getPlaceholderByType(item.details.type)" v-model="formData[item.field]" @input="this.$refs.form.validate()" ></el-input>
                            <el-select v-else-if="item.details.type == 'boolean'" @change="this.$refs.form.validate()" v-model="formData[item.field]" class="m-2" placeholder="Select" size="large">
                                <el-option
                                v-for="item in optionsBoolean"
                                :key="item.value"
                                :label="item.label"
                                :value="item.value"
                                />
                            </el-select>   
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <h3>Recommended</h3>
                        <el-form-item class="editModalityInputItem" v-for="(item, index) in fields.recommended" :key="'recommended' + index" :label="`${item.details.display_name}`" :prop="item.field">
                            <template #label>
                                <span>
                                    {{ item.details.display_name }} 
                                    <el-tooltip placement="top">
                                        <template #content> {{ item.details.description }}</template>
                                        <!-- show question mark button-->
                                        <font-awesome-icon :icon="['fas', 'info-circle']" />
                                    </el-tooltip>
                                </span>
                            </template>
                            <el-input v-if="(item.details.type == 'string' || item.details.type == 'object' || item.details.type=='array') && item.details.enum == undefined"
                            :name="item.field" v-model="formData[item.field]" @input="this.$refs.form.validate()" :placeholder="getPlaceholderByType(item.details.type)"></el-input>

                            {{ formData[item.field] , typeof (formData[item.field]) }}
                            
                            <el-select v-if="item.details.enum" v-model="formData[item.field]" @change="this.$refs.form.validate()">
                                <el-option
                                    v-for="option in parseOptionsEnum(item?.details?.enum)"
                                    :key="option.value"
                                    :label="option.label"
                                    :value="option.value"
                                />
                            </el-select>
                            <el-input v-else-if="item.details.type == 'number'" type="text" inputmode="decimal" :name="item.field" v-model.number="formData[item.field]" @input="this.$refs.form.validate()" :placeholder="getPlaceholderByType(item.details.type)"></el-input>
                            <el-select v-else-if="item.details.type == 'boolean'" v-model="formData[item.field]" class="m-2" @change="this.$refs.form.validate()" placeholder="Select" size="large">
                                <el-option
                                v-for="item in optionsBoolean"
                                :key="item.value"
                                :label="item.label"
                                :value="item.value"
                                />
                            </el-select>   
                        </el-form-item>
                    </el-col>

                    <el-col :span="8">
                        <h3>Optional</h3>
                        <el-form-item class="editModalityInputItem" v-for="(item, index) in fields.optional" :key="'optional' + index" :label="`${item.details.display_name}`" :prop="item.field">
                            
                            <template #label>
                                <span>
                                    {{ item.details.display_name }} 
                                    <el-tooltip placement="top">
                                        <template #content> {{ item.details.description }}</template>
                                        <!-- show question mark button-->
                                        <font-awesome-icon :icon="['fas', 'info-circle']" />
                                    </el-tooltip>
                                </span>
                            </template>
                            
                            <el-input v-if="(item.details.type == 'string' || item.details.type == 'object' || item.details.type=='array') && item.details.enum == undefined"
                            :name="item.field" v-model="formData[item.field]" @input="this.$refs.form.validate()" :placeholder="getPlaceholderByType(item.details.type)"></el-input>
                            
                            <el-select v-if="item.details.enum" v-model="formData[item.field]" @change="this.$refs.form.validate()">
                                <el-option
                                    v-for="option in parseOptionsEnum(item?.details?.enum)"
                                    :key="option.value"
                                    :label="option.label"
                                    :value="option.value"
                                />
                            </el-select>
                            <el-input v-else-if="item.details.type == 'number'" type="text" inputmode="decimal" :name="item.field" v-model.number="formData[item.field]" @input="this.$refs.form.validate()" :placeholder="getPlaceholderByType(item.details.type)"></el-input>
                            <el-select v-else-if="item.details.type == 'boolean'" v-model="formData[item.field]" class="m-2" @change="this.$refs.form.validate()" placeholder="Select" size="large">
                                <el-option
                                v-for="item in optionsBoolean"
                                :key="item.value"
                                :label="item.label"
                                :value="item.value"
                                />
                            </el-select>   
                        </el-form-item>
                        <el-form-item class="editModalityInputItem" v-for="(item, index) in fields.conditional" :key="'conditional' + index" :label="`${item.details.display_name}`" :prop="item.field">

                            <template #label>
                                <span>
                                    {{ item.details.display_name }} 
                                    <el-tooltip placement="top">
                                        <template #content> {{ item.details.description }}</template>
                                        <!-- show question mark button-->
                                        <font-awesome-icon :icon="['fas', 'info-circle']" />
                                    </el-tooltip>
                                </span>
                            </template>
                            <el-input v-if="(item.details.type == 'string' || item.details.type == 'object' || item.details.type=='array') && item.details.enum == undefined"
                            :name="item.field" v-model="formData[item.field]" @input="this.$refs.form.validate()" :placeholder="getPlaceholderByType(item.details.type)"></el-input>
                            
                            <el-select v-if="item.details.enum" v-model="formData[item.field]" @change="this.$refs.form.validate()">
                                <el-option
                                    v-for="option in parseOptionsEnum(item?.details?.enum)"
                                    :key="option.value"
                                    :label="option.label"
                                    :value="option.value"
                                />
                            </el-select>   
                            
                            <el-input v-else-if="item.details.type == 'number'" type="text" inputmode="decimal" :name="item.field" v-model.number="formData[item.field]" @input="this.$refs.form.validate()" :placeholder="getPlaceholderByType(item.details.type)"></el-input>
                            <el-select v-else-if="item.details.type == 'boolean'" v-model="formData[item.field]" @change="this.$refs.form.validate()" class="m-2" placeholder="Select" size="large">
                                <el-option
                                v-for="item in optionsBoolean"
                                :key="item.value"
                                :label="item.label"
                                :value="item.value"
                                />
                            </el-select>   
                        </el-form-item>
                    </el-col>
            </el-row>
            </div>
        </el-form>
        <br>
        <span slot="footer" class="dialog-footer">
            <!-- {{ formData }} -->
            <el-button @click="showDialog = false">Cancel</el-button>
            <el-button type="primary" @click="submitForm">Submit</el-button>
        </span>
    </el-dialog>
</template>

<script lang="ts">
import aslYaml from "../../src/assets/schema/rules/sidecars/asl.yaml";

import metadata_types from '../../src/assets/schema/rules/sidecars/metadata_types.yaml';
import { ElMessageBox, ElMessage, useFocus } from 'element-plus'
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
        optionsBoolean : [
            { value: true, label: 'True' },
            { value: false, label: 'False' },
            // { value: null, label: 'Null'}
        ],
        //MoType add options 
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
                                // only if value is not null, empty string or empty array or undefined
                                for (let [key, value] of Object.entries(this.formData)) {
                                    const type = Object.values(this.fields).flatMap(fieldArray => fieldArray).find((item: any) => item.field == key)?.details.type;
                                    if (value !== null && value !== "" && value !== undefined && !(Array.isArray(value) && value.length === 1 && value[0] === "")){
                                        if(type == 'number') value = Number(value);
                                        if(type == 'boolean') value = Boolean(value);
                                        if(type == 'array') value = value.toString().split(',');
                                        if(type == 'object') value = JSON.parse(value);
                                        json[key] = value;
                                    }
                                }

                                item.sidecar_json = JSON.stringify(json, null, 2);
                                // console.log("finalOutput",item.sidecar);
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
        this.showDialog = false;
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

        //set default values for all fields in the form optional, recommended, required, conditional
        for(let field in this.fields) {
            this.fields[field].forEach((item: any) => {
                this.formData[item.field] = item.details.default_value;
            });
        }
        //match the pos of type and series.idx inside the ezbids.objects[]
        this.loadInitFormValues();
        //Task validate form on load
        this.showDialog = true;
        this.$nextTick(() => {
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
                        // console.log("jsonOrginal",json);
                        for (const [key, value] of Object.entries(json)) {
                            if(this.formData.hasOwnProperty(key)) this.formData[key] = value;
                        }
                    }
                });
            }
        });
    },
    getFieldsMetaData(type: string) {
        let fileObject = {};
        // if(type == 'pet/pet') {
        //     console.log("petYaml", petYaml);
        //     fileObject = petYaml;
        // }
        if(type == 'perf/asl') fileObject = aslYaml;
        
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
                details.default_value = this.setDefaultValue(details);
                details.type = this.parseType(details);
                if(details.type == 'array') {
                    console.log("details",details);
                }

                let fieldData = {field,details};

                

                if (metadata === 'required' && !result.required.some(item=> item.field == fieldData.field)) result.required.push(fieldData);

                if (metadata === 'recommended' && !result.recommended.some(item=> item.field == fieldData.field)) result.recommended.push(fieldData);

                if(metadata === 'optional' && !result.optional.some(item=> item.field == fieldData.field)) result.optional.push(fieldData);

                //fields with level
                const level = metadata.level || '';
                if (level === 'required' && !result.required.some(item=> item.field == fieldData.field)) {
                    result.required.push(fieldData);
                } else if (level === 'recommended' && !result.recommended.some(item=> item.field == fieldData.field)) {
                    result.recommended.push(fieldData);
                } else if (level === 'optional' && !result.optional.some(item=> item.field == fieldData.field)) {
                    result.optional.push(fieldData);  // Include optional fields in the recommended list
                }

                //fields with level_addendum
                const levelAddendum = metadata.level_addendum || '';
                if (levelAddendum.includes('required if') || levelAddendum.includes('required when')) {
                    const obj = {...fieldData,level: 'required', condition: levelAddendum};
                    if(!result.conditional.some(item=> item.field == fieldData.field))result.conditional.push(obj);
                } else if (levelAddendum.includes('recommended if') || levelAddendum.includes('recommended when')) {
                    const obj = {...fieldData, level: 'recommended', condition: levelAddendum}
                    if(!result.conditional.some(item=> item.field == fieldData.field)) result.conditional.push(obj);
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
    generateValidationRules(fieldsMetadata: { required: never[]; recommended: never[]; optional: never[]; conditional: never[]; }) {
            const rules = {}; 

            // For required fields
            fieldsMetadata.required.forEach((item: { field: string | number; }) => {
                rules[item.field] = [
                    { required: true, message: `${item.field} is required`, trigger: 'change' } //change checks in real time
                ];
                this.addNumericValidationRule(rules,item);
                this.addArrayValidationRule(rules,item);
            });

            // For recommended fields
            fieldsMetadata.recommended.forEach((item: { field: string | number; }) => {
                rules[item.field] = [];
                this.addNumericValidationRule(rules,item);
                this.addArrayValidationRule(rules,item);
            });

            // For optional fields

            fieldsMetadata.optional.forEach((item: { field: string | number; }) => {
                rules[item.field] = [];
                this.addNumericValidationRule(rules,item);
                this.addArrayValidationRule(rules,item);
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
                                const expectedValue = matches[2];  
                                // console.log("true/false",`Field to check: ${fieldName}, Expected: ${expectedValue}, Current: ${this.formData[fieldName]}`);                          
                                if (this.formData.hasOwnProperty(fieldName) && 
                                    this.formData[fieldName] === expectedValue && expectedValue &&
                                    (value == null || value === '')) {
                                    // console.log("t/F",`Validation failed for field ${item.field}.`,this.formData[fieldName]);
                                    callback(new Error('This field is required based on the condition '+fieldName+' == '+expectedValue,));
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
                                    callback(new Error('This field is required based on the condition '+fieldName+' == '+expectedValue));
                                    return;
                                }
                            }

                            callback();

                        },
                        trigger: 'change'
                    }];

                    this.addNumericValidationRule(rules,item);
                    this.addArrayValidationRule(rules,item);
                }
            });

            // No special rules for recommended as they are optional, but you can add if needed
            // console.log('Generated Rules:', rules);
            return rules;

        },
        addNumericValidationRule(rules,item) {
            if (item.details && item.details.type === 'number') {
                console.log("itemNUMBER",item);
                if (!rules[item.field]) {
                    rules[item.field] = [];
                }
                rules[item.field].push({
                    validator: (rule, value, callback) => {
                        if (value !=null && !this.isNumeric(value)) {
                            callback(new Error('Please enter a valid number'));
                        } else {
                            callback();
                        }
                    },
                    trigger: 'change'
                });
            }
        },

        addArrayValidationRule(rules,item) {
            if (item.details && item.details.type === 'array') {
                if (!rules[item.field]) {
                    rules[item.field] = [];
                }
                rules[item.field].push({
                    validator: (rule, value, callback) => {
                        const validation = this.getArrayValidation(value,item);
                        if (value !=null && validation !== true) {
                            callback(new Error(validation));
                        } else {
                            callback();
                        }
                    },
                    trigger: 'change'
                });
            }
        },

        getArrayValidation(value,item) {
            // prevent user from entering [] or [""]
            // add check to prevent from entering brackets
            if(value.includes('[') || value.includes(']')) return "Please enter a valid entry no brackets allowed [], only comma separated values";
          
            if(item.details.items.type == 'number') {
                 // If the value is a string that represents a single number or a list of numbers separated by commas
                if(typeof value == 'string') {
                    // If it’s a single number, try to parse it
                    if(!isNaN(Number(value))) {
                        value = Number(value);
                    } 
                    // If it's a list of numbers separated by commas
                    else if(value.includes(',')) {
                        // Split the string into an array of strings
                        let stringArray = value.split(',');
                        
                        // Check if every item in the string array represents a number
                        if(stringArray.every((item: any) => !isNaN(Number(item)))) {
                            value = stringArray.map(Number); // If all are numbers, parse strings to numbers and update the value to be the number array
                        } else {
                            return "Every item in the list should be a number";
                        }
                    } else {
                        return "The value should be a number or a list of numbers separated by commas";
                    }
                }

                // Check if value is a number
                if(typeof value == 'number') return true;
                
                // Check if value is an array
                if(Array.isArray(value)) {
                    // Check if array is empty
                    if(value.length == 0) return true;
                    // Check if array has empty string
                    if(value.length == 1 && value[0] == "") return true;
                    // Check if array has only number values
                    if(value.every((item: any) => typeof item == 'number')) return true;
                }
                
                return "The value should be a number or an array of numbers";

            }
            return true;
        },

        setDefaultValue(details: { type: null; anyOf: any[]; }) {
            if(details.type != null) return this.parseDefaultValue(details.type);
            if(details?.anyOf?.length > 0) {
                if(details.anyOf[0].type) return this.parseDefaultValue(details.anyOf[0].type);
                else {
                    details.anyOf.forEach((item: any) => {
                        if(item.type) return this.parseDefaultValue(item.type);
                    });
                    return "";
                }
            }
            return "";
        },
        parseType(details: {type: null; anyOf:any[]}) {
            if(details.type != null) return details.type;
            if(details?.anyOf?.length > 0) {
                if(details.anyOf[0].type) return details.anyOf[0].type;
                else {
                    details.anyOf.forEach((item: any) => {
                        if(item.type) return item.type;
                    });
                    return "string";
                }
            }
            return "string";
        },
        parseDefaultValue(type: string) {
            if(type == 'string') return "";
            if(type == 'number') return null;
            if(type == 'boolean') return undefined;
            if(type == 'array') return []; // will help user to identify its an array
            if(type == 'object') return {}; // will help user to identify its an object
            return "";
        },
        isNumeric(value) {
            return /^(\-?\d+(\.\d+)?)?$/.test(value);
        },
        getPlaceholderByType(type) {
            if(type == 'string') return "Enter string";
            if(type == 'number') return "Enter number";
            if(type == 'boolean') return "Select";
            if(type == 'array') return "Enter array []";
            if(type == 'object') return "Enter object {}";
        },
        parseOptionsEnum(enumArray) {
            // return enumArray;
            const array =  enumArray.map((item: any) => {
                if(typeof item == 'object') {
                    // "$ref": "objects.enums.CASL.value"
                    if(item['$ref']) {
                        // objects.enums.CASL.value -> CASL
                        // regex to get CASL 
                        // const regex = /objects.enums.(\w+).value/;
                        const regex = /objects.enums.(\w+).value/;
                        const refObject = regex.exec(item['$ref']);
                        return {value: refObject[1], label: refObject[1]};
                    }
                }
                return {value: item, label: item};
            });
            return array;
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