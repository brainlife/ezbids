<template>
    <footer class="site-footer">
        <div class="wrap row">
            <div>
                <div class="fbrand">
                    <img class="mark" :src="brainlifeMark" alt="brainlife.io" />
                    <span class="brand">ezBIDS</span>
                </div>
                <p class="small">
                    Part of <a href="https://brainlife.io/about/" target="_blank">brainlife.io</a>. Free for
                    researchers.
                </p>
            </div>
            <nav class="links mono">
                <a href="https://brainlife.io/docs/using_ezBIDS/" target="_blank">Docs</a>
                <a href="https://brainlife.io/docs/using_aimport/" target="_blank">aimport</a>
                <a href="https://github.com/brainlife/ezbids" target="_blank">GitHub</a>
                <a href="https://bids-specification.readthedocs.io/en/v1.11.2/" target="_blank">BIDS v1.11.2</a>
                <a href="https://brainlife.io/team/" target="_blank">Team</a>
            </nav>
        </div>
        <div class="wrap small mono legal">© Pestillilab. All rights reserved.</div>
    </footer>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

import brainlifeMark from './assets/brainlife-mark.svg';

export default defineComponent({
    data() {
        return { brainlifeMark };
    },
});
</script>

<style scoped>
.site-footer {
    background: var(--hero);
    color: var(--hero-ink);
    padding: 40px 0 28px;
}
.site-footer a {
    color: var(--hero-ink);
}
.row {
    display: flex;
    justify-content: space-between;
    gap: 24px;
    flex-wrap: wrap;
}
.fbrand {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}
.mark {
    height: 26px;
    width: auto;
}
.brand {
    font-weight: 600;
    font-size: 1.1rem;
}
.small {
    font-size: 0.82rem;
    color: var(--hero-muted);
}
.links {
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    font-size: 0.78rem;
}
.legal {
    margin-top: 24px;
    font-size: 0.7rem;
}
</style>
