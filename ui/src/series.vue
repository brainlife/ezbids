<template>
<div>
    <h4>Series / Datatype Mappings</h4>
    <p>Please update how you'd like to map each dicom SeriesDescription to BIDS datatype/entities.</p>
    <el-table :data="$root.series" style="width: 100%" size="mini" class="table-align-top">
        <el-table-column label="Series Number" width="150px">
            <template slot-scope="scope">
                <p style="margin-top: 10px">{{scope.row.SeriesNumber}}</p>
            </template>
        </el-table-column>
        <el-table-column label="Series Description" width="300px">
            <template slot-scope="scope">
                <!--<el-tag type="info" size="mini"><small>{{scope.row.SeriesNumber}}</small></el-tag>-->
                <p style="margin-top: 10px;">
                    <i class="el-icon-right" style="float: right; font-size: 150%; font-weight: bold;"/>
                    {{scope.row.SeriesDescription}}
                </p>
                <!-- <el-checkbox v-model="scope.row.include">Include in the BIDS output</el-checkbox> -->
                <p> 
                    <el-tag type="info" size="mini"><small>EchoTime: {{scope.row.EchoTime}}</small></el-tag>&nbsp;
                    <el-tag type="info" size="mini"><small>ImageType: {{scope.row.ImageType}}</small></el-tag>&nbsp;
                    <el-tag type="info" size="mini"><small>MultibandAccelerationFactor: {{scope.row.MultibandAccelerationFactor}}</small></el-tag>&nbsp;
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
                            size="small" style="width: 100%">
                            <el-option-group v-for="type in $root.datatypes" :key="type.label" :label="type.label">
                                <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                    {{type.label}} / {{subtype.label}}
                                </el-option>
                            </el-option-group>
                        </el-select>
                    </el-form-item>
                    <div v-if="scope.row.type">
                        <el-form-item v-for="(v, entity) in getSomeEntities(scope.row.type)" :key="entity" :label="entity+'-'+(v=='required'?' *':'')" style="width: 350px">
                            <el-popover width="300" trigger="focus" placement="right-start"
                                :title="$root.bids_entities[entity].name" 
                                :content="$root.bids_entities[entity].description">
                                <el-input slot="reference" v-model="scope.row.entities[entity]" size="small" :required="v == 'required'"/>
                            </el-popover>
                        </el-form-item>
                    </div>
                    <!--
                    <div v-if="scope.row.type && scope.row.type.startsWith('fmap/')">
                        <el-form-item label="IntendedFor">
                            <el-select v-model="scope.row.IntendedFor" multiple placeholder="Select Series" style="width: 100%">
                                <el-option
                                v-for="(s, idx) in $root.series" :key="idx"
                                :label="s.SeriesDescription" :value="idx">
                                </el-option>
                            </el-select>
                        </el-form-item>
                    </div> 
                    -->
                </el-form>
            </template>
        </el-table-column>
    </el-table>
</div>
</template>

<script>

//import SlideUpDown from 'vue-slide-up-down'

export default {
    components: {
        //SlideUpDown,
    },
    data() {
        return {
            showInfo: {},
        }
    },
    watch: {
    },

    created() {
    },

    methods: {
        getSomeEntities(type) {
            let entities = this.$root.getEntities(type);

            //we don't want user set sub/ses through series
            delete entities.sub;
            delete entities.ses;
            delete entities.run;

            return entities;
        },

        toggleInfo(entity) {
            this.$set(this.showInfo, entity, !this.showInfo[entity]);
        },
    },
}
</script>

<style scoped>
.el-form-item {
    margin-bottom: 0;
}
</style>
