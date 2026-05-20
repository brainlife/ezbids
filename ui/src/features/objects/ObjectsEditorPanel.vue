<template>
    <div class="editor-panel">
        <el-form class="editor-form">
            <div class="panel-card">
                <div>
                    <p style="white-space: nowrap">Series Description:</p>
                    <p style="word-break: break-all; color: var(--el-text-color-secondary, #909399)">
                        {{ object._SeriesDescription }}
                    </p>
                </div>
                <el-form-item>
                    <el-checkbox v-model="object.exclude" @change="$emit('update', object)"
                        >Exclude this object</el-checkbox
                    >
                </el-form-item>
                <div v-if="object.exclude === true" class="stack-alert-wrap">
                    <el-alert :closable="false" type="info">This object will be excluded from the BIDS output</el-alert>
                </div>

                <div class="stack-alert-wrap">
                    <el-alert
                        v-for="(error, idx) in object.validationErrors"
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
                        v-for="(warning, idx) in object.validationWarnings"
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
                        v-for="(error, idx) in object.analysisResults.errors"
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
                        v-model="object.type"
                        clearable
                        :placeholder="object._type"
                        size="small"
                        style="width: 100%"
                        @change="$emit('update', object)"
                    >
                        <el-option value="">(Use Series Default)</el-option>
                        <el-option-group v-for="type in bidsSchema.datatypes" :key="type.label" :label="type.label">
                            <el-option v-for="subtype in type.options" :key="subtype.value" :value="subtype.value">
                                {{ type.label }} / {{ subtype.label }}
                            </el-option>
                        </el-option-group>
                    </el-select>
                </el-form-item>

                <div class="entity-grid">
                    <div v-for="(v, entity) in getBIDSEntities(object._type)" :key="entity" class="entity-row">
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
                                        v-model="object.entities[entity]"
                                        size="small"
                                        :placeholder="getDefault(object, entity.toString())"
                                        @blur="$emit('update', object)"
                                    />
                                </template>
                            </el-popover>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="object._type.startsWith('fmap/') || object._type === 'perf/m0scan'" class="border-top">
                <el-form-item label="IntendedFor" class="form-grid-item">
                    <el-select
                        v-model="object.IntendedFor"
                        multiple
                        placeholder="Select Object"
                        style="width: 100%"
                        @change="$emit('update', object)"
                    >
                        <el-option
                            v-for="o in session.objects.filter((o) => !isExcluded(o))"
                            :key="o.idx"
                            :label="intendedForLabel(o)"
                            :value="o.idx"
                        >
                        </el-option>
                    </el-select>
                </el-form-item>
                <p class="field-note">
                    * IntendedFor information is used to specify which image this fieldmap is intended for. This is
                    recommended information according to the BIDS specification.
                </p>
            </div>
            <div
                v-if="
                    object._type &&
                    !object._type.includes('exclude') &&
                    (!object._type.includes('events') ||
                        ['perf/asl', 'perf/m0scan'].includes(object._type) ||
                        object._type.startsWith('pet') ||
                        object._type.startsWith('func') ||
                        object._type.startsWith('fmap') ||
                        object._type.startsWith('dwi') ||
                        object._type.startsWith('anat') ||
                        object._type.startsWith('meg'))
                "
                class="border-top"
            >
                <template
                    v-if="
                        !object._type.includes('events') &&
                        !object._type.startsWith('meg') &&
                        !object._type.startsWith('pet')
                    "
                >
                    <el-form-item label="B0FieldIdentifier" class="form-grid-item">
                        <el-select
                            v-model="object.B0FieldIdentifier"
                            multiple
                            filterable
                            allow-create
                            default-first-option
                            placeholder="Enter text string"
                            size="small"
                            style="width: 100%"
                            @change="$emit('update', object)"
                        >
                        </el-select>
                    </el-form-item>
                    <p class="field-note">
                        * <b>Recommended/Optional if no IntendedFor</b>: If this sequence will be used fieldmap
                        correction, enter a text string of your choice. A good formatting suggestion is the
                        "datatype_suffix[index]" format (e.g., <b>fmap_epi0</b>, <b>fmap_phasediff1</b>, etc). If
                        another sequence will be used with this one for fieldmap correction, use the exact same text
                        string there as well. Leave field if unclear.
                    </p>

                    <el-form-item label="B0FieldSource" class="form-grid-item">
                        <el-select
                            v-model="object.B0FieldSource"
                            multiple
                            filterable
                            allow-create
                            default-first-option
                            placeholder="Enter text string"
                            size="small"
                            style="width: 100%"
                            @change="$emit('update', object)"
                        >
                        </el-select>
                    </el-form-item>
                    <p class="field-note">
                        * <b>Recommended/Optional if no IntendedFor</b>: If this sequence will be used fieldmap
                        correction, enter a text string of your choice. A good formatting suggestion is the
                        "datatype_suffix" format (e.g., fmap_epi, fmap_phasediff). If another sequence will be used with
                        this one for fieldmap correction, use the same text string there as well. Leave field blank if
                        unclear.
                    </p>
                </template>

                <el-form-item
                    v-if="
                        ['perf/asl', 'perf/m0scan'].includes(object._type) ||
                        object._type.startsWith('pet') ||
                        object._type.startsWith('func') ||
                        object._type.startsWith('fmap') ||
                        object._type.startsWith('dwi') ||
                        object._type.startsWith('anat') ||
                        object._type.startsWith('meg')
                    "
                    class="form-grid-item form-grid-item--file"
                    label="Relevant Metadata"
                >
                    <ModalityForm :ss="object" :ezbids="ezbids" @form-submitted="$emit('form-submitted', $event)" />
                </el-form-item>
            </div>

            <div v-if="object.items.length" class="border-top item-files">
                <div v-for="(item, idx) in object.items" :key="idx" class="item-block">
                    <el-form-item :label="item.name || 'noname'" class="form-grid-item form-grid-item--file">
                        <div class="item-path-row">
                            <el-select
                                v-model="item.path"
                                placeholder="Source path"
                                size="small"
                                class="item-path-row__select"
                            >
                                <el-option
                                    v-for="(optItem, optIdx) in object.items"
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
                        </div>
                    </el-form-item>
                    <el-form-item v-if="item.sidecar" label="sidecar" class="form-grid-item form-grid-item--file">
                        <el-input
                            v-model="item.sidecar_json"
                            type="textarea"
                            rows="10"
                            class="item-field-input"
                            @blur="$emit('update', object)"
                        />
                    </el-form-item>
                    <el-form-item
                        v-if="item.headers"
                        class="form-grid-item form-grid-item--file form-grid-item--stacked-label"
                    >
                        <template #label>
                            <span class="stacked-label">
                                Nifti Headers<br />
                                <span class="stacked-label__sub">(read-only)</span>
                            </span>
                        </template>
                        <pre class="headers item-field-pre">{{ item.headers }}</pre>
                    </el-form-item>
                    <el-form-item v-if="item.eventsBIDS" label="eventsBIDS" class="form-grid-item form-grid-item--file">
                        <div class="item-field-scroll">
                            <el-table :data="item.eventsBIDS" size="mini" border>
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
                        </div>
                    </el-form-item>
                </div>
            </div>

            <div v-if="object.analysisResults.filesize" class="analysis-summary">
                <p style="font-size: 90%">
                    Volumes: <b>{{ object.analysisResults.NumVolumes }}</b> &nbsp;&nbsp; Orientation:
                    <b>{{ object.analysisResults.orientation }}</b> &nbsp;&nbsp; File Size:
                    <b>{{ prettyBytes(object.analysisResults.filesize) }}</b>
                </p>
                <div v-for="(item, itemIdx) in ezbids.objects[object.idx].items" :key="itemIdx">
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
                <pre v-if="config.debug" class="debug-pre">{{ object }}</pre>
            </el-collapse-item>
        </el-collapse>
    </div>
</template>

<script lang="ts">
import { mapState, mapGetters } from 'vuex';
import { defineComponent, PropType } from 'vue';
import ModalityForm from '@/components/modalityForm.vue';
import AsyncImageLink from '@/components/AsyncImageLink.vue';
import { prettyBytes } from '@/filters';
import { IObject, OrganizedSession } from '@/store/store.types';

export default defineComponent({
    name: 'ObjectsEditorPanel',
    components: {
        ModalityForm,
        AsyncImageLink,
    },
    props: {
        object: {
            type: Object as PropType<IObject>,
            required: true,
        },
        session: {
            type: Object as PropType<OrganizedSession>,
            required: true,
        },
    },
    emits: ['update', 'niivue', 'form-submitted'],
    computed: {
        ...mapState(['ezbids', 'config', 'bidsSchema']),
        ...mapGetters(['getBIDSEntities', 'findSubject', 'findSession']),
    },
    methods: {
        prettyBytes,

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

        getDefault(o: IObject, entity: string): string {
            if (entity == 'subject') {
                const subject = this.findSubject(o);
                return subject.subject;
            } else if (entity == 'session') {
                const subject = this.findSubject(o);
                const session = this.findSession(subject, o);
                return session.session;
            } else {
                const objects = this.ezbids.objects[o.idx];
                if (!objects) return '';
                return objects._entities[entity];
            }
        },

        intendedForLabel(o: IObject) {
            const series = this.ezbids.series[o.series_idx];
            if (!series) return 'no-series';
            let l = '#' + series.series_idx + ' ';
            l += o._type;
            for (const k in o._entities) {
                if (k == 'subject' || k == 'session') continue;
                if (!o._entities[k]) continue;
                l += ' ' + k + '-' + o._entities[k];
            }
            return l;
        },
    },
});
</script>

<style lang="scss" scoped>
.editor-panel {
    flex: 1 1 auto;
    width: 100%;
    min-width: 0;
    min-height: 0;
    padding-right: 8px;
    box-sizing: border-box;
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
    grid-template-columns: 150px minmax(0, 1fr);
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

.form-grid-item--file :deep(.el-form-item__label) {
    width: 96px;
    flex-shrink: 0;
}

.form-grid-item--stacked-label :deep(.el-form-item__label) {
    line-height: 1.35;
}

.stacked-label__sub {
    font-size: 12px;
    font-weight: normal;
    color: var(--el-text-color-secondary, #909399);
}

.editor-form :deep(.el-form-item__content) {
    flex: 1;
    min-width: 0;
    max-width: 100%;
}

.border-top {
    border-top: 1px solid #f6f6f6;
    padding-top: 2px;
    margin-top: 2px;
}

.item-files,
.item-block {
    max-width: 100%;
    min-width: 0;
}

.item-block + .item-block {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #f6f6f6;
}

.item-path-row {
    display: flex;
    align-items: center;
    gap: 8px;
    max-width: 100%;
    min-width: 0;
}

.item-path-row__select {
    flex: 1;
    min-width: 0;
}

.item-field-input,
.item-field-pre,
.item-field-scroll {
    max-width: 100%;
    min-width: 0;
}

.item-field-scroll {
    overflow-x: auto;
}

.item-field-input :deep(textarea) {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
}

pre.headers {
    width: 100%;
    max-width: 100%;
    height: 200px;
    margin: 0;
    box-sizing: border-box;
    overflow: auto;
    line-height: 1.5;
    border-radius: 5px;
    padding: 5px 15px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
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

.editor-form :deep(.el-form-item) {
    margin-bottom: 10px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    max-width: 100%;
    min-width: 0;
}
</style>
