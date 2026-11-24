<template>
    <section class="dashboard-card aimport-entry" aria-labelledby="aimport-entry-title">
        <div>
            <h2 id="aimport-entry-title" class="aimport-entry-title">
                AI import <el-tag size="small" type="warning">beta</el-tag>
            </h2>
            <p class="aimport-entry-sub">
                Convert, de-identify and deface a folder entirely on this computer, with a plan you review before
                anything is written. Nothing is uploaded.
            </p>
        </div>
        <el-button type="primary" size="large" @click="$router.push({ name: 'aimport' })">Start AI import</el-button>
    </section>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({ name: 'DashboardAimport' });
</script>

<style scoped lang="scss">
.dashboard-card {
    background: var(--panel-bg);
    border-radius: var(--panel-radius);
    border: 1px solid var(--line);
    padding: 1.25rem 1.5rem;
}
.aimport-entry {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
}
.aimport-entry-title {
    margin: 0 0 0.35rem;
    font-size: 1.25rem;
    font-weight: 500;
    color: var(--ink);
}
.aimport-entry-sub {
    margin: 0;
    color: var(--ink-2);
    font-size: 0.9rem;
}
</style>
