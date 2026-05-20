<template>
    <header class="objects-intro">
        <h2 class="objects-intro__title">Object Mapping</h2>
        <p class="objects-intro__text">
            Review and refine object-level mappings. Series-level settings are used as defaults, and you can override
            values here when specific objects need different labels or metadata.
        </p>
    </header>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
    name: 'ObjectsIntro',
});
</script>

<style lang="scss" scoped>
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
</style>
