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
                >
                    <el-tag size="mini" type="info" class="object-list__tag">{{ idx }}</el-tag>
                    <span class="object-list__label">{{ itemPath(object.items) }}</span>
                </button>
            </div>
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
        };
    },
    computed: {
        selectedObject(): IObject | null {
            if (!this.objects.length) return null;
            return this.objects[this.selectedIndex] ?? null;
        },
        niftiPath(): string | null {
            const o = this.selectedObject;
            if (!o?.items?.length) return null;
            for (const item of o.items) {
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

        itemPath(items: IObjectItem[]) {
            let str = '';
            items.forEach((item) => {
                if (str == '') str = item.path;
                else {
                    const strtokens = str.split('.');
                    const pathtokens = item.path.split('.');
                    str += ' / ';
                    for (let i = 0; i < pathtokens.length; ++i) {
                        if (pathtokens[i] == strtokens[i]) continue;
                        else str += '.' + pathtokens[i];
                    }
                }
            });
            return str;
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
    margin: 0;
    padding: 6px 8px;
    text-align: left;
    font: inherit;
    font-size: 12px;
    line-height: 1.35;
    color: var(--el-text-color-primary, #303133);
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
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

.object-list__label {
    word-break: break-word;
    white-space: normal;
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
