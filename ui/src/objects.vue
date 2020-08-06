<template>
<div class="objects">
    <p>Please make sure all subject/session/series mappings are correctly applied to your data.</p>
    <p>By default, entity specified in the <b>Series</b> page will be used as defaults for all objects. On this page you can override those entities.</p>
    <div class="bids-structure">
        <h5>BIDS Structure</h5>
        <div v-for="(o_sub, sub) in $root.subs" :key="sub" style="font-size: 90%;">
            <span v-if="sub != ''" class="hierarchy" style="opacity: 0.8;">
                <i class="el-icon-user-solid"/> 
                <small>sub</small> {{sub}} 
                <small>({{o_sub.objects.length}})</small>
            </span>
            <div v-for="(o_ses, ses) in o_sub.sess" :key="ses" :class="{'left-border': ses != ''}" class="left-border">
                <span v-if="ses != ''" class="hierarchy" style="opacity: 0.8;"><i class="el-icon-time"/> <small>ses</small> {{ses}}</span>
                <div v-for="(o, idx) in o_ses.objects" :key="idx" style="padding: 2px;" class="clickable" :class="{'selected': so === o}" @click="select(o, o_ses)">
                    <el-tag type="info" size="mini"><small>{{o.SeriesNumber}}</small></el-tag>
                    &nbsp;
                    <datatype :o="o"/>
                    <el-badge v-if="o.validationErrors.length > 0" type="danger" 
                        :value="o.validationErrors.length" 
                        style="margin-left: 5px;"/>
                </div>
            </div>
        </div>
    </div>
    <div class="object">
        <p v-if="!so">
            <br>
            <br>
            <br>
            <br>
            <br>
            <i class="el-icon-back"/> <small>Please select an object to view/edit in the BIDS Structure list</small>
        </p>
        <div v-if="so">
            <div style="margin-bottom: 10px;">
                <el-alert type="error" v-for="(error, idx) in so.validationErrors" :key="idx" :title="error" style="margin-bottom: 4px;"/>
            </div>

            <el-form label-width="100px">
                <el-form-item label="Include">
                    <el-checkbox v-model="so.include" title="Include this object in the BIDS output" @change="update(so)">Include this object in BIDS output</el-checkbox>
                </el-form-item>

                <div :class="{'object-exclude': !so.include}">
                    <el-form-item label="Series">
                        {{so.SeriesDescription}}
                        <el-tag type="info" size="mini"><small>{{so.SeriesNumber}}</small></el-tag>
                    </el-form-item>
                    <el-form-item label="Datatype">
                        <el-select v-model="so.type" placeholder="Modality" size="small" style="width: 100%" @change="update(so)">
                            <el-option-group v-for="type in $root.datatypes" :key="type.label" :label="type.label">
                                <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                    {{type.label}} / {{subtype.label}}
                                </el-option>
                            </el-option-group>
                        </el-select>
                    </el-form-item>

                    <div style="width: 350px;">
                        <el-form-item v-for="(v, entity) in $root.getEntities(so.type)" :key="entity" 
                            :label="entity+'-'+(v=='required'?' *':'')">
                            <el-popover width="300" trigger="focus" placement="right-start"
                                :title="$root.bids_entities[entity].name" 
                                :content="$root.bids_entities[entity].description">
                                <el-input slot="reference" v-model="so.entities[entity]" size="small" @blur="update(so)" :placeholder="getDefault(so, entity)"/>
                            </el-popover>
                        </el-form-item>
                    </div>

                    <div v-for="(item, idx) in so.items" :key="idx" class="border-top">
                        <el-form-item :label="item.name||'noname'">
                            <el-select v-model="item.path" placeholder="Source path" size="small" style="width: 100%">
                                <el-option v-for="(path, idx) in so.paths" :key="idx" :label="path" :value="path"/>
                            </el-select>
                        </el-form-item>
                        <el-form-item v-if="item.sidecar" label="Sidecar">
                            <el-input type="textarea" rows="10" v-model="item.sidecar_json" @blur="update(so)"/>
                        </el-form-item>
                        <el-form-item v-if="item.headers" label="Nifti Headers (readonly)">
                            <pre class="headers">{{item.headers}}</pre>
                        </el-form-item>
                        <br>
                    </div>

                    <div v-if="so.type.startsWith('fmap/')" class="border-top">
                        <el-form-item label="IntendedFor">
                            <p v-for="(o, idx) in sess.objects.filter(o=>o!=so)" :key="idx" style="margin: 0;">
                                <el-checkbox :checked="so.IntendedFor[idx]" @change="updateIntendedFor($event, idx)">
                                    <el-tag type="info" size="mini"><small>{{o.SeriesNumber}}</small></el-tag>
                                    {{o.SeriesDescription}}
                                    &nbsp;
                                    <datatype :o="o"/>
                                </el-checkbox>
                            </p>
                            <!--
                            <el-select v-model="so.IntendedFor" multiple placeholder="Select Object" style="width: 100%">
                                <el-option
                                v-for="(o, idx) in $root.objects"
                                :key="idx"
                                :label="s.SeriesDescription"
                                :value="idx">
                                </el-option>
                            </el-select>
                            -->
                        </el-form-item>
                    </div>

                </div>
                <div style="margin-top: 5px; padding: 5px; background-color: #eee;">
                    <el-form-item v-if="so.pngPath" label="Thumbnail">
                        <img :src="$root.apihost+'/download/'+$root.session._id+'/'+so.pngPath"/>
                    </el-form-item>
                </div>
            </el-form>
            <pre v-if="config.debug">{{so}}</pre>
        </div><!--selected != null-->
    </div><!--object-->
</div>
</template>

<script>

import Vue from 'vue'

import datatype from '@/components/datatype'

export default {
    components: {
        datatype,
    },
    data() {
        return {
            so: null, //selected object
            sses: [], //selected session
            config: Vue.config,
        }
    },
    
    mounted() {
    },

    methods: {
        select(o, sess) {
            this.sess = sess;
            this.so = o;
        },

        update(o) {
            this.$root.organizeObjects();
            this.$root.validateObject(o);
            this.$root.validated = this.$root.isAllValid(); 
        },

        updateIntendedFor(checked, idx) {
            this.so.IntendedFor[idx] = checked;
            this.$forceUpdate();
        },

        getDefault(o, entity) {
            if(entity == "sub") {
                const subject = this.$root.findSubject(o);
                return subject.sub;
            } else if(entity == "ses") {
                const session = this.$root.findSession(o);
                return session.ses;
            } else {
                //rest should come from series
                const series = this.$root.findSeries(o);
                return series.entities[entity];
            }
        },
    },

    computed: {
    },
}
</script>

<style scoped>
.objects {
position: relative;
}
.bids-structure {
position: absolute;
width: 275px;
}
.object {
margin-left: 280px;
}
.item {
padding-bottom: 5px;
margin-bottom: 5px;
}
.hierarchy {
padding: 3px;
display: block;
line-height: 100%;
}
.clickable {
transition: background-color 0.3s;
}
.selected {
background-color: #d9ecff;
}
.clickable:hover {
background-color: #ddd;
cursor: pointer;
}
.left-border {
margin-left: 8.5px; 
padding-left: 4px; 
border-left: 2px solid #3331;
padding-top: 4px;
}
.exclude {
opacity: 0.5;
}
.object-exclude {
opacity: 0.5;
}
.sub-title {
font-size: 85%;
margin-bottom: 5px;
}
.el-form-item {
margin-bottom: 0;
}
.border-top {
border-top: 1px solid #d9d9d9; 
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
</style>

