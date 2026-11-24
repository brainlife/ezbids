<template>
    <el-dialog
        :model-value="!!page.url"
        :title="page.title || host"
        :width="frame ? '92%' : '460px'"
        top="4vh"
        custom-class="external-dialog"
        append-to-body
        destroy-on-close
        @close="close"
    >
        <div v-if="page.note" class="note">{{ page.note }}</div>
        <iframe v-if="frame" class="frame" :src="page.url" :title="page.title || host" />
        <p v-else class="blocked">
            <b>{{ host }}</b> doesn't allow being shown inside other sites, so it can only open in a new browser tab.
        </p>
        <template #footer>
            <span class="foot">
                <span v-if="frame" class="url">{{ page.url }}</span>
                <span v-else />
                <span>
                    <el-button size="small" @click="close">{{ frame ? 'Close' : 'Cancel' }}</el-button>
                    <el-button :type="frame ? 'default' : 'primary'" size="small" @click="openTab">
                        Open in a new tab
                    </el-button>
                </span>
            </span>
        </template>
    </el-dialog>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { externalPage, canFrame, closeExternal } from '../../externalPage';

export default defineComponent({
    data() {
        return { page: externalPage };
    },
    computed: {
        frame(): boolean {
            return !!this.page.url && canFrame(this.page.url);
        },
        host(): string {
            try {
                return new URL(this.page.url, window.location.href).hostname;
            } catch {
                return this.page.url;
            }
        },
    },
    methods: {
        close() {
            closeExternal();
        },
        openTab() {
            // the one place ezBIDS opens a window, and only on an explicit click
            window.open(this.page.url, '_blank', 'noopener');
            closeExternal();
        },
    },
});
</script>

<style scoped>
.frame {
    display: block;
    width: 100%;
    height: 76vh;
    border: 1px solid var(--line, #e2e8f0);
    border-radius: var(--panel-radius, 6px);
    background: #fff;
}
.note {
    font-size: 0.85rem;
    color: var(--ink-2, #718096);
    margin-bottom: 10px;
}
.blocked {
    margin: 0;
    word-break: normal;
    line-height: 1.5;
}
.foot > span:last-child {
    white-space: nowrap;
}
.foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}
.url {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.72rem;
    color: var(--ink-2, #718096);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: left;
}
</style>
<style>
.external-dialog .el-dialog__body {
    padding-top: 8px;
    padding-bottom: 8px;
}
</style>
