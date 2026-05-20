<template>
    <div class="empty-state">
        <div class="empty-state__card">
            <p>Please make sure all subject/session/series mappings are correctly applied to your data.</p>
            <p>
                Please select an object from the left list to inspect and edit datatype, entities, and related metadata.
            </p>
        </div>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
    name: 'ObjectsEmptyState',
});
</script>

<style lang="scss" scoped>
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
</style>
