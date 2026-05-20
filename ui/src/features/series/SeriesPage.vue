<template>
    <div class="series-page">
        <header class="series-intro">
            <h2 class="series-intro__title">Series Mapping</h2>
            <p class="series-intro__text">
                Please update (if necessary) how you'd like to map each dicom SeriesDescription to BIDS datatype,
                suffix, entities.
                <br />The information you specify here will be applied to all subjects that uses matching
                SeriesDescription. You can also override this information later for each subject.
            </p>
            <el-checkbox v-model="ezbids.BIDSURI" @change="BIDSURI(ezbids, $event)">
                <small>Use BIDS URI format for IntendedFor metadata mapping (if applicable)</small>
            </el-checkbox>
            <p class="series-intro__text">Click on a series in the left panel to view/edit.</p>
        </header>

        <div class="series-workspace">
            <aside class="series-list-panel">
                <div class="series-list">
                    <button
                        v-for="(s, series_idx) in ezbids.series"
                        :key="series_idx"
                        type="button"
                        class="series-list__item"
                        :class="{
                            'series-list__item--active': ss === s,
                            'series-list__item--excluded': s.type == 'exclude',
                        }"
                        @click="ss = s"
                    >
                        <div class="series-list__top">
                            <div class="series-list__tags">
                                <el-tag type="info" size="mini">#{{ series_idx }}</el-tag>
                                <el-tag type="info" effect="plain" size="mini">
                                    {{ getObjectsFromSeries(s).length }} objs
                                </el-tag>
                                <datatype :type="s.type" :series_idx="series_idx" :entities="s.entities" />
                            </div>
                        </div>
                        <el-tooltip :content="seriesListLabel(s)" placement="top" :show-after="400">
                            <div class="series-list__desc">{{ seriesListLabel(s) }}</div>
                        </el-tooltip>
                        <span v-if="seriesListExtension(s)" class="series-list__ext">{{ seriesListExtension(s) }}</span>
                        <div
                            v-if="s.validationErrors.length > 0 || s.validationWarnings.length > 0"
                            class="series-list__validation"
                        >
                            <el-tag v-if="s.validationErrors.length > 0" type="danger" size="mini" effect="plain">
                                {{ s.validationErrors.length }}
                                {{ s.validationErrors.length === 1 ? 'error' : 'errors' }}
                            </el-tag>
                            <el-tag v-if="s.validationWarnings.length > 0" type="warning" size="mini" effect="plain">
                                {{ s.validationWarnings.length }}
                                {{ s.validationWarnings.length === 1 ? 'warning' : 'warnings' }}
                            </el-tag>
                        </div>
                    </button>
                </div>
            </aside>

            <main class="series-detail-panel">
                <div class="series-detail-scroll">
                    <div v-if="!ss" class="empty-state">
                        <div class="empty-state__card">
                            <p class="empty-state__message">Select a series on the left</p>
                        </div>
                    </div>
                    <template v-else>
                        <div class="series-main">
                            <div class="panel-card">
                                <h5 class="section-title">BIDS Datatype, Suffix, Entities</h5>
                                <el-form label-width="150px">
                                    <el-alert
                                        v-if="ss.message"
                                        :title="ss.message"
                                        type="info"
                                        show-icon
                                        class="stack-alert"
                                    />
                                    <div class="stack-alert-wrap">
                                        <el-alert
                                            v-for="(error, idx) in ss.validationErrors"
                                            :key="idx"
                                            show-icon
                                            :closable="false"
                                            type="error"
                                            :title="error"
                                            class="stack-alert"
                                        />
                                        <el-alert
                                            v-for="(warn, idx) in ss.validationWarnings"
                                            :key="idx"
                                            show-icon
                                            :closable="false"
                                            type="warning"
                                            :title="warn"
                                            class="stack-alert"
                                        />
                                    </div>

                                    <el-form-item label="Datatype/Suffix">
                                        <el-select
                                            v-model="ss.type"
                                            required
                                            filterable
                                            placeholder="(exclude)"
                                            size="small"
                                            class="w80"
                                            @change="validateAll()"
                                        >
                                            <el-option value="exclude">(Exclude from BIDS conversion)</el-option>
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

                                    <div v-if="ss.type">
                                        <el-form-item
                                            v-for="(v, entity) in getSomeEntities(ss.type)"
                                            :key="entity"
                                            :label="entity.toString() + '-' + (v == 'required' ? ' *' : '')"
                                            class="entity-item"
                                        >
                                            <el-popover
                                                v-if="bidsSchema.entities[entity]"
                                                :width="350"
                                                :title="bidsSchema.entities[entity].name"
                                                :content="bidsSchema.entities[entity].description"
                                            >
                                                <template #reference>
                                                    <el-input
                                                        v-model="ss.entities[entity]"
                                                        size="small"
                                                        :required="v == 'required'"
                                                        @change="validateAll()"
                                                    />
                                                </template>
                                            </el-popover>
                                        </el-form-item>
                                    </div>

                                    <div v-if="ss.type && (ss.type.startsWith('fmap/') || ss.type === 'perf/m0scan')">
                                        <el-form-item label="IntendedFor">
                                            <el-select
                                                v-model="ss.IntendedFor"
                                                required
                                                multiple
                                                filterable
                                                placeholder="Please select Series"
                                                size="small"
                                                class="w80"
                                                @change="validateAll()"
                                            >
                                                <el-option
                                                    v-for="(
                                                        series, idx
                                                    ) in ezbids.series /*.filter(s=>s.type != 'exclude')*/"
                                                    :key="idx"
                                                    :label="'(#' + idx.toString() + ') ' + series.type"
                                                    :value="idx"
                                                >
                                                    (#{{ idx.toString() }}) {{ series.type }}
                                                </el-option>
                                            </el-select>
                                            <p class="field-note">
                                                * <b>Recommended (Required if perf/m0scan)</b>: select Series that this
                                                sequence should be applied to.
                                            </p>
                                        </el-form-item>
                                    </div>

                                    <div
                                        v-if="
                                            ss.type &&
                                            !ss.type.includes('exclude') &&
                                            !ss.type.startsWith('meg') &&
                                            !ss.type.startsWith('pet')
                                        "
                                    >
                                        <el-form-item label="B0FieldIdentifier" prop="B0FieldIdentifier">
                                            <el-select
                                                v-model="ss.B0FieldIdentifier"
                                                multiple
                                                filterable
                                                allow-create
                                                default-first-option
                                                placeholder="Enter text string"
                                                size="small"
                                                class="w80"
                                                @change="validateAll()"
                                            />
                                            <p class="field-note">
                                                * <b>Recommended/Optional if no IntendedFor</b>: If this sequence will
                                                be used for fieldmap/distortion correction, enter a text string of your
                                                choice. A good formatting suggestion is the "datatype_suffix[index]"
                                                format (e.g., <b>fmap_epi0</b>, <b>fmap_phasediff1</b>, etc). If another
                                                sequence will be used with this one for fieldmap/distortion correction,
                                                use the exact same text string there as well. Leave field blank if
                                                unclear.
                                            </p>
                                        </el-form-item>
                                        <el-form-item label="B0FieldSource" prop="B0FieldSource">
                                            <el-select
                                                v-model="ss.B0FieldSource"
                                                multiple
                                                filterable
                                                allow-create
                                                default-first-option
                                                placeholder="Enter text string"
                                                size="small"
                                                class="w80"
                                                @change="validateAll()"
                                            />
                                            <p class="field-note">
                                                * <b>Recommended/Optional if no IntendedFor</b>: If fieldmap/distortion
                                                correction will be applied to this image, enter the identical text
                                                string from the B0FieldIdentifier field of the sequence(s) used to
                                                create the fieldmap/distortion estimation. Leave field blank if unclear.
                                            </p>
                                        </el-form-item>
                                    </div>

                                    <el-form-item label="Common Metadata">
                                        <p style="font-size: 12px; line-height: normal">
                                            All objects under this series contain the following common metadata.
                                        </p>
                                        <p class="metadata-tags">
                                            <el-tag type="info" size="mini">
                                                <small>SeriesDescription: {{ ss.SeriesDescription }}</small>
                                            </el-tag>
                                            <el-tag type="info" size="mini">
                                                <small>EchoTime: {{ ss.EchoTime }}</small>
                                            </el-tag>
                                            <el-tag type="info" size="mini">
                                                <small>ImageType: {{ ss.ImageType }}</small>
                                            </el-tag>
                                            <el-tag type="info" size="mini">
                                                <small>RepetitionTime: {{ ss.RepetitionTime }}</small>
                                            </el-tag>
                                        </p>
                                    </el-form-item>

                                    <div style="margin-top: 10px">
                                        <el-form-item
                                            v-if="
                                                ['perf/asl', 'perf/m0scan'].includes(ss.type) ||
                                                ss.type.startsWith('pet') ||
                                                ss.type.startsWith('func') ||
                                                ss.type.startsWith('fmap') ||
                                                ss.type.startsWith('dwi') ||
                                                ss.type.startsWith('anat') ||
                                                ss.type.startsWith('meg')
                                            "
                                            label="Relevant Metadata"
                                        >
                                            <ModalityForm :ss="ss" :ezbids="ezbids" @form-submitted="submitForm" />
                                        </el-form-item>
                                    </div>
                                </el-form>
                            </div>

                            <div class="panel-card panel-card--objects">
                                <p class="objects-header">
                                    <small>The following objects belongs to this series.</small>
                                </p>
                                <div v-for="object in getObjectsFromSeries(ss)" :key="object.idx" class="object">
                                    <div class="object__head">
                                        <i class="el-icon-caret-right" />
                                        <div class="object__entities">
                                            <div
                                                v-for="(v, k) in object._entities"
                                                :key="object.idx + '.' + k.toString()"
                                            >
                                                <span v-if="v">
                                                    {{ k }}-<b>{{ v }}</b>
                                                </span>
                                            </div>
                                        </div>
                                        <div class="object__stats">
                                            <el-tag size="mini" type="info"
                                                >volumes:
                                                {{ ezbids.objects[object.idx].analysisResults.NumVolumes }}</el-tag
                                            >
                                            <el-tag size="mini" type="info">
                                                filesize:
                                                {{ prettyBytes(ezbids.objects[object.idx].analysisResults.filesize) }}
                                            </el-tag>
                                            <el-tag size="mini" type="info">
                                                orientation:
                                                {{ ezbids.objects[object.idx].analysisResults.orientation }}
                                            </el-tag>
                                            <el-tag size="mini" type="info">
                                                direction: {{ ezbids.objects[object.idx].PED }}
                                            </el-tag>
                                        </div>
                                    </div>
                                    <div>
                                        <div v-for="(item, itemIdx) in ezbids.objects[object.idx].items" :key="itemIdx">
                                            <div v-if="item.pngPaths">
                                                <div v-for="(path, idx) in item.pngPaths" :key="idx">
                                                    <div class="object__path-row">
                                                        <pre>{{ path }}</pre>
                                                        <el-button
                                                            type="info"
                                                            size="small"
                                                            @click="$emit('niivue', item.path)"
                                                        >
                                                            <font-awesome-icon :icon="['fas', 'eye']" />
                                                            NiiVue
                                                        </el-button>
                                                    </div>
                                                    <AsyncImageLink :path="path" />
                                                </div>
                                            </div>
                                        </div>

                                        <div class="object__files">
                                            <b>Files</b>
                                            <div
                                                v-for="(item, idx) in ezbids.objects[object.idx].items"
                                                :key="idx"
                                                class="object__file"
                                            >
                                                <div class="object__file-path">
                                                    <span class="object__file-index">#{{ idx + 1 }}</span>
                                                    <pre>{{ item.path }}</pre>
                                                </div>
                                                <showfile
                                                    v-if="fileHasDisplayableContents(item.path)"
                                                    :path="item.path"
                                                />
                                                <p v-else class="object__file-no-contents">
                                                    no file contents to display
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="metadata-panel">
                            <h5 class="section-title">Series Metadata</h5>
                            <div class="metadata-panel__content">
                                <div class="metadata-panel__tags">
                                    <el-tag size="mini" type="info">Series #{{ ss.series_idx }}</el-tag>
                                    <el-tag size="mini" type="success">{{ ss.type }}</el-tag>
                                    <el-tag size="mini" effect="plain"
                                        >{{ getObjectsFromSeries(ss).length }} objects</el-tag
                                    >
                                </div>
                                <pre class="metadata-panel__pre">{{ stringifyMetadata(selectedSeriesMetadata) }}</pre>
                            </div>
                        </div>
                    </template>
                </div>
            </main>
        </div>
        <el-collapse>
            <el-collapse-item title="Debug">
                <pre v-if="config.debug" class="debug-pre">{{ ezbids.series }}</pre>
            </el-collapse-item>
        </el-collapse>
    </div>
</template>

<script lang="ts">
import { mapState, mapGetters } from 'vuex';
import { defineComponent } from 'vue';

import showfile from '@/components/showfile.vue';
import datatype from '@/components/datatype.vue';
import ModalityForm from '@/components/modalityForm.vue';

import { prettyBytes } from '@/filters';

import { validateEntities, validate_B0FieldIdentifier_B0FieldSource, metadataAlerts } from '@/libUnsafe';
import anatYaml from '@/assets/schema/rules/sidecars/anat.yaml';
import funcYaml from '@/assets/schema/rules/sidecars/func.yaml';
import fmapYaml from '@/assets/schema/rules/sidecars/fmap.yaml';
import dwiYaml from '@/assets/schema/rules/sidecars/dwi.yaml';
import aslYaml from '@/assets/schema/rules/sidecars/asl.yaml';
import petYaml from '@/assets/schema/rules/sidecars/pet.yaml';
import megYaml from '@/assets/schema/rules/sidecars/meg.yaml';
import metadataInfo from '@/assets/schema/rules/sidecars/metadata.yaml';

import AsyncImageLink from '@/components/AsyncImageLink.vue';

import { IEZBIDS, IObject, IObjectItem, Series } from '@/store/store.types';

export default defineComponent({
    components: {
        datatype,
        showfile,
        AsyncImageLink,
    },
    emits: ['niivue'],

    data() {
        return {
            showInfo: {} as any,
            ss: null as Series | null, //selected series
            metadataAlertsFields: [] as any,
            fields: {},
            showDialog: false,
            rules: {},
            formData: {},
        };
    },

    computed: {
        ...mapState(['ezbids', 'session', 'bidsSchema', 'config']),
        ...mapGetters(['getBIDSEntities', 'getMetaDataRule']), //doesn't work with ts?
        selectedSeriesMetadata(): Record<string, unknown> {
            if (!this.ss) return {};
            return {
                series_idx: this.ss.series_idx,
                type: this.ss.type,
                SeriesDescription: this.ss.SeriesDescription,
                EchoTime: this.ss.EchoTime,
                RepetitionTime: this.ss.RepetitionTime,
                ImageType: this.ss.ImageType,
                entities: this.ss.entities,
                IntendedFor: this.ss.IntendedFor,
                B0FieldIdentifier: this.ss.B0FieldIdentifier,
                B0FieldSource: this.ss.B0FieldSource,
                validationErrors: this.ss.validationErrors,
                validationWarnings: this.ss.validationWarnings,
                objectCount: this.getObjectsFromSeries(this.ss).length,
            };
        },
    },

    mounted() {
        this.validateAll();
    },

    methods: {
        prettyBytes,

        getObjectsFromSeries(series: Series): IObject[] {
            const idx = this.ezbids.series.indexOf(series);
            return (this.ezbids.objects as IObject[]).filter((object) => object.series_idx == idx);
        },

        fileHasDisplayableContents(path: string) {
            const ext = path.split('.').pop()?.toLowerCase() ?? '';
            return ['json', 'bval', 'bvec'].includes(ext);
        },

        seriesListLabel(series: Series) {
            return series.SeriesDescription || 'No SeriesDescription available';
        },

        seriesListExtension(series: Series) {
            const extensions = new Set<string>();
            for (const object of this.getObjectsFromSeries(series)) {
                const ext = this.objectListExtension(object);
                if (ext) {
                    ext.split(', ').forEach((e) => extensions.add(e));
                }
            }
            return [...extensions].join(', ');
        },

        objectListExtension(object: IObject) {
            return this.itemExtension(this.normalizeItems(object.items));
        },

        normalizeItems(items: IObjectItem[] | IObjectItem | undefined): IObjectItem[] {
            if (!items) return [];
            return Array.isArray(items) ? items : [items];
        },

        itemExtension(items: IObjectItem[]) {
            const extensions = new Set<string>();
            for (const item of items) {
                const ext = this.pathExtension(item.path) || this.nameExtension(item.name);
                if (ext) extensions.add(ext);
            }
            return [...extensions].join(', ');
        },

        pathExtension(path: string | undefined) {
            if (!path) return '';
            const basename = path.split(/[/\\]/).pop() || path;
            const lower = basename.toLowerCase();
            if (lower.endsWith('.nii.gz')) return '.nii.gz';
            if (lower.endsWith('.bval') || lower.endsWith('.bvec')) {
                return basename.slice(basename.lastIndexOf('.'));
            }
            const dot = basename.lastIndexOf('.');
            if (dot <= 0) return '';
            return basename.slice(dot);
        },

        nameExtension(name: string | undefined) {
            if (!name) return '';
            const trimmed = name.trim();
            if (!trimmed) return '';
            return trimmed.startsWith('.') ? trimmed : `.${trimmed}`;
        },

        stringifyMetadata(metadata: Record<string, unknown>) {
            return JSON.stringify(metadata, null, 2);
        },

        getSomeEntities(type: string): any {
            const entities = Object.assign({}, this.getBIDSEntities(type));
            delete entities.subject;
            delete entities.session;
            return entities;
        },

        toggleInfo(entity: string) {
            this.showInfo[entity] = !this.showInfo[entity];
        },

        BIDSURI($root: IEZBIDS, b: boolean) {
            if (b === true) {
                $root.BIDSURI = true;
                localStorage.setItem('checkboxState', 'true');
            } else {
                $root.BIDSURI = false;
                localStorage.setItem('checkboxState', 'false');
            }
        },

        validate(s: Series | null) {
            if (!s) return;

            s.validationErrors = [];
            s.validationWarnings = [];

            if (s.type != 'exclude') {
                validateEntities('Series', s);
                validate_B0FieldIdentifier_B0FieldSource(s);
            }

            /* Alert users to metadata issues, such as missing required fields or
            improperly-formmated metadata field values.
            */
            let bidsDatatypeMetadata = {};
            if (['perf/asl', 'perf/m0scan'].includes(s.type)) {
                bidsDatatypeMetadata = aslYaml;
            } else if (s.type.startsWith('pet')) {
                bidsDatatypeMetadata = petYaml;
            } else if (s.type.startsWith('func')) {
                bidsDatatypeMetadata = funcYaml;
            } else if (s.type.startsWith('fmap')) {
                bidsDatatypeMetadata = fmapYaml;
            } else if (s.type.startsWith('dwi')) {
                bidsDatatypeMetadata = dwiYaml;
            } else if (s.type.startsWith('anat')) {
                bidsDatatypeMetadata = anatYaml;
            } else if (s.type.startsWith('meg')) {
                bidsDatatypeMetadata = megYaml;
            }

            const metadataAlertsFields = metadataAlerts(
                bidsDatatypeMetadata,
                metadataInfo,
                this.ezbids,
                s.series_idx,
                s.type
            );
            // console.log(s.series_idx, s.type);
            // console.log('metadataAlertsFields', metadataAlertsFields);
            if (metadataAlertsFields.length) {
                let warn: string = `'Required metadata is missing, provided metadata field values have improper
                format. Please click on the "Edit Metadata" button below to resolve. You may skip fields for which you
                do not know the proper value, but you will not have a fully BIDS-compliant dataset.'`;
                s.validationWarnings.push(warn);
            }

            // DON'T REALLY NEED THIS if setRun() functionality is in place

            // //let user know if multiple series have same datatype and entity labels
            // if(s.type != "exclude") {
            //     for(let s2 of this.ezbids.series) {
            //         if(s == s2) continue;
            //         if(s.type != s2.type) continue;
            //         if(s2.type == "exclude") continue;

            //         let same = s2;
            //         for(let e in s.entities) {
            //             if(s.entities[e] != s2.entities[e]) {
            //                 same = undefined;
            //                 break;
            //             }
            //         }
            //         if(same) {
            //             const sameseries = s2.series_idx;
            //             s.validationWarnings.push("This series contains the same datatype, suffix and entity labels as series #"+sameseries+", consider setting different entity label(s) to differentiate between the series. If not, ezBIDS will automatically apply the run entity label to differentiate.");
            //             break;
            //         }
            //     }
            // }

            let entities_requirement = this.getBIDSEntities(s.type);
            for (let k in this.getSomeEntities(s.type)) {
                if (entities_requirement[k] == 'required') {
                    if (!s.entities[k]) {
                        s.validationErrors.push('entity: ' + k + ' is required.');
                    }
                }
            }

            /*
            If user specified a specific entity label and then changed the datatype/suffix pairing to something
            that doesn't allow that entity, we need to remove it. Otherwise, the bids-validator will complain.
            */
            for (let k in s.entities) {
                if (!['subject', 'session'].includes(k)) {
                    // this line prevents sequence ordering from being messed up
                    if (s.entities[k] !== '' && !entities_requirement[k]) {
                        s.entities[k] = '';
                    }
                }
            }

            if (s.type.startsWith('fmap/') || s.type === 'perf/m0scan') {
                if (!s.IntendedFor) s.IntendedFor = [];
                if (s.IntendedFor.length == 0) {
                    if (s.type.startsWith('fmap/')) {
                        s.validationWarnings.push(
                            'It is recommended that field map (fmap) images have IntendedFor set to at least 1 series ID. This is necessary if you plan on using processing BIDS-apps such as fMRIPrep'
                        );
                    } else if (s.type === 'perf/m0scan') {
                        s.validationErrors.push(
                            'It is required that perfusion m0scan images have IntendedFor set to at least 1 series ID.'
                        );
                    }
                }
                // Ensure other fmap or perf/m0scan series aren't included in the IntendedFor mapping
                if (s.IntendedFor.length > 0) {
                    s.IntendedFor.forEach((i) => {
                        if (
                            this.ezbids.series[i].type.startsWith('fmap/') ||
                            this.ezbids.series[i].type === 'perf/m0scan'
                        ) {
                            s.validationErrors.push(
                                'The selected series (#' +
                                    i +
                                    ") appears to be a field map (fmap), which isn't allowed in the IntendedFor mapping. Please remove this series, or, if it isn't a field map, please correct it."
                            );
                        }
                    });
                }
            }
            /*
            If user tries modifying a DWI b0map (fmap/epi) to dwi/dwi, warn them that it could be improper. At the
            end of the day though, user has final say.
            */
            if (s.type === 'dwi/dwi') {
                if (s.message.includes('fmap/epi')) {
                    s.validationWarnings.push(
                        'This sequence is believed to be a DWI b0map, which in BIDS corresponds to fmap/epi. If this sequence is not a DWI b0map, please proceed. Otherwise, please reconsider.'
                    );
                }
            }
        },

        isValid(cb: (v?: string) => void) {
            this.validateAll();

            let err = undefined;
            this.ezbids.series.forEach((s: Series) => {
                if (s.validationErrors.length > 0) err = 'Please correct all issues';
            });
            return cb(err);
        },

        validateAll() {
            this.ezbids.series.forEach(this.validate);
        },
        submitForm(data: any) {
            //TODO: should we make an interface for data in store/index.ts?
            this.ezbids = data;
            this.ezbids.series.forEach(this.validate);
        },
    },
});
</script>

<style lang="scss" scoped>
.series-page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0.5rem 1.25rem 2.75rem;
}

.series-intro {
    margin-bottom: 1.5rem;
    padding: 1.35rem 1.5rem 1.5rem;
    border-radius: 10px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-fill-color-blank, #fff);
    box-shadow: 0 1px 2px rgb(0 0 0 / 4%);
}

.series-intro__title {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--el-text-color-primary, #303133);
}

.series-intro__text {
    font-size: 14px;
    line-height: normal;
    color: var(--el-text-color-regular, #606266);
}

.series-workspace {
    display: grid;
    grid-template-columns: minmax(200px, 260px) minmax(0, 1fr);
    gap: 12px;
    margin: 1rem 0;
    height: min(80vh, calc(100vh - 14rem));
    min-height: 420px;
    min-width: 0;
}

.series-workspace > * {
    min-height: 0;
}

.series-list-panel {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
    border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
    padding-right: 6px;
}

.series-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    min-height: 0;
    min-width: 0;
    overflow-y: auto;
}

.series-detail-panel {
    min-height: 0;
    min-width: 0;
    height: 100%;
    padding-left: 2px;
    overflow-x: hidden;
    overflow-y: auto;
}

.series-detail-scroll {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 0 2rem 12px 2rem;
    padding-bottom: 12px;
}

.series-list__item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 100%;
    min-width: 0;
    margin: 0;
    padding: 8px;
    text-align: left;
    font: inherit;
    color: var(--el-text-color-primary, #303133);
    border: 1px solid transparent;
    border-radius: 6px;
    background: transparent;
    cursor: pointer;
    transition:
        background-color 0.2s ease,
        border-color 0.2s ease;
}

.series-list__item:hover {
    background: var(--el-fill-color-light, #f5f7fa);
}

.series-list__item--active {
    background: var(--el-color-primary-light-9, #ecf5ff);
    border-color: var(--el-color-primary-light-7, #b3d8ff);
}

.series-list__item--excluded {
    opacity: 0.4;
}

.series-list__top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
}

.series-list__tags {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 0;
}

.series-list :deep(.el-tooltip__trigger) {
    display: block;
    min-width: 0;
}

.series-list__desc {
    font-size: 12px;
    line-height: 1.35;
    color: var(--el-text-color-primary, #303133);
    min-width: 0;
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    text-overflow: ellipsis;
    overflow-wrap: anywhere;
}

.series-list__ext {
    min-width: 0;
    font-size: 11px;
    line-height: 1.2;
    color: var(--el-text-color-secondary, #909399);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.series-list__validation {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-start;
    gap: 4px;
    margin-top: auto;
    padding-top: 4px;
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

.empty-state__hint {
    margin-top: 10px;
    background: var(--el-fill-color-blank, #fff);
    border-radius: 4px;
    padding: 10px;
}

.empty-state__message {
    margin: 0;
    color: var(--el-text-color-secondary, #909399);
    font-size: 14px;
    text-transform: lowercase;
}

.series-main {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
}

.panel-card {
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    border-radius: 8px;
    background: var(--el-bg-color, #fff);
    padding: 14px;
    min-width: 0;
    max-width: 100%;

    :deep(.el-form-item__content) {
        min-width: 0;
        max-width: 100%;
    }
}

.panel-card--objects {
    padding: 0;
    overflow: hidden;
}

.section-title {
    margin: 0 0 10px 0;
    font-weight: 600;
}

.stack-alert-wrap {
    margin-bottom: 10px;
}

.stack-alert {
    margin-bottom: 4px;
}

.w80 {
    width: 80%;
}

.entity-item {
    width: 350px;
}

.field-note {
    margin-top: 4px;
    font-size: 12px;
    line-height: 1.6;
}

.metadata-tags {
    margin-top: 4px;
    margin-bottom: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    min-width: 0;
    max-width: 100%;
}

.metadata-tags :deep(.el-tag) {
    height: auto;
    max-width: 100%;
    white-space: normal;
    word-break: break-word;
    overflow-wrap: anywhere;
    line-height: 1.35;
    padding-top: 4px;
    padding-bottom: 4px;
}

.objects-header {
    border-top: 1px solid #eee;
    padding: 10px 14px;
    margin: 0;
}

.object {
    padding: 0 14px 14px;
    margin-bottom: 14px;
    min-width: 0;
    border-bottom: 1px dashed var(--el-border-color-lighter, #ebeef5);
}

.series-detail-scroll pre {
    box-sizing: border-box;
    max-width: 100%;
    min-width: 0;
    margin: 0;
    overflow-x: auto;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
}

.object__path-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-width: 0;
    margin-bottom: 0.5rem;

    pre {
        flex: 1;
        min-width: 0;
    }
}

.object__files {
    margin-top: 10px;

    > b {
        display: block;
        margin-bottom: 0.5rem;
    }
}

.object__file-no-contents {
    margin: 0;
    font-size: 12px;
    color: var(--el-text-color-secondary, #909399);
    text-transform: lowercase;
}

.object__file {
    margin-bottom: 1rem;

    &:last-child {
        margin-bottom: 0;
    }
}

.object__file-path {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 0.5rem;
    min-width: 0;

    pre {
        flex: 1;
        min-width: 0;
    }
}

.object__file-index {
    flex-shrink: 0;
    font-size: 11px;
    font-weight: 600;
    line-height: 1.45;
    color: var(--el-text-color-secondary, #909399);
    padding-top: 2px;
}

.object:last-child {
    border-bottom: 0;
    margin-bottom: 0;
}

.object__head {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    margin: 0.5rem 0;
}

.object__entities {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 10px;
    flex: 1;
    font-size: 85%;
}

.object__stats {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 6px;
}

.metadata-panel {
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    border-radius: 8px;
    background: var(--el-bg-color, #fff);
    padding: 12px;
    min-width: 0;
    display: flex;
    flex-direction: column;
}

.metadata-panel__content {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
    min-height: 0;
    flex: 1;
}

.metadata-panel__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.metadata-panel__pre {
    padding: 10px;
    border-radius: 6px;
    background: #2a2d34;
    color: #f2f4f8;
    font-size: 12px;
    line-height: 1.45;
}

.metadata-panel__empty {
    color: var(--el-text-color-secondary, #909399);
    background-color: #f5f7fa;
    font-size: 13px;
    padding-top: 8px;
}

.debug-pre {
    margin-top: 10px;
    height: 80vh;
    overflow: auto;
    background-color: #666;
    color: white;
    padding: 10px;
    border-radius: 6px;
}

.el-form-item {
    margin-bottom: 0;
}
</style>
