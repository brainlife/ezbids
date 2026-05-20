<template>
    <splitpanes class="default-theme upload-objects-split">
        <pane :size="30" :min-size="12" class="upload-objects-pane upload-objects-pane--list">
            <div class="object-list">
                <button
                    v-for="(object, idx) in objects"
                    :key="object.idx ?? idx"
                    type="button"
                    class="object-list__item"
                    :class="{ 'object-list__item--active': idx === selectedIndex }"
                    @click="selectObject(idx)"
                    @mouseenter="showTooltip($event, object)"
                    @mousemove="moveTooltip($event)"
                    @mouseleave="hideTooltip"
                >
                    <el-tag size="mini" type="info" class="object-list__tag">{{ idx }}</el-tag>
                    <div class="object-list__body">
                        <span class="object-list__label">{{ listItemPath(object) }}</span>
                        <span v-if="listItemExtension(object)" class="object-list__ext">{{
                            listItemExtension(object)
                        }}</span>
                    </div>
                </button>
            </div>
            <Teleport to="body">
                <div
                    v-show="tooltip.visible"
                    class="object-list__tooltip"
                    :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
                >
                    <span class="object-list__tooltip-path">{{ tooltip.path }}</span>
                    <span v-if="tooltip.extension" class="object-list__tooltip-ext">{{ tooltip.extension }}</span>
                </div>
            </Teleport>
        </pane>
        <pane class="upload-objects-pane upload-objects-pane--main">
            <div class="display-head">
                <el-radio-group v-model="displayTab" size="small">
                    <el-radio-button label="volume">NIfTI viewer</el-radio-button>
                    <el-radio-button label="metadata">Metadata</el-radio-button>
                </el-radio-group>
            </div>
            <div v-if="displayTab === 'metadata'" class="display-body display-body--meta">
                <pre v-if="selectedObject" class="status">{{ selectedObject }}</pre>
            </div>
            <div v-if="displayTab === 'volume'" class="display-body display-body--viz" style="height: 65vh">
                <p v-if="!niftiPath" class="display-hint">No NIfTI file is associated with this object.</p>
                <niivue v-else :path="niftiPath" :open-in-dialog="false" :height="'65vh'" />
            </div>
        </pane>
    </splitpanes>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';
import { Splitpanes, Pane } from 'splitpanes';
import 'splitpanes/dist/splitpanes.css';
import { IObject, IObjectItem } from '@/store/store.types';
import niivue from '@/components/niivue.vue';

type DisplayTab = 'volume' | 'metadata';

export default defineComponent({
    name: 'UploadObjectsPanel',
    components: {
        Splitpanes,
        Pane,
        niivue,
    },
    props: {
        objects: {
            type: Array as PropType<IObject[]>,
            required: true,
        },
    },
    data() {
        return {
            selectedIndex: 0,
            displayTab: 'volume' as DisplayTab,
            tooltip: {
                visible: false,
                path: '',
                extension: '',
                x: 0,
                y: 0,
            },
        };
    },
    computed: {
        selectedObject(): IObject | null {
            if (!this.objects.length) return null;
            return this.objects[this.selectedIndex] ?? null;
        },
        niftiPath(): string | null {
            const o = this.selectedObject;
            const items = this.normalizeItems(o?.items);
            if (!items.length) return null;
            for (const item of items) {
                const p = item.path.toLowerCase();
                if (p.endsWith('.nii.gz') || p.endsWith('.nii')) return item.path;
            }
            return null;
        },
    },
    watch: {
        objects: {
            handler() {
                if (this.selectedIndex >= this.objects.length) {
                    this.selectedIndex = Math.max(0, this.objects.length - 1);
                }
            },
            deep: true,
        },
    },
    methods: {
        selectObject(idx: number) {
            this.selectedIndex = idx;
        },

        listItemPath(object: IObject) {
            return this.itemPath(this.normalizeItems(object.items));
        },

        listItemExtension(object: IObject) {
            return this.itemExtension(this.normalizeItems(object.items));
        },

        showTooltip(event: MouseEvent, object: IObject) {
            this.tooltip.path = this.listItemPath(object);
            this.tooltip.extension = this.listItemExtension(object);
            this.tooltip.visible = true;
            this.moveTooltip(event);
        },

        moveTooltip(event: MouseEvent) {
            if (!this.tooltip.visible) return;
            this.tooltip.x = event.clientX + 12;
            this.tooltip.y = event.clientY + 12;
        },

        hideTooltip() {
            this.tooltip.visible = false;
        },

        normalizeItems(items: IObjectItem[] | IObjectItem | undefined): IObjectItem[] {
            if (!items) return [];
            return Array.isArray(items) ? items : [items];
        },

        itemPath(items: IObjectItem[]) {
            let str = '';
            items.forEach((item) => {
                const itemPath = item.path || item.name || '';
                if (str == '') str = itemPath;
                else {
                    const strtokens = str.split('.');
                    const pathtokens = itemPath.split('.');
                    str += ' / ';
                    for (let i = 0; i < pathtokens.length; ++i) {
                        if (pathtokens[i] == strtokens[i]) continue;
                        else str += '.' + pathtokens[i];
                    }
                }
            });
            return str;
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
    },
});
</script>

<style lang="scss" scoped>
.upload-objects-split {
    width: 100%;
    max-width: 100%;
    margin-top: 1rem;
    margin-bottom: 1rem;
    min-height: 420px;
}

.upload-objects-pane {
    display: flex;
    flex-direction: column;
    min-height: 0;
}

.upload-objects-pane--list {
    border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
}

.object-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 4px 6px 8px 0;
    overflow-y: auto;
    max-height: 70vh;
}

.object-list__item {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    width: 100%;
    height: 60px;
    min-height: 60px;
    max-height: 60px;
    margin: 0;
    padding: 6px 8px;
    box-sizing: border-box;
    text-align: left;
    font: inherit;
    font-size: 12px;
    line-height: 1.35;
    color: var(--el-text-color-primary, #303133);
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    overflow: hidden;
}

.object-list__item:hover {
    background: var(--el-fill-color-light, #f5f7fa);
}

.object-list__item--active {
    background: var(--el-color-primary-light-9, #ecf5ff);
    border-color: var(--el-color-primary-light-7, #b3d8ff);
}

.object-list__tag {
    flex-shrink: 0;
}

.object-list__body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    overflow: hidden;
}

.object-list__label {
    word-break: break-word;
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
}

.object-list__ext {
    flex-shrink: 0;
    font-size: 11px;
    line-height: 1.2;
    color: var(--el-text-color-secondary, #909399);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.upload-objects-pane--main {
    padding-left: 8px;
}

.display-head {
    flex-shrink: 0;
    margin: 10px 0;
}

.display-body {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
}

.display-body--meta {
    overflow: auto;
    max-height: 65vh;
}

.display-body--viz {
    position: relative;
    align-items: stretch;
}

.display-hint {
    margin: 0;
    color: var(--el-text-color-secondary, #909399);
    font-size: 13px;
}

pre.status {
    flex: 1;
    margin: 0;
    padding: 10px;
    border-radius: 5px;
    background-color: #666;
    color: #fff;
    overflow: auto;
    word-break: break-all;
    min-height: 320px;
}
</style>

<style lang="scss">
.object-list__tooltip {
    position: fixed;
    z-index: 10000;
    max-width: min(480px, 90vw);
    padding: 8px 10px;
    border-radius: 4px;
    background: var(--el-text-color-primary, #303133);
    color: #fff;
    font-size: 12px;
    line-height: 1.4;
    pointer-events: none;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
}

.object-list__tooltip-path {
    display: block;
    word-break: break-word;
    white-space: normal;
}

.object-list__tooltip-ext {
    display: block;
    margin-top: 4px;
    color: var(--el-text-color-placeholder, #c0c4cc);
    font-size: 11px;
}
</style>
