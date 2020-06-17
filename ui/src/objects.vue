<template>
<div class="objects">
    <el-row :gutter="5">
        <el-col :span="5">
            <h4>BIDS Structure</h4>
            <div v-for="(o_sub, sub) in subs" :key="sub" style="font-size: 90%;">
                <span v-if="sub != ''" class="hierarchy" style="opacity: 0.8;"><i class="el-icon-user-solid"/> <small>sub</small> {{sub}} <small>({{o_sub.objects.length}})</small></span>
                <div v-for="(o_ses, ses) in o_sub.sess" :key="ses" :class="{'left-border': ses != ''}">
                    <span v-if="ses != ''" class="hierarchy" style="opacity: 0.8;"><i class="el-icon-time"/> <small>ses</small> {{ses}} <!--<small>({{o_ses.objects.length}})</small>--></span>
                    <div v-for="(o_run, run) in o_ses.runs" :key="run" @click="selected = o_run.objects" 
                        class="hierarchy clickable" :class="{'selected': selected === o_run.objects}">
                        <span v-if="run != ''" style="opacity: 0.8;"><small>run</small> {{run}} <!--({{o_run.objects.length}})--></span>
                        <div class="left-border">
                            <div v-for="(o, idx) in o_run.objects" :key="idx" style="padding-left: 6px; padding: 2px;">
                                <datatype :o="o"/>
                                <el-badge v-if="o.analysisResults.errors.length > 0" type="danger" 
                                    :value="o.analysisResults.errors.length" 
                                    style="margin-left: 5px;"/>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </el-col>
        <el-col :span="19">
            <p v-if="!selected"><small>Please select data objects on the left menu.</small></p>
            <el-table v-if="selected" :data="selected" style="width: 100%" border>
                <el-table-column label="Hierarchy" width="200" class-name="vtop">
                    <template slot-scope="scope">
                        <datatype :o="scope.row"/>

                        <div class="sub-title">Subject</div>
                        <el-input v-model="scope.row.hierarchy.subject" size="small">
                            <!--<template slot="suffix">Subject</template>-->
                        </el-input>

                        <div class="sub-title">Session</div>
                        <el-input v-model="scope.row.hierarchy.session" size="small"/>

                        <div class="sub-title">Run</div>
                        <el-input v-model="scope.row.hierarchy.run" size="small"/>

                        <div class="sub-title">Datatype</div>
                        <el-select v-model="scope.row.type" placeholder="Modality" size="small">
                            <el-option-group v-for="type in types" :key="type.label" :label="type.label">
                                <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                 <!-- :label="type.label+' / '+subtype.label" :value="subtype.value"/>-->
                                    {{type.label}} / {{subtype.label}}
                                    <!--<datatype :o="{type: subtype.value, hierarchy: {}}"/>-->
                                </el-option>
                            </el-option-group>
                        </el-select>

                        <div class="item" v-if="scope.row.type.startsWith('func/')">
                            <div class="sub-title">Task Name</div>
                            <el-input v-model="scope.row.hierarchy.task" size="small" required>
                            </el-input>
                        </div>

                        <p>
                            <el-checkbox v-model="scope.row.include" title="Include this object in the BIDS output">Include</el-checkbox>
                        </p>

                    </template>
                </el-table-column>

                <el-table-column label="File / sidecar" class-name="vtop">
                    <template slot-scope="scope">
                        <el-alert type="error" v-for="(error, idx) in scope.row.analysisResults.errors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
                        <el-form>
                            <div class="item" v-for="(item, idx) in scope.row.items" :key="idx">
                                <el-select v-model="item.path" placeholder="Source path" size="small" style="width: 100%">
                                    <el-option v-for="(path, idx) in scope.row.paths" :key="idx" :label="path" :value="path"/>
                                    <template slot="prefix">{{item.id}}</template>
                                </el-select>
                                <div v-if="item.sidecar">
                                    <kveditor :kv="item.sidecar"/>
                                </div>
                            </div>
                         </el-form>

                    </template>
                </el-table-column>
            </el-table>
            
        </el-col>
    </el-row>
    <!--
    <pre>{{objects}}</pre>
    {{$store.state.objects}}
    <el-button @click="increment">Increment {{$store.state}}</el-button>
    -->
</div>
</template>

<script>

//import store from './store'
//import obj from '@/components/object'
import kveditor from '@/components/kveditor'
import datatype from '@/components/datatype'

export default {
    //store,
    components: {
        kveditor,
        datatype,
    },
    data() {
        return {
            types: [
                {label: 'Anatomical', 
                    options: [
                        {value: 'anat/t1w', label: "t1w"},
                        {value: 'anat/t2w', label: "t2w"},
                        {value: 'anat/flair', label: "Flair"},
                    ]
                },
                {value: 'dwi', label: 'Diffusion', 
                    options: [
                        {value: 'dwi', label: "DWI"},
                    ]
                },
                {value: 'func', label: 'Functional',  
                    options: [
                        {value: 'func/bold', label: "Bold"}, 
                        {value: 'func/cbv', label: "Cerebral Blood Volume"},
                    ]
                },
                {value: 'fmap', label: 'Field Map', 
                    options: [
                        {value: 'fmap/2phasemag', label: "2 Phase images"},
                        {value: 'fmap/phasediff', label: "Phase Difference"},
                        {value: 'fmap/single', label: "single(real) image"},
                        {value: 'fmap/pepolar', label: "Multiple phase encoded"},
                    ]
                },
            ],

            //organize objects by hierarchy
            subs: {},
            selected: null,
        }
    },
    created() {
        this.analyzeH();
    },
    methods: {
        /*
        increment() {
            this.$store.commit('increment')
            console.log(this.$store.state.count);
        }
        */
        //return error messages
        /*
        validate(o) {
            let errors = [];
            if(o.type == "func/bold" && !o.hierarchy.task) {
                errors.push("func/bold needs task name");
            }
            return errors;
        },
        */

        analyzeH() {
            this.subs = {}; 
            this.sess = {};
            this.runs = {};
            this.$root.objects.forEach(o=>{
                let sub = o.hierarchy.subject||"";
                let ses = o.hierarchy.session||"";
                let run = o.hierarchy.run||"";

                if(!this.subs[sub]) this.subs[sub] = { sess: {}, objects: []}; 
                this.subs[sub].objects.push(o);

                if(!this.subs[sub].sess[ses]) this.subs[sub].sess[ses] = { runs: {}, objects: [] };
                this.subs[sub].sess[ses].objects.push(o);

                if(!this.subs[sub].sess[ses].runs[run]) this.subs[sub].sess[ses].runs[run] = { objects: [] };
                this.subs[sub].sess[ses].runs[run].objects.push(o);
            });
        }
    },
    computed: {

    },
}
</script>

<style scoped>
.item {
padding-bottom: 5px;
margin-bottom: 5px;
}
.hierarchy {
padding: 3px;
display: block;
}
.hierarchy.clickable {
transition: background-color 0.3s;
}
.hierarchy.selected {
background-color: #d9ecff;
}
.hierarchy.clickable:hover {
background-color: #ddd;
cursor: pointer;
}
.left-border {
margin-left: 8.5px; 
padding-left: 4px; 
border-left: 2px solid #3331;
}
.exclude {
opacity: 0.5;
}
</style>

