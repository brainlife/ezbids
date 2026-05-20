<template>
    <div class="objects-page">
        <header class="objects-intro">
            <h2 class="objects-intro__title">Object Mapping</h2>
            <p class="objects-intro__text">
                Review and refine object-level mappings. Series-level settings are used as defaults, and you can
                override values here when specific objects need different labels or metadata.
            </p>
        </header>

        <splitpanes class="default-theme panes">
            <pane :size="30" :min-size="18" class="objects-pane objects-pane--list">
                <div ref="objectsList" class="objects-list">
                    <div v-for="o_sub in ezbids._organized" :key="o_sub.sub" class="subject-block">
                        <div v-if="o_sub.sub != ''" class="subject-row">
                            <div class="subject-row__label">
                                <i class="el-icon-user-solid" />
                                <small>sub-</small><b>{{ o_sub.sub }}</b>
                            </div>
                            <el-checkbox :value="o_sub.exclude" @change="excludeSubject(o_sub.sub.toString(), $event)">
                                <small>Exclude subject</small>
                            </el-checkbox>
                        </div>

                        <div v-for="o_ses in o_sub.sess" :key="o_ses.sess" class="session-block">
                            <div v-if="o_ses.sess" class="session-row">
                                <div class="session-row__label">
                                    <i class="el-icon-time" />
                                    <small>ses-</small><b>{{ o_ses.sess }}</b>
                                    <small class="session-row__date">{{ o_ses.AcquisitionDate }}</small>
                                </div>
                                <el-checkbox
                                    :value="o_ses.exclude"
                                    @change="excludeSession(o_sub.sub.toString(), o_ses.sess.toString(), $event)"
                                >
                                    <small>Exclude session</small>
                                </el-checkbox>
                            </div>

                            <div
                                v-for="(section, sectionId) in groupSections(o_ses)"
                                :key="sectionId"
                                class="section-block"
                            >
                                <div class="section-divider-wrap">
                                    <span class="section-divider">Group {{ sectionId }}</span>
                                </div>

                                <button
                                    v-for="o in section"
                                    :key="o.idx"
                                    type="button"
                                    class="object-list-item"
                                    :data-object-idx="o.idx"
                                    :class="{
                                        'object-list-item--active': so === o,
                                        'object-list-item--excluded': isExcluded(o),
                                    }"
                                    @click="select(o, o_ses)"
                                >
                                    <div class="object-list-item__main">
                                        <el-tag
                                            v-if="o.series_idx !== undefined"
                                            type="info"
                                            size="mini"
                                            :title="'Series#' + o.series_idx + ' ' + o._SeriesDescription"
                                        >
                                            #{{ o.series_idx }}
                                        </el-tag>
                                        <datatype :type="o._type" :series_idx="o.series_idx" :entities="o._entities" />
                                    </div>
                                    <small v-if="o._type == 'exclude'" class="object-list-item__desc">
                                        {{ o._SeriesDescription }}
                                    </small>

                                    <div class="object-list-item__badges">
                                        <el-badge
                                            v-if="o.validationErrors.length > 0"
                                            type="danger"
                                            :value="o.validationErrors.length"
                                        />
                                        <el-badge
                                            v-if="!isExcluded(o) && o.validationWarnings.length > 0"
                                            type="warning"
                                            :value="o.validationWarnings.length"
                                        />
                                        <el-badge
                                            v-if="
                                                !isExcluded(o) &&
                                                o._type != 'exclude' &&
                                                o.analysisResults &&
                                                o.analysisResults.errors &&
                                                o.analysisResults.errors.length > 0
                                            "
                                            type="warning"
                                            :value="o.analysisResults.errors.length"
                                        />
                                    </div>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </pane>

            <pane class="objects-pane objects-pane--main">
                <div v-if="!so" class="empty-state">
                    <div class="empty-state__card">
                        <p>Please make sure all subject/session/series mappings are correctly applied to your data.</p>
                        <p>
                            Please select an object from the left list to inspect and edit datatype, entities, and
                            related metadata.
                        </p>
                    </div>
                </div>

                <div v-if="so && sess" class="editor-panel">
                    <el-form class="editor-form">
                        <div class="panel-card">
                            <div>
                                <p style="white-space: nowrap">Series Description:</p>
                                <p style="word-break: break-all; color: var(--el-text-color-secondary, #909399)">
                                    {{ so._SeriesDescription }}
                                </p>
                            </div>
                            <el-form-item>
                                <el-checkbox v-model="so.exclude" @change="update(so)">Exclude this object</el-checkbox>
                            </el-form-item>
                            <div v-if="so.exclude === true" class="stack-alert-wrap">
                                <el-alert :closable="false" type="info"
                                    >This object will be excluded from the BIDS output</el-alert
                                >
                            </div>

                            <!--messagess-->
                            <div class="stack-alert-wrap">
                                <el-alert
                                    v-for="(error, idx) in so.validationErrors"
                                    :key="idx"
                                    show-icon
                                    :closable="false"
                                    type="error"
                                    :title="error"
                                    class="stack-alert"
                                />
                            </div>
                            <div class="stack-alert-wrap">
                                <el-alert
                                    v-for="(warning, idx) in so.validationWarnings"
                                    :key="idx"
                                    show-icon
                                    :closable="false"
                                    type="warning"
                                    :title="warning"
                                    class="stack-alert"
                                />
                            </div>
                            <div class="stack-alert-wrap">
                                <el-alert
                                    v-for="(error, idx) in so.analysisResults.errors"
                                    :key="idx"
                                    show-icon
                                    :closable="false"
                                    type="warning"
                                    :title="error"
                                    class="stack-alert"
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
                                    <el-option-group
                                        v-for="type in bidsSchema.datatypes"
                                        :key="type.label"
                                        :label="type.label"
                                    >
                                        <el-option
                                            v-for="subtype in type.options"
                                            :key="subtype.value"
                                            :value="subtype.value"
                                        >
                                            {{ type.label }} / {{ subtype.label }}
                                        </el-option>
                                    </el-option-group>
                                </el-select>
                            </el-form-item>

                            <div class="entity-grid">
                                <div v-for="(v, entity) in getBIDSEntities(so._type)" :key="entity" class="entity-row">
                                    <div class="entity-row__label">
                                        {{ bidsSchema.entities[entity].name }}{{ v == 'required' ? '- *' : '-' }}
                                    </div>
                                    <div class="entity-row__input">
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
                                                    @blur="update(so)"
                                                />
                                            </template>
                                        </el-popover>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div v-if="so._type.startsWith('fmap/') || so._type === 'perf/m0scan'" class="border-top">
                            <el-form-item label="IntendedFor" class="form-grid-item">
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
                            <p class="field-note">
                                * IntendedFor information is used to specify which image this fieldmap is intended for.
                                This is recommended information according to the BIDS specification.
                            </p>
                        </div>
                        <div
                            v-if="
                                so._type &&
                                !so._type.includes('exclude') &&
                                (!so._type.includes('events') ||
                                    ['perf/asl', 'perf/m0scan'].includes(so._type) ||
                                    so._type.startsWith('pet') ||
                                    so._type.startsWith('func') ||
                                    so._type.startsWith('fmap') ||
                                    so._type.startsWith('dwi') ||
                                    so._type.startsWith('anat') ||
                                    so._type.startsWith('meg'))
                            "
                            class="border-top"
                        >
                            <template
                                v-if="
                                    !so._type.includes('events') &&
                                    !so._type.startsWith('meg') &&
                                    !so._type.startsWith('pet')
                                "
                            >
                                <el-form-item label="B0FieldIdentifier" class="form-grid-item">
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
                                <p class="field-note">
                                    * <b>Recommended/Optional if no IntendedFor</b>: If this sequence will be used
                                    fieldmap correction, enter a text string of your choice. A good formatting
                                    suggestion is the "datatype_suffix[index]" format (e.g., <b>fmap_epi0</b>,
                                    <b>fmap_phasediff1</b>, etc). If another sequence will be used with this one for
                                    fieldmap correction, use the exact same text string there as well. Leave field if
                                    unclear.
                                </p>

                                <el-form-item label="B0FieldSource" class="form-grid-item">
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
                                <p class="field-note">
                                    * <b>Recommended/Optional if no IntendedFor</b>: If this sequence will be used
                                    fieldmap correction, enter a text string of your choice. A good formatting
                                    suggestion is the "datatype_suffix" format (e.g., fmap_epi, fmap_phasediff). If
                                    another sequence will be used with this one for fieldmap correction, use the same
                                    text string there as well. Leave field blank if unclear.
                                </p>
                            </template>

                            <el-form-item
                                v-if="
                                    ['perf/asl', 'perf/m0scan'].includes(so._type) ||
                                    so._type.startsWith('pet') ||
                                    so._type.startsWith('func') ||
                                    so._type.startsWith('fmap') ||
                                    so._type.startsWith('dwi') ||
                                    so._type.startsWith('anat') ||
                                    so._type.startsWith('meg')
                                "
                                class="form-grid-item"
                                label="Relevant Metadata"
                            >
                                <ModalityForm :ss="so" :ezbids="ezbids" @form-submitted="submitForm" />
                            </el-form-item>
                        </div>

                        <div v-if="so.items.length" class="border-top">
                            <div v-for="(item, idx) in so.items" :key="idx" class="item-block">
                                <el-form-item :label="item.name || 'noname'" class="form-grid-item">
                                    <el-select
                                        v-model="item.path"
                                        placeholder="Source path"
                                        size="small"
                                        style="width: 100%"
                                    >
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
                                <el-form-item v-if="item.sidecar" label="sidecar" class="form-grid-item">
                                    <el-input
                                        v-model="item.sidecar_json"
                                        type="textarea"
                                        rows="10"
                                        @blur="update(so)"
                                    />
                                </el-form-item>
                                <el-form-item
                                    v-if="item.headers"
                                    label="Nifti Headers (read-only)"
                                    class="form-grid-item"
                                >
                                    <pre class="headers">{{ item.headers }}</pre>
                                </el-form-item>
                                <el-form-item v-if="item.eventsBIDS" label="eventsBIDS" class="form-grid-item">
                                    <el-table :data="item.eventsBIDS" size="mini" border style="width: 100%">
                                        <el-table-column prop="onset" label="onset" />
                                        <el-table-column prop="duration" label="duration" />
                                        <el-table-column
                                            v-if="item.eventsBIDS[0].sample"
                                            prop="sample"
                                            label="sample"
                                        />
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
                            </div>
                        </div>

                        <div v-if="so.analysisResults.filesize" class="analysis-summary">
                            <p style="font-size: 90%">
                                Volumes: <b>{{ so.analysisResults.NumVolumes }}</b> &nbsp;&nbsp; Orientation:
                                <b>{{ so.analysisResults.orientation }}</b> &nbsp;&nbsp; File Size:
                                <b>{{ prettyBytes(so.analysisResults.filesize) }}</b>
                            </p>
                            <div v-for="(item, itemIdx) in ezbids.objects[so.idx].items" :key="itemIdx">
                                <div v-if="item.pngPaths">
                                    <div v-for="(path, idx) in item.pngPaths" :key="idx">
                                        <pre class="png-path">{{ path }}</pre>
                                        <AsyncImageLink :path="path" />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </el-form>

                    <el-collapse>
                        <el-collapse-item title="Debug">
                            <pre v-if="config.debug" class="debug-pre">{{ so }}</pre>
                        </el-collapse-item>
                    </el-collapse>
                </div>
            </pane>
        </splitpanes>
    </div>
</template>

<script lang="ts">
import { mapState, mapGetters } from 'vuex';
import { defineComponent } from 'vue';
import datatype from '@/components/datatype.vue';
import ModalityForm from '@/components/modalityForm.vue';

import anatYaml from '@/assets/schema/rules/sidecars/anat.yaml';
import funcYaml from '@/assets/schema/rules/sidecars/func.yaml';
import fmapYaml from '@/assets/schema/rules/sidecars/fmap.yaml';
import dwiYaml from '@/assets/schema/rules/sidecars/dwi.yaml';
import aslYaml from '@/assets/schema/rules/sidecars/asl.yaml';
import petYaml from '@/assets/schema/rules/sidecars/pet.yaml';
import megYaml from '@/assets/schema/rules/sidecars/meg.yaml';
import metadataInfo from '@/assets/schema/rules/sidecars/metadata.yaml';

import { prettyBytes } from '@/filters';
import {
    setRun,
    setIntendedFor,
    alignEntities,
    validateEntities,
    validate_B0FieldIdentifier_B0FieldSource,
    fileLogicLink,
    dwiQA,
    petQA,
    updateErrorMessages,
} from '@/libUnsafe';

import AsyncImageLink from '@/components/AsyncImageLink.vue';

// @ts-ignore
import { Splitpanes, Pane } from 'splitpanes';

import 'splitpanes/dist/splitpanes.css';
import { IObject, OrganizedSession, OrganizedSubject, Session } from '@/store/store.types';

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
            this.scrollSelectedObjectIntoView();
        },
        scrollSelectedObjectIntoView(behavior: ScrollBehavior = 'smooth') {
            if (!this.so) return;
            this.$nextTick(() => {
                const list = this.$refs.objectsList as HTMLElement | undefined;
                if (!list) return;
                const target = list.querySelector(
                    `.object-list-item[data-object-idx="${this.so?.idx}"]`
                ) as HTMLElement | null;
                if (!target) return;

                // Scroll the left list container directly for reliable behavior.
                const offsetTop = target.offsetTop;
                const centeredTop = Math.max(0, offsetTop - list.clientHeight / 2 + target.clientHeight / 2);
                list.scrollTo({ top: centeredTop, behavior });
            });
        },
        update(o: IObject | null) {
            if (!o) return;
            this.$emit('updateObject', o);
            this.scrollSelectedObjectIntoView('smooth');
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
                //Ensure other fmap series aren't included in the IntendedFor mapping
                if ((o.IntendedFor ?? []).length > 0) {
                    (o.IntendedFor ?? []).forEach((i) => {
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
            alignEntities(this.ezbids);
            dwiQA(this.ezbids);
            petQA(this.ezbids);
            setRun(this.ezbids);
            this.ezbids.objects.forEach(this.validate);
            setIntendedFor(this.ezbids); // keep this last, otherwise IntendedFor in Dataset Review can be messed up
            updateErrorMessages(this.ezbids);
        },

        submitForm(data: any) {
            //TODO: should we make an interface for data in store/index.ts?
            this.ezbids = data;
        },
    },
});
</script>

<style lang="scss" scoped>
.splitpanes.default-theme .splitpanes__pane {
    background-color: inherit;
}

.objects-page {
    max-width: 1600px;
    margin: 0 auto;
    padding: 0.5rem 1.25rem 2.75rem;
}

.objects-intro {
    margin-bottom: 1.25rem;
    padding: 1.35rem 1.5rem 1.5rem;
    border-radius: 10px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-fill-color-blank, #fff);
    box-shadow: 0 1px 2px rgb(0 0 0 / 4%);
}

.objects-intro__title {
    margin: 0 0 0.55rem;
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--el-text-color-primary, #303133);
}

.objects-intro__text {
    margin: 0;
    font-size: 14px;
    line-height: 1.6;
    color: var(--el-text-color-regular, #606266);
}

.panes {
    width: 100%;
    max-width: 100%;
    min-height: calc(100vh - 220px);
}

.objects-pane {
    min-height: 0;
    display: flex;
    flex-direction: column;
}

.objects-pane--list {
    border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
    padding-right: 8px;
}

.objects-list {
    overflow-y: auto;
    max-height: 75vh;
    padding-right: 4px;
}

.subject-block {
    margin-bottom: 12px;
}

.subject-row,
.session-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;
}

.subject-row__label,
.session-row__label {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
}

.session-row {
    margin-left: 10px;
    padding-left: 8px;
    border-left: 2px solid #3331;
}

.session-row__date {
    opacity: 0.65;
}

.section-block {
    margin-left: 12px;
}

.section-divider-wrap {
    border-top: 1px dotted #bbb;
    margin: 8px 0;
    position: relative;
}

.object-list-item {
    width: 100%;
    text-align: left;
    border: 1px solid transparent;
    background: transparent;
    border-radius: 6px;
    padding: 7px 8px;
    margin-bottom: 4px;
    cursor: pointer;
    color: inherit;
    transition:
        background-color 0.2s ease,
        border-color 0.2s ease;
}

.object-list-item:hover {
    background: var(--el-fill-color-light, #f5f7fa);
}

.object-list-item--active {
    background: var(--el-color-primary-light-9, #ecf5ff);
    border-color: var(--el-color-primary-light-7, #b3d8ff);
}

.object-list-item--excluded {
    opacity: 0.55;
}

.object-list-item__main {
    display: flex;
    align-items: center;
    gap: 6px;
}

.object-list-item__desc {
    display: block;
    margin-top: 4px;
    color: var(--el-text-color-secondary, #909399);
}

.object-list-item__badges {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 5px;
}

.objects-pane--main {
    padding-left: 12px;
}

.empty-state {
    padding: 12px 0;
}

.empty-state__card {
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    border-radius: 8px;
    background: var(--el-bg-color, #fff);
    padding: 16px;
    color: var(--el-text-color-regular, #606266);
}

.editor-panel {
    overflow-y: auto;
    max-height: 75vh;
    padding-right: 8px;
}

.editor-form {
    padding-bottom: 10px;
    padding: 1rem;
}

.panel-card {
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    border-radius: 8px;
    background: var(--el-bg-color, #fff);
    padding: 14px;
    margin-bottom: 10px;
}

.stack-alert-wrap {
    margin-bottom: 5px;
}

.stack-alert {
    margin-bottom: 4px;
}

.entity-grid {
    width: 100%;
    margin: 6px 0 2px;
}

.entity-row {
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
}

.entity-row__label {
    font-size: 13px;
    color: var(--el-text-color-regular, #606266);
    text-align: right;
    line-height: 1.2;
}

.entity-row__input {
    min-width: 0;
}

.field-note {
    margin-left: 200px;
    margin-top: 4px;
    font-size: 12px;
}

.editor-form :deep(.el-form-item__label) {
    float: none;
    text-align: right;
    line-height: 32px;
    padding: 0;
}

.form-grid-item :deep(.el-form-item__label) {
    width: 180px;
}

.editor-form :deep(.el-form-item__content) {
    min-width: 0;
}

.border-top {
    border-top: 1px solid #f6f6f6;
    padding-top: 2px;
    margin-top: 2px;
}

.item-block + .item-block {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #f6f6f6;
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

.analysis-summary {
    margin-top: 5px;
    padding: 2rem;
    border-radius: 6px;
    background-color: #f5f7fa;
}

.png-path {
    margin-top: 1rem;
    margin-bottom: 0.5rem;
    max-width: 100%;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-all;
}

.debug-pre {
    margin-top: 10px;
    max-height: 65vh;
    overflow: auto;
    background-color: #666;
    color: #fff;
    padding: 10px;
    border-radius: 6px;
}

.el-form-item {
    margin-bottom: 0;
    display: flex;
    gap: 1rem;
    flex: 1 1 auto;
}

.section-divider {
    position: absolute;
    right: 10px;
    top: -8px;
    background-color: white;
    color: #999;
    padding: 0 10px;
    font-size: 12px;
}
</style>
