<template>
    <splitpanes class="objectpage default-theme">
        <pane min-size="20" size="30" class="bids-structure">
            <div v-for="o_sub in ezbids._organized" :key="o_sub.sub" style="font-size: 90%; margin-bottom: 10px">
                <span v-if="o_sub.sub != ''" class="hierarchy">
                    <i class="el-icon-user-solid" style="margin-right: 2px" />
                    <small>sub-</small><b>{{ o_sub.sub }}</b>
                    &nbsp;
                    <el-checkbox :value="o_sub.exclude" @change="excludeSubject(o_sub.sub.toString(), $event)">
                        <small>Exclude this subject</small>
                    </el-checkbox>
                </span>
                <div v-for="o_ses in o_sub.sess" :key="o_ses.sess" :class="{ 'left-border': o_ses.sess != '' }">
                    <span v-if="o_ses.sess" class="hierarchy">
                        <i class="el-icon-time" style="margin-right: 2px" />
                        <small>ses-</small><b>{{ o_ses.sess }}</b>
                        &nbsp;
                        <small style="opacity: 0.5">{{ o_ses.AcquisitionDate }}</small>
                        &nbsp; &nbsp;
                        <el-checkbox
                            :value="o_ses.exclude"
                            @change="excludeSession(o_sub.sub.toString(), o_ses.sess.toString(), $event)"
                        >
                            <small>Exclude this session</small>
                        </el-checkbox>
                    </span>
                    <div
                        v-for="(section, sectionId) in groupSections(o_ses)"
                        :key="sectionId"
                        style="position: relative"
                    >
                        <div v-if="section.length > 1" style="border-top: 1px dotted #bbb; width: 100%; margin: 9px 0">
                            <span class="section-divider">section {{ sectionId }}</span>
                        </div>
                        <div
                            v-for="o in section"
                            :key="o.idx"
                            class="clickable hierarchy-item"
                            :class="{ selected: so === o, excluded: isExcluded(o) }"
                            @click="select(o, o_ses)"
                        >
                            <el-tag
                                v-if="o.series_idx !== undefined"
                                type="info"
                                size="mini"
                                :title="'Series#' + o.series_idx + ' ' + o._SeriesDescription"
                                >#{{ o.series_idx }}</el-tag
                            >&nbsp;
                            <datatype :type="o._type" :series_idx="o.series_idx" :entities="o._entities" />
                            <small v-if="o._type == 'exclude'">&nbsp;({{ o._SeriesDescription }})</small>

                            <span v-if="!isExcluded(o)">
                                <!--show validation error(s) as "error"-->
                                <el-badge
                                    v-if="o.validationErrors.length > 0"
                                    type="danger"
                                    :value="o.validationErrors.length"
                                    style="margin-left: 5px"
                                />

                                <!--show validation warning(s) as "warning"-->
                                <el-badge
                                    v-if="o.validationWarnings.length > 0"
                                    type="warning"
                                    :value="o.validationWarnings.length"
                                    style="margin-left: 5px"
                                />

                                <!-- show "QC errors" as warnings-->
                                <el-badge
                                    v-if="
                                        o._type != 'exclude' &&
                                        o.analysisResults &&
                                        o.analysisResults.errors &&
                                        o.analysisResults.errors.length > 0
                                    "
                                    type="warning"
                                    :value="o.analysisResults.errors.length"
                                    style="margin-left: 5px"
                                />
                            </span>
                            <span v-if="isExcluded(o)">
                                <!--show validation error(s) as "error"-->
                                <el-badge
                                    v-if="o.validationErrors.length > 0"
                                    type="danger"
                                    :value="o.validationErrors.length"
                                    style="margin-left: 5px"
                                />
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <br />
            <br />
            <br />
            <br />
        </pane>

        <pane class="object-detail">
            <div v-if="!so" style="padding: 20px">
                <div class="hint">
                    <p>Please make sure all subject/session/series mappings are correctly applied to your data.</p>
                    <p>
                        By default, entities specified in the <b>Series</b> page will be used as defaults for all
                        objects. On this page you can override those entities.
                    </p>
                    <div style="background-color: white; padding: 10px; color: #666">
                        <i class="el-icon-back" /> Please select an object to view/edit in the BIDS Structure list
                    </div>
                </div>
            </div>

            <div v-if="so && sess">
                <el-form label-width="200px">
                    <el-form-item>
                        <el-checkbox v-model="so.exclude" @change="update(so)">Exclude this object</el-checkbox>
                    </el-form-item>
                    <div v-if="isExcluded(so)" style="margin-bottom: 5px">
                        <el-alert :closable="false" type="info"
                            >This object will be excluded from the BIDS output</el-alert
                        >
                    </div>
                    <el-form-item v-if="so.series_idx" label="Series Desc">
                        {{ so._SeriesDescription }}
                    </el-form-item>

                    <!--messagess-->
                    <div style="margin-bottom: 5px">
                        <el-alert
                            v-for="(error, idx) in so.validationErrors"
                            :key="idx"
                            show-icon
                            :closable="false"
                            type="error"
                            :title="error"
                            style="margin-bottom: 4px"
                        />
                    </div>
                    <div style="margin-bottom: 5px">
                        <el-alert
                            v-for="(warning, idx) in so.validationWarnings"
                            :key="idx"
                            show-icon
                            :closable="false"
                            type="warning"
                            :title="warning"
                            style="margin-bottom: 4px"
                        />
                    </div>
                    <div style="margin-bottom: 5px">
                        <el-alert
                            v-for="(error, idx) in so.analysisResults.errors"
                            :key="idx"
                            show-icon
                            :closable="false"
                            type="warning"
                            :title="error"
                        />
                    </div>

                    <el-form-item label="Datatype/Suffix">
                        <el-select
                            v-model="so.type"
                            clearable
                            :placeholder="so._type"
                            size="small"
                            style="width: 100%"
                            @change="update(so)"
                        >
                            <el-option value="">(Use Series Default)</el-option>
                            <el-option-group v-for="type in bidsSchema.datatypes" :key="type.label" :label="type.label">
                                <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                    {{ type.label }} / {{ subtype.label }}
                                </el-option>
                            </el-option-group>
                        </el-select>
                    </el-form-item>

                    <div style="width: 350px">
                        <el-form-item
                            v-for="(v, entity) in getBIDSEntities(so._type)"
                            :key="entity"
                            :label="bidsSchema.entities[entity].name + (v == 'required' ? '- *' : '-')"
                        >
                            <el-popover
                                :width="300"
                                trigger="focus"
                                placement="left-start"
                                :title="bidsSchema.entities[entity].name"
                                :content="bidsSchema.entities[entity].description"
                            >
                                <template #reference>
                                    <el-input
                                        v-model="so.entities[entity]"
                                        size="small"
                                        :placeholder="getDefault(so, entity.toString())"
                                        style="width: 200px"
                                        @blur="update(so)"
                                    />
                                </template>
                            </el-popover>
                        </el-form-item>
                    </div>

                    <div v-if="so._type.startsWith('fmap/') || so._type === 'perf/m0scan'" class="border-top">
                        <br />
                        <el-form-item label="IntendedFor">
                            <el-select
                                v-model="so.IntendedFor"
                                multiple
                                placeholder="Select Object"
                                style="width: 100%"
                                @change="update(so)"
                            >
                                <el-option
                                    v-for="o in sess.objects.filter((o) => !isExcluded(o))"
                                    :key="o.idx"
                                    :label="intendedForLabel(o)"
                                    :value="o.idx"
                                >
                                </el-option>
                            </el-select>
                        </el-form-item>
                        <p style="margin-left: 200px">
                            <small
                                >* IntendedFor information is used to specify which image this fieldmap is intended for.
                                This is recommended information according to the BIDS specification.</small
                            >
                        </p>
                    </div>
                    <div v-if="so._type && !so._type.includes('exclude')" class="border-top">
                        <br />
                        <div v-if="!so._type.includes('events')" class="border-top">
                            <el-form-item label="B0FieldIdentifier">
                                <el-select
                                    v-model="so.B0FieldIdentifier"
                                    multiple
                                    filterable
                                    allow-create
                                    default-first-option
                                    placeholder="Enter text string"
                                    size="small"
                                    style="width: 100%"
                                    @change="update(so)"
                                >
                                </el-select>
                            </el-form-item>
                            <p style="margin-left: 200px">
                                <small
                                    >* <b>Recommended/Optional if no IntendedFor</b>: If this sequence will be used for
                                    fieldmap correction, enter a text string of your choice. A good formatting
                                    suggestion is the "datatype_suffix[index]" format (e.g., <b>fmap_epi0</b>,
                                    <b>fmap_phasediff1</b>, etc). If another sequence will be used with this one for
                                    fieldmap correction, use the exact same text string there as well. Leave field blank
                                    if unclear.</small
                                >
                            </p>
                        </div>

                        <br />
                        <div v-if="!so._type.includes('events')" class="border-top">
                            <el-form-item label="B0FieldSource">
                                <el-select
                                    v-model="so.B0FieldSource"
                                    multiple
                                    filterable
                                    allow-create
                                    default-first-option
                                    placeholder="Enter text string"
                                    size="small"
                                    style="width: 100%"
                                    @change="update(so)"
                                >
                                </el-select>
                            </el-form-item>
                            <p style="margin-left: 200px">
                                <small
                                    >* <b>Recommended/Optional if no IntendedFor</b>: If this sequence will be used for
                                    fieldmap correction, enter a text string of your choice. A good formatting
                                    suggestion is the "datatype_suffix" format (e.g., fmap_epi, fmap_phasediff). If
                                    another sequence will be used with this one for fieldmap correction, use the exact
                                    same text string there as well. Leave field blank if unclear.</small
                                >
                            </p>
                            <el-form-item
                                v-if="
                                    ['perf/asl', 'perf/m0scan'].includes(so._type) ||
                                    so._type.startsWith('pet') ||
                                    so._type.startsWith('func') ||
                                    so._type.startsWith('fmap') ||
                                    so._type.startsWith('dwi') ||
                                    so._type.startsWith('anat')
                                "
                                label="Relevant Metadata"
                            >
                                <ModalityForm :ss="so" :ezbids="ezbids" @form-submitted="submitForm" />
                            </el-form-item>
                        </div>
                    </div>

                    <div v-for="(item, idx) in so.items" :key="idx" class="border-top">
                        <el-form-item :label="item.name || 'noname'">
                            <el-select v-model="item.path" placeholder="Source path" size="small" style="width: 100%">
                                <el-option
                                    v-for="(optItem, optIdx) in so.items"
                                    :key="optIdx"
                                    :label="optItem.path"
                                    :value="optItem.path"
                                />
                            </el-select>
                            <el-button
                                v-if="item.path?.endsWith('.nii.gz')"
                                size="small"
                                type="info"
                                @click="$emit('niivue', item.path)"
                            >
                                <font-awesome-icon :icon="['fas', 'eye']" />
                                NiiVue
                            </el-button>
                        </el-form-item>
                        <el-form-item v-if="item.sidecar" label="sidecar">
                            <el-input v-model="item.sidecar_json" type="textarea" rows="10" @blur="update(so)" />
                        </el-form-item>
                        <el-form-item v-if="item.headers" label="Nifti Headers (read-only)">
                            <pre class="headers">{{ item.headers }}</pre>
                        </el-form-item>
                        <el-form-item v-if="item.eventsBIDS" label="eventsBIDS">
                            <el-table :data="item.eventsBIDS" size="mini" border style="width: 100%">
                                <el-table-column prop="onset" label="onset" />
                                <el-table-column prop="duration" label="duration" />
                                <el-table-column v-if="item.eventsBIDS[0].sample" prop="sample" label="sample" />
                                <el-table-column
                                    v-if="item.eventsBIDS[0].trial_type"
                                    prop="trial_type"
                                    label="trial_type"
                                />
                                <el-table-column
                                    v-if="item.eventsBIDS[0].response_time"
                                    prop="response_time"
                                    label="response_time"
                                />
                                <el-table-column v-if="item.eventsBIDS[0].value" prop="value" label="value" />
                                <el-table-column v-if="item.eventsBIDS[0].HED" prop="HED" label="HED" />
                                <el-table-column
                                    v-if="item.eventsBIDS[0].stim_file"
                                    prop="stim_file"
                                    label="stim_file"
                                />
                            </el-table>
                        </el-form-item>
                        <br />
                    </div>

                    <div
                        v-if="so.analysisResults.filesize"
                        style="margin-top: 5px; padding: 5px; background-color: #f0f0f0"
                    >
                        <p style="font-size: 90%">
                            Volumes: <b>{{ so.analysisResults.NumVolumes }}</b> &nbsp;&nbsp; Orientation:
                            <b>{{ so.analysisResults.orientation }}</b> &nbsp;&nbsp; File Size:
                            <b>{{ prettyBytes(so.analysisResults.filesize) }}</b>
                        </p>
                        <div v-for="(item, itemIdx) in ezbids.objects[so.idx].items" :key="itemIdx">
                            <div v-if="item.pngPaths">
                                <div v-for="(path, idx) in item.pngPaths" :key="idx">
                                    <pre style="margin-bottom: 0">{{ path }}</pre>
                                    <AsyncImageLink :path="path" />
                                </div>
                            </div>
                        </div>
                    </div>
                </el-form>

                <pre v-if="config.debug">{{ so }}</pre>
            </div>
            <!--selected != null-->
            <br />
            <br />
            <br /> </pane
        ><!--object-->
    </splitpanes>
</template>

<script lang="ts">
import { mapState, mapGetters } from 'vuex';
import { defineComponent } from 'vue';
import datatype from './components/datatype.vue';
import ModalityForm from './components/modalityForm.vue';

import anatYaml from '../src/assets/schema/rules/sidecars/anat.yaml';
import funcYaml from '../src/assets/schema/rules/sidecars/func.yaml';
import fmapYaml from '../src/assets/schema/rules/sidecars/fmap.yaml';
import dwiYaml from '../src/assets/schema/rules/sidecars/dwi.yaml';
import aslYaml from '../src/assets/schema/rules/sidecars/asl.yaml';
import petYaml from '../src/assets/schema/rules/sidecars/pet.yaml';
import megYaml from '../src/assets/schema/rules/sidecars/meg.yaml';
import metadataInfo from '../src/assets/schema/rules/sidecars/metadata.yaml';

import { IObject, Session, OrganizedSession, OrganizedSubject } from './store';
import { prettyBytes } from './filters';
import {
    setRun,
    setIntendedFor,
    alignEntities,
    validateEntities,
    validate_B0FieldIdentifier_B0FieldSource,
    fileLogicLink,
    dwiQA,
    petQA,
} from './libUnsafe';

import AsyncImageLink from './components/AsyncImageLink.vue';

// @ts-ignore
import { Splitpanes, Pane } from 'splitpanes';

import 'splitpanes/dist/splitpanes.css';

interface Section {
    [key: string]: IObject[];
}

export default defineComponent({
    components: {
        datatype,
        Splitpanes,
        Pane,
        AsyncImageLink,
    },
    emits: ['niivue', 'mapObjects', 'updateObject'],

    data() {
        return {
            so: null as IObject | null, //selected object
            sess: null as OrganizedSession | null, //selected session for IntendedFor handling
            showInfo: {} as any,
            petYaml: petYaml,
            aslYaml: aslYaml,
            fields: {},
            showDialog: false,
            rules: {},
            formData: {},
        };
    },

    computed: {
        ...mapState(['ezbids', 'config', 'bidsSchema', 'events']),
        ...mapGetters(['getBIDSEntities', 'findSubject', 'findSession', 'findSubjectFromString']),

        totalIssues() {
            let count = 0;
            this.ezbids.objects.forEach((o: IObject) => {
                if (this.isExcluded(o)) return;
                count += o.validationErrors.length;
            });
            return count;
        },
    },
    mounted() {
        this.validateAll();
    },

    methods: {
        prettyBytes,

        getSomeEntities(type: string): any {
            const entities = Object.assign({}, this.getBIDSEntities(type));
            delete entities.subject;
            delete entities.session;
            return entities;
        },

        //subject needs to be an object
        findSessionFromString(sub: string, ses: string) {
            const subject = this.findSubjectFromString(sub);
            return subject.sessions.find((s: Session) => s.session == ses);
        },

        excludeSubject(sub: string, b: boolean) {
            if (this.findSubjectFromString(sub) !== undefined) {
                const subject = this.findSubjectFromString(sub);
                subject.exclude = b;
            } else {
                const o_subs = this.ezbids._organized.filter((e: OrganizedSubject) => e.sub == sub);
                o_subs.forEach((o_sub: OrganizedSubject) => {
                    o_sub.sess.forEach((ses) => {
                        ses.objects.forEach((obj) => {
                            obj.exclude = b;
                        });
                    });
                });
            }

            this.$emit('mapObjects');
            this.validateAll();
        },

        isExcluded(o: IObject) {
            if (o.exclude) {
                return true;
            } else if (o._exclude) {
                return true;
            } else if (o._type === 'exclude') {
                return true;
            } else {
                return false;
            }
        },

        excludeSession(sub: string, ses: string, b: boolean) {
            if (this.findSubjectFromString(sub) !== undefined && this.findSessionFromString(sub, ses) !== undefined) {
                const session = this.findSessionFromString(sub, ses);
                if (session) session.exclude = b;
            } else {
                const o_subs = this.ezbids._organized.filter((e: OrganizedSubject) => e.sub == sub);
                o_subs.forEach((o_sub: OrganizedSubject) => {
                    const o_ses = o_sub.sess.filter((s) => s.sess == ses);
                    o_ses.forEach((ses) => {
                        ses.objects.forEach((obj) => {
                            obj.exclude = b;
                        });
                    });
                });
            }

            this.$emit('mapObjects');
            this.validateAll();
        },

        groupSections(sess: OrganizedSession) {
            let sections = {} as Section;
            sess.objects.forEach((o) => {
                let sectionId = o.analysisResults.section_id;
                if (!sections[sectionId]) sections[sectionId] = [];
                sections[sectionId].push(o);
            });
            return sections;
        },

        select(o: IObject, sess: OrganizedSession) {
            this.sess = sess; //for IntendedFor
            this.so = o;
            window.scrollTo(0, 0);
        },

        update(o: IObject | null) {
            if (!o) return;
            this.$emit('updateObject', o);
        },

        isValid(cb: (err?: string) => void) {
            this.$emit('mapObjects');
            this.validateAll();

            let err = undefined;
            this.ezbids.objects.forEach((o: IObject) => {
                if (o.validationErrors.length > 0) err = 'Please correct all issues.';
            });

            //make sure there is at least 1 object to output
            let one = this.ezbids.objects.find((o: IObject) => !o._exclude);
            if (!one) {
                err = 'All objects are excluded. Please update so that there is at least 1 object to output to BIDS';
            }

            return cb(err);
        },

        getDefault(o: IObject, entity: string): string {
            if (entity == 'subject') {
                //default subject name only comes from subject
                const subject = this.findSubject(o);
                return subject.subject;
            } else if (entity == 'session') {
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
                if (!objects) return ''; //no object. no default..
                return objects._entities[entity];
            }
        },

        intendedForLabel(o: IObject) {
            const series = this.ezbids.series[o.series_idx];
            if (!series) return 'no-series';
            // if(!series && o._type != "func/events") return "no-series";
            let l = '#' + series.series_idx + ' ';
            l += o._type;
            for (let k in o._entities) {
                if (k == 'subject' || k == 'session') continue;
                if (!o._entities[k]) continue;
                l += ' ' + k + '-' + o._entities[k];
            }
            return l;
        },

        validate(o: IObject | null) {
            if (!o) return;

            o.validationErrors = [];
            o.validationWarnings = [];

            // setIntendedFor(this.ezbids)

            // alignEntities(this.ezbids)

            validateEntities('Objects', o);

            // dwiQA(this.ezbids)

            validate_B0FieldIdentifier_B0FieldSource(o);

            // setRun(this.ezbids)

            fileLogicLink(this.ezbids, o);

            //update validationWarnings
            if (o.analysisResults.warnings?.length) {
                o.validationWarnings = o.analysisResults.warnings;
            }

            let entities_requirement = this.getBIDSEntities(o._type);
            for (let k in this.getSomeEntities(o._type)) {
                if (entities_requirement[k] === 'required') {
                    if (!o._entities[k]) {
                        o.validationErrors.push('entity: ' + k + ' is required.');
                    }
                }
            }

            /*
                If user specified a specific entity label and then changed the datatype/suffix pairing to something
                that doesn't allow that entity, we need to remove it. Otherwise, the bids-validator will complain.
                */
            for (let k in o._entities) {
                if (!['subject', 'session'].includes(k)) {
                    // this line prevents sequence ordering from being messed up
                    if (o.entities[k] !== '' && !entities_requirement[k]) {
                        o._entities[k] = '';
                        o.entities[k] = '';
                    }
                }
            }

            if (o._type.startsWith('func/')) {
                const series = this.ezbids.series[o.series_idx];
                if (entities_requirement['task'] && !o.entities.task && !series?.entities.task) {
                    o.validationErrors.push(
                        'task entity label is required for func/bold but not set on Series Mapping page, nor overridden.'
                    );
                }
            }

            if (o._type.startsWith('fmap/') || o._type === 'perf/m0scan') {
                if (!o.IntendedFor) o.IntendedFor = [];
                if (o.IntendedFor.length == 0) {
                    if (o._type.startsWith('fmap/')) {
                        o.validationWarnings.push(
                            'It is recommended that field map (fmap) images have IntendedFor set to at least 1 series ID. This is necessary if you plan on using processing BIDS-apps such as fMRIPrep'
                        );
                    } else if (o.type === 'perf/m0scan') {
                        o.validationErrors.push(
                            'It is required that perfusion m0scan images have IntendedFor set to at least 1 series ID.'
                        );
                    }
                    // let warningMessage = "It is recommended that these images have IntendedFor set to at least 1 object. This is necessary if you plan on using processing BIDS-apps such as fMRIPrep"
                    // if (!o.validationWarnings.includes(warningMessage)) {
                    //     o.validationWarnings.push(warningMessage);
                    // }
                }
                //Ensure other fmap series aren't included in the IntendedFor mapping
                if (o.IntendedFor.length > 0) {
                    o.IntendedFor.forEach((i) => {
                        let series_idx = this.ezbids.objects[i].series_idx;
                        if (this.ezbids.objects[i]._type.startsWith('fmap/')) {
                            o.validationErrors.push(
                                'The selected series (#' +
                                    series_idx +
                                    ") appears to be a field map (fmap), \
                                which isn't allowed in the IntendedFor mapping. Please remove this series, or, if it \
                                isn't a field map, please correct it."
                            );
                        }
                    });
                }
            }

            //try parsing items
            o.items.forEach((item) => {
                if (item.sidecar) {
                    try {
                        item.sidecar = JSON.parse(item.sidecar_json);
                    } catch (err) {
                        console.error(err);
                        o.validationErrors.push('Failed to parse sidecar_json. Please check the syntax');
                    }
                }
            });

            if (this.isExcluded(o)) return;

            // NOTE: don't need this section if setRun() functionality is in place, prevents conflicts

            // //make sure no 2 objects are exactly alike
            // for(let o2 of this.ezbids.objects) {
            //     if(o.idx == o2.idx) continue;
            //     if(this.isExcluded(o2)) continue;
            //     if(o._type != o2._type) continue;

            //     let same = o2;
            //     for(let k in o._entities) {
            //         if(o._entities[k] != o2._entities[k]) {
            //             same = undefined;
            //             break;
            //         }
            //     }
            //     if(same) {
            //         const sameseries = this.ezbids.series[same.series_idx];
            //         let sameidx = undefined;
            //         if(sameseries) sameidx = sameseries.series_idx;
            //         o.validationErrors.push("This object looks exactly like another object with Series #"+sameidx+
            //             ". We can not convert this object to BIDS as they will overwrite each other. "+
            //             "Please set entities such as 'run' to make them all unique (across subjects/sessions).");
            //         break;
            //     }
            // }
        },

        validateAll() {
            setIntendedFor(this.ezbids);
            alignEntities(this.ezbids);
            dwiQA(this.ezbids);
            petQA(this.ezbids);
            setRun(this.ezbids);
            this.ezbids.objects.forEach(this.validate);
        },

        submitForm(data: any) {
            //TODO: should we make an interface for data in store/index.ts?
            this.ezbids = data;
        },
    },
});
</script>

<style lang="scss" scoped>
.objectpage {
    position: fixed;
    top: 0;
    bottom: 60px;
    left: 160px;
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
