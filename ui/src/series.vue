<template>
<div v-if="$root.currentPage.id == 'series'" style="padding: 20px;">
    <h4>Series / Datatype Mappings</h4>
    <p>Please update how you'd like to map each dicom SeriesDescription to BIDS datatype/entities.</p>
    <el-table :data="$root.series" size="mini" class="table-align-top">
        <el-table-column label="Series" width="350px">
            <template slot-scope="scope">
            {{scope.row.entities}}
                <p style="margin-top: 10px;">
                    <i class="el-icon-right" style="float: right; font-size: 150%; font-weight: bold;"/>
                    <el-tag type="info" size="mini">sn {{scope.row.SeriesNumber}}</el-tag>&nbsp;
                    {{scope.row.SeriesDescription}}
                </p>
                <p> 
                    <el-tag type="info" size="mini"><small>EchoTime: {{scope.row.EchoTime}}</small></el-tag><br>
                    <el-tag type="info" size="mini"><small>ImageType: {{scope.row.ImageType}}</small></el-tag><br>
                    <el-tag type="info" size="mini"><small>MultibandAccelerationFactor: {{scope.row.MultibandAccelerationFactor}}</small></el-tag><br>
                    <br>
                    <small>RepetitionTime: {{scope.row.repetitionTimes}}</small>
                </p>
            </template>
        </el-table-column>
        <el-table-column label="BIDS Datatype">
            <template slot-scope="scope">
                <el-form label-width="100px">
                    <el-form-item label="Datatype">
                        <el-select v-model="scope.row.type" reqiured
                            placeholder="unknown" 
                            size="small">
                            <el-option-group v-for="type in $root.datatypes" :key="type.label" :label="type.label">
                                <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                    {{type.label}} / {{subtype.label}}
                                </el-option>
                            </el-option-group>
                        </el-select>
                    </el-form-item>
                    <div v-if="scope.row.type">
                        <el-form-item v-for="(v, entity) in getSomeEntities(scope.row.type)" :key="entity" 
                            :label="entity+'-'+(v=='required'?' *':'')" style="width: 350px">
                            <el-popover width="300" trigger="focus" placement="right-start"
                                :title="$root.bids_entities[entity].name" 
                                :content="$root.bids_entities[entity].description">
                                <el-input slot="reference" v-model="scope.row.entities[entity]" size="small" :required="v == 'required'" @change="validate(scope.row)"/>
                            </el-popover>
                        </el-form-item>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <el-alert show-icon :closable="false" type="error" v-for="(error, idx) in scope.row.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                    </div>
                </el-form>
            </template>
        </el-table-column>
    </el-table>

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

export default {
    data() {
        return {
            showInfo: {},
        }
    },
    watch: {
        '$root.currentPage'(v) {
            if(v.id == 'series') {
                this.$root.series.forEach(this.validate);
            }
        },
    },
    methods: {
        getSomeEntities(type) {
            let entities = this.$root.getEntities(type);

            //we don't want user set sub/ses through series
            delete entities.sub;
            delete entities.ses;
            //delete entities.run;

            return entities;
        },

        toggleInfo(entity) {
            this.$set(this.showInfo, entity, !this.showInfo[entity]);
        },

        validate(s) {
            Vue.set(s, 'validationErrors', []);
            let entities = this.$root.getEntities(s.type);
            for(let k in this.getSomeEntities(s.type)) {
                console.log(k);
                if(entities[k] == "required") {
                    console.log(k, "required", s.entities[k]);
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
                this.$root.changePage("participant");
            } else {
                alert('Please correct all issues');
                return false;
            }
        },

        back() {
            this.$root.changePage("session");
        },

    },
}
</script>

<style scoped>
.el-form-item {
    margin-bottom: 0;
}
</style>
