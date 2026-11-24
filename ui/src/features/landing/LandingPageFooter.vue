<template>
    <footer class="site-footer">
        <div class="wrap row">
            <span class="fbrand">
                <BrandLockup size="sm" tone="auto" />
                <span class="left">Part of brainlife.io · Pestilli Lab, The University of Texas at Austin</span>
            </span>
            <span class="links">
                <a href="https://brainlife.io/docs/using_ezBIDS/">Docs</a> ·
                <a href="https://brainlife.io/docs/using_aimport/">aimport</a> ·
                <a href="https://github.com/brainlife/ezbids">GitHub</a> ·
                <a href="https://bids-specification.readthedocs.io/en/v1.11.2/">BIDS v1.11.2</a> ·
                <a href="https://brainlife.io/team/">Team</a> ·
                <a href="https://github.com/brainlife/ezbids/blob/master/CREDITS.md">Credits</a>
            </span>
        </div>
    </footer>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import BrandLockup from '@/components/brand/BrandLockup.vue';

export default defineComponent({
    components: { BrandLockup },
});
</script>

<style scoped>
/* landing-next SiteFooter: light, a hairline above, mark and credit left, links right */
.site-footer {
    border-top: 1px solid var(--rule);
    padding-block: 36px;
    font-size: 0.88rem;
    color: var(--muted);
    background: var(--bg);
}
.row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
}
.fbrand {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
}
</style>
