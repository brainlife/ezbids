<template>
    <section id="aimport" class="band aimport">
        <div class="wrap">
            <div class="head">
                <div class="sec-head">
                    <div class="eyebrow">New · aimport <span class="beta mono">beta</span></div>
                    <h2>AI import, privacy first.</h2>
                    <p>
                        aimport turns a folder of raw neuroscience data on your own computer into a validated,
                        de-identified BIDS dataset, with an AI agent that suggests and you deciding, before anything is
                        uploaded to brainlife.io.
                    </p>
                    <p class="status mono">{{ status }}</p>
                    <div class="cta">
                        <a class="btn p" href="#try" @click.prevent="scrollToTry">Try it with sample data</a>
                        <a class="btn ghost" :href="readme">How aimport works</a>
                    </div>
                </div>
                <ul class="privacy" aria-label="Privacy promise">
                    <li v-for="p in privacy" :key="p.t">
                        <svg class="tick" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3 3 7-7" /></svg>
                        <span
                            ><b>{{ p.t }}</b> {{ p.d }}</span
                        >
                    </li>
                </ul>
            </div>

            <h3 class="sub">How it works</h3>
            <AimportFlow />

            <div class="info">
                <div class="box">
                    <h3>What it needs</h3>
                    <div v-for="n in needs" :key="n.t" class="need">
                        <div class="k mono">{{ n.t }}</div>
                        <ul>
                            <li v-for="i in n.items" :key="i">{{ i }}</li>
                        </ul>
                    </div>
                </div>
                <div class="box">
                    <h3>Which data</h3>
                    <div v-for="d in data" :key="d.t" class="need">
                        <div class="k mono">{{ d.t }}</div>
                        <p>{{ d.d }}</p>
                    </div>
                </div>
            </div>
        </div>
    </section>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import AimportFlow from '@/features/landing/landing/AimportFlow.vue';
import { PRIVACY, NEEDS, WHICH_DATA, AIMPORT_STATUS, AIMPORT_README_URL } from '@/features/landing/landing/data';

export default defineComponent({
    components: { AimportFlow },
    data() {
        return {
            privacy: PRIVACY,
            needs: NEEDS,
            data: WHICH_DATA,
            status: AIMPORT_STATUS,
            readme: AIMPORT_README_URL,
        };
    },
    methods: {
        // not a plain #hash: in the desktop app (hash history) that would be a route
        scrollToTry() {
            document.getElementById('try')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
    },
});
</script>

<style scoped>
.head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
    gap: clamp(24px, 4vw, 56px);
    align-items: start;
    margin-bottom: 40px;
}
.head .sec-head {
    margin-bottom: 0;
}
.beta {
    display: inline-block;
    margin-left: 6px;
    padding: 1px 7px;
    border-radius: 4px;
    border: 1px solid var(--c-next);
    color: var(--c-next);
    font-size: 0.62rem;
    letter-spacing: 0.12em;
}
.status {
    font-size: 0.8rem;
    color: var(--ink);
}
.cta {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 6px;
}
.privacy {
    list-style: none;
    margin: 0;
    padding: 20px 22px;
    border: 1.5px dashed var(--c-now);
    border-radius: 10px;
    background: color-mix(in srgb, var(--c-now) 6%, var(--bg-2));
    display: grid;
    gap: 12px;
    font-size: 0.9rem;
    color: var(--muted);
}
.privacy li {
    display: grid;
    grid-template-columns: 18px 1fr;
    gap: 10px;
    align-items: start;
}
.privacy b {
    color: var(--ink);
}
.tick {
    width: 16px;
    height: 16px;
    margin-top: 4px;
    fill: none;
    stroke: var(--c-now);
    stroke-width: 2.2;
    stroke-linecap: round;
    stroke-linejoin: round;
}
.sub {
    font-size: 1.15rem;
    margin-bottom: 14px;
}
.info {
    display: grid;
    grid-template-columns: 1.3fr 1fr;
    gap: 16px;
    margin-top: 24px;
}
.box {
    background: var(--bg-2);
    border: 1px solid var(--rule);
    border-radius: 10px;
    padding: 18px 20px;
}
.box h3 {
    font-size: 1.05rem;
    margin-bottom: 10px;
}
.need + .need {
    margin-top: 10px;
}
.k {
    font-size: 0.68rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
}
.need ul {
    margin: 4px 0 0;
    padding-left: 18px;
}
.need li,
.need p {
    font-size: 0.88rem;
    color: var(--muted);
}
@media (max-width: 992px) {
    .head,
    .info {
        grid-template-columns: 1fr;
    }
}
</style>
