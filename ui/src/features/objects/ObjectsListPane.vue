<template>
    <div ref="objectsList" class="objects-list">
        <section v-for="o_sub in organized" :key="o_sub.sub" class="subject-block">
            <header v-if="o_sub.sub != ''" class="subject-header">
                <div
                    class="subject-header__label"
                    :class="{ 'subject-header__label--excluded': isSubjectExcluded(o_sub) }"
                >
                    <font-awesome-icon class="tier-icon" :icon="['fas', 'user']" aria-hidden="true" />
                    <span class="subject-header__id line-clamp-2">sub-{{ o_sub.sub }}</span>
                </div>
                <el-checkbox
                    :value="o_sub.exclude"
                    class="exclude-checkbox"
                    @change="$emit('exclude-subject', o_sub.sub.toString(), $event)"
                >
                    <span class="exclude-checkbox__label">Exclude subject</span>
                </el-checkbox>
            </header>

            <div class="subject-body">
                <div v-for="o_ses in o_sub.sess" :key="o_ses.sess" class="session-block">
                    <header
                        v-if="o_ses.sess"
                        class="session-header"
                        :class="{ 'session-header--excluded': isSessionExcluded(o_ses) }"
                    >
                        <div class="session-header__info">
                            <div class="session-header__label">
                                <font-awesome-icon class="tier-icon" :icon="['fas', 'clock']" aria-hidden="true" />
                                <span class="session-header__id line-clamp-2">ses-{{ o_ses.sess }}</span>
                            </div>
                            <span v-if="o_ses.AcquisitionDate" class="session-header__date line-clamp-2">{{
                                o_ses.AcquisitionDate
                            }}</span>
                        </div>
                        <el-checkbox
                            :value="o_ses.exclude"
                            class="exclude-checkbox"
                            @change="$emit('exclude-session', o_sub.sub.toString(), o_ses.sess.toString(), $event)"
                        >
                            <span class="exclude-checkbox__label">Exclude session</span>
                        </el-checkbox>
                    </header>

                    <div class="object-groups">
                        <div
                            v-for="section in groupSections(o_ses)"
                            :key="`${o_ses.sess}-${section.id}`"
                            class="object-group"
                        >
                            <div v-if="section.showLabel" class="object-group__label">
                                Scan section {{ section.id }}
                            </div>

                            <div class="object-group__items">
                                <button
                                    v-for="o in section.objects"
                                    :key="o.idx"
                                    type="button"
                                    class="object-item"
                                    :data-object-idx="o.idx"
                                    :class="{
                                        'object-item--active': selectedObject === o,
                                        'object-item--excluded': isExcluded(o),
                                    }"
                                    @click="$emit('select', o, o_ses)"
                                >
                                    <div class="object-item__top">
                                        <el-tag
                                            v-if="o.series_idx !== undefined"
                                            type="info"
                                            size="mini"
                                            :title="'Series#' + o.series_idx + ' ' + o._SeriesDescription"
                                        >
                                            #{{ o.series_idx }}
                                        </el-tag>
                                        <div class="object-item__type line-clamp-2">
                                            <datatype
                                                :type="o._type"
                                                :series_idx="o.series_idx"
                                                :entities="o._entities"
                                            />
                                        </div>
                                    </div>
                                    <div class="object-item__desc line-clamp-2">{{ objectListLabel(o) }}</div>
                                    <span v-if="objectListExtension(o)" class="object-item__ext">{{
                                        objectListExtension(o)
                                    }}</span>

                                    <div
                                        v-if="
                                            o.validationErrors.length > 0 ||
                                            (!isExcluded(o) && o.validationWarnings.length > 0) ||
                                            (!isExcluded(o) &&
                                                o._type != 'exclude' &&
                                                o.analysisResults?.errors?.length > 0)
                                        "
                                        class="object-item__badges"
                                    >
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
            </div>
        </section>
    </div>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';
import datatype from '@/components/datatype.vue';
import { IObject, IObjectItem, OrganizedSession, OrganizedSubject } from '@/store/store.types';

interface ObjectSection {
    id: number;
    objects: IObject[];
    showLabel: boolean;
}

export default defineComponent({
    name: 'ObjectsListPane',
    components: {
        datatype,
    },
    props: {
        organized: {
            type: Array as PropType<OrganizedSubject[]>,
            required: true,
        },
        selectedObject: {
            type: Object as PropType<IObject | null>,
            default: null,
        },
    },
    emits: ['select', 'exclude-subject', 'exclude-session'],
    methods: {
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

        isSubjectExcluded(sub: OrganizedSubject) {
            const objects = sub.sess.flatMap((s) => s.objects);
            return objects.length > 0 && objects.every((o) => this.isExcluded(o));
        },

        isSessionExcluded(sess: OrganizedSession) {
            return sess.objects.length > 0 && sess.objects.every((o) => this.isExcluded(o));
        },

        groupSections(sess: OrganizedSession): ObjectSection[] {
            const byId = new Map<number, IObject[]>();
            sess.objects.forEach((o) => {
                const sectionId = o.analysisResults.section_id;
                const group = byId.get(sectionId);
                if (group) group.push(o);
                else byId.set(sectionId, [o]);
            });

            const sections = [...byId.entries()].map(([id, objects]) => ({ id, objects })).sort((a, b) => a.id - b.id);

            const showLabels = sections.length > 1;
            return sections.map((section) => ({
                ...section,
                showLabel: showLabels,
            }));
        },

        objectListLabel(o: IObject) {
            return o._SeriesDescription || o.message || o._type || 'Object';
        },

        objectListExtension(o: IObject) {
            return this.itemExtension(this.normalizeItems(o.items));
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

        scrollSelectedIntoView(objectIdx: number, behavior: ScrollBehavior = 'smooth') {
            this.$nextTick(() => {
                const list = this.$refs.objectsList as HTMLElement | undefined;
                if (!list) return;
                const target = list.querySelector(`.object-item[data-object-idx="${objectIdx}"]`) as HTMLElement | null;
                if (!target) return;

                const offsetTop = target.offsetTop;
                const centeredTop = Math.max(0, offsetTop - list.clientHeight / 2 + target.clientHeight / 2);
                list.scrollTo({ top: centeredTop, behavior });
            });
        },
    },
});
</script>

<style lang="scss" scoped>
.objects-list {
    flex: 1;
    min-height: 0;
    height: 100%;
    overflow-y: auto;
    padding-right: 6px;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.subject-block {
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    border-radius: 8px;
    background: var(--el-fill-color-blank, #fff);
    overflow: hidden;
}

.subject-header,
.session-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
}

.subject-header {
    align-items: center;
    padding: 8px 10px;
    background: var(--el-fill-color-light, #f5f7fa);
    border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}

.subject-header__label,
.session-header__label {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
}

.subject-header__id,
.session-header__id,
.session-header__date {
    min-width: 0;
}

.subject-header__id {
    font-size: 14px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--el-text-color-primary, #303133);
}

.subject-header__label--excluded,
.session-header--excluded .session-header__info {
    opacity: 0.55;
}

.subject-body {
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.session-block {
    border: 1px solid var(--el-border-color-extra-light, #f2f6fc);
    border-radius: 6px;
    background: var(--el-fill-color-blank, #fff);
    overflow: hidden;
}

.session-header {
    padding: 7px 8px;
    background: var(--el-fill-color-lighter, #fafafa);
    border-bottom: 1px solid var(--el-border-color-extra-light, #f2f6fc);
}

.session-header__info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
}

.session-header__id {
    font-size: 12px;
    font-weight: 600;
    color: var(--el-text-color-primary, #303133);
}

.session-header__date {
    font-size: 10px;
    line-height: 1.3;
    color: var(--el-text-color-secondary, #909399);
}

.line-clamp-2 {
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow-wrap: anywhere;
}

.tier-icon {
    flex-shrink: 0;
    width: 12px;
    opacity: 0.7;
    color: var(--el-text-color-secondary, #909399);
}

.exclude-checkbox {
    flex-shrink: 0;

    :deep(.el-checkbox__label) {
        padding-left: 6px;
        line-height: 1.2;
    }
}

.exclude-checkbox__label {
    font-size: 11px;
    color: var(--el-text-color-secondary, #909399);
    white-space: nowrap;
}

.object-groups {
    padding: 6px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.object-group__label {
    margin: 2px 4px 4px;
    padding: 2px 8px;
    display: inline-block;
    width: fit-content;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--el-text-color-secondary, #909399);
    background: var(--el-fill-color-light, #f5f7fa);
    border-radius: 4px;
}

.object-group__items {
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.object-item {
    width: 100%;
    text-align: left;
    border: 1px solid transparent;
    background: transparent;
    border-radius: 6px;
    padding: 7px 8px;
    cursor: pointer;
    color: inherit;
    font: inherit;
    transition:
        background-color 0.2s ease,
        border-color 0.2s ease,
        opacity 0.2s ease;
}

.object-item:hover {
    background: var(--el-fill-color-light, #f5f7fa);
}

.object-item--active {
    background: var(--el-color-primary-light-9, #ecf5ff);
    border-color: var(--el-color-primary-light-7, #b3d8ff);
}

.object-item--excluded {
    opacity: 0.55;
}

.object-item__top {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    min-width: 0;
}

.object-item__type {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    line-height: 1.35;
}

.object-item__desc {
    margin-top: 4px;
    font-size: 12px;
    line-height: 1.35;
    color: var(--el-text-color-primary, #303133);
    min-width: 0;
}

.object-item__ext {
    display: block;
    margin-top: 4px;
    min-width: 0;
    font-size: 11px;
    line-height: 1.2;
    color: var(--el-text-color-secondary, #909399);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.object-item__badges {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 5px;
}
</style>
