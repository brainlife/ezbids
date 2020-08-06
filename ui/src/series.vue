<template>
<div>
    <h4>Series / Datatype Mappings</h4>
    <p>Please update how you'd like to map each dicom series to BIDS datatype.</p>
    <el-table :data="$root.series" style="width: 100%" size="mini" class="table-align-top">
        <el-table-column label="sn/Series Description" width="300px">
            <template slot-scope="scope">
                <i class="el-icon-right" style="float: right; font-size: 150%; font-weight: bold;"/>
                <el-tag type="info" size="mini"><small>{{scope.row.SeriesNumber}}</small></el-tag>
                {{scope.row.SeriesDescription}}
            </template>
        </el-table-column>
        <el-table-column label="BIDS Datatype">
            <template slot-scope="scope">
                <el-form label-width="100px">
                    <el-form-item label="">
                        <el-checkbox v-model="scope.row.include">Include this series in the BIDS output</el-checkbox>
                    </el-form-item>
                    <el-form-item label="Datatype">
                        <el-select v-model="scope.row.type" placeholder="Please select" size="small" style="width: 100%">
                            <el-option-group v-for="type in $root.datatypes" :key="type.label" :label="type.label">
                                <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                    {{type.label}} / {{subtype.label}}
                                </el-option>
                            </el-option-group>
                        </el-select>
                    </el-form-item>
                    <div v-if="scope.row.type" style="width: 350px">
                        <el-form-item v-for="(v, entity) in getSomeEntities(scope.row.type)" :key="entity" :label="entity+'-'+(v=='required'?' *':'')">
                            <el-popover width="300" trigger="focus" placement="right-start"
                                :title="$root.bids_entities[entity].name" 
                                :content="$root.bids_entities[entity].description">
                                <el-input slot="reference" v-model="scope.row.entities[entity]" size="small" :required="v == 'required'"/>
                                <!--
                                <p class="help-block">
                                    <b @click="toggleInfo(entity)" class="clickable">{{$root.bids_entities[entity].name}}</b> 
                                    <slide-up-down :active="showInfo[entity]">{{$root.bids_entities[entity].description}}</slide-up-down>
                                </p>
                                -->
                            </el-popover>
                        </el-form-item>
                    </div>
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
