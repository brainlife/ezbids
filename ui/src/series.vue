<template>
<div>
    <p>Please decide how to map Acquisition Date to BIDS series ID. You can leave it blank if your study does not consists of multiple sessions.</p>
    <el-table :data="$root.series" style="width: 100%" size="mini" class="series-table">
        <el-table-column label="Include" width="100">
            <template slot-scope="scope">
                <el-checkbox v-model="scope.row.include" title="Include this series in the BIDS output"/>
            </template>
        </el-table-column>
        <el-table-column label="Series Description (id)" width="250">
            <template slot-scope="scope">
                <i class="el-icon-right" style="float: right"/>
                {{scope.row.description}} <small>{{scope.row.id}}</small>
            </template>
        </el-table-column>
        <el-table-column label="BIDS Datatype" width="150">
            <template slot-scope="scope">
                <!--
                <el-input v-model="scope.row.ses" placeholder="no session" size="small">
                    <template slot="prepend">ses-</template>
                </el-input>
                -->
                <el-select v-model="scope.row.type" placeholder="Modality" size="small" style="width: 100%">
                    <el-option-group v-for="type in $root.datatypes" :key="type.label" :label="type.label">
                        <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                            {{type.label}} / {{subtype.label}}
                        </el-option>
                    </el-option-group>
                </el-select>
            </template>
        </el-table-column>
        <el-table-column label="Series Specific Entities">
            <template slot-scope="scope">
                <div v-if="scope.row.type.startsWith('func/')">
                    <el-input v-model="scope.row.labels.task" size="small" required>
                        <template slot="prepend">Task Name</template>
                    </el-input>
                </div>
            </template>
        </el-table-column>
    </el-table>
</div>
</template>

<script>

export default {
    data() {
        return {
            //subjects: [] 
        }
    },
    watch: {
    },

    created() {
    },

    methods: {
    },
}
</script>

<style scoped>
.el-table td {
    vertical-align: top;
}
</style>
