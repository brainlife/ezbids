<template>
    <section id="try" class="try">
        <div class="wrap">
            <div class="sec-head">
                <div class="eyebrow">Try it · low-stakes examples</div>
                <h2>Try aimport on public sample data first.</h2>
                <p>
                    Three small walkthroughs on tiny, openly licensed test files, so nothing personal is at risk. Each
                    one stops before upload (<span class="mono">--no-upload</span>) and opens the local QA viewer (<span
                        class="mono"
                        >--qa</span
                    >). Set up once, as in <a :href="examples">aimport/EXAMPLES.md</a>.
                </p>
            </div>
            <div class="setup">
                <div class="k mono">Once: the engine and bl, from source (beta)</div>
                <pre class="mono"><code>{{ setup }}</code></pre>
            </div>
            <div class="ex">
                <article v-for="e in list" :key="e.id" class="card">
                    <div class="k mono">{{ e.id }}</div>
                    <h3>{{ e.t }}</h3>
                    <p class="src">
                        <a :href="e.dataHref">{{ e.data }}</a> · {{ e.licence }}
                    </p>
                    <pre class="mono"><code>{{ e.cmd }}</code></pre>
                    <div class="k mono">What you should see</div>
                    <ul>
                        <li v-for="o in e.outcome" :key="o">{{ o }}</li>
                    </ul>
                </article>
            </div>
            <p class="more">
                Full steps, expected output and what to check: <a :href="examples">aimport/EXAMPLES.md</a>. Prefer no
                command line? <a :href="desktop">ezBIDS desktop</a> (beta, Mac) runs the same engine in an app.
            </p>
        </div>
    </section>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { EXAMPLES, EXAMPLES_URL, EXAMPLES_SETUP, REPO } from '@/features/landing/landing/data';

export default defineComponent({
    data() {
        return {
            list: EXAMPLES,
            setup: EXAMPLES_SETUP,
            examples: EXAMPLES_URL,
            desktop: `${REPO}#ezbids-desktop`,
        };
    },
});
</script>

<style scoped>
.k {
    font-size: 0.68rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
}
pre {
    margin: 8px 0 14px;
    padding: 12px 14px;
    background: var(--hero);
    color: var(--hero-ink);
    border-radius: 8px;
    font-size: 0.74rem;
    line-height: 1.55;
    overflow-x: auto;
    white-space: pre;
}
.setup {
    max-width: 900px;
    min-width: 0;
    margin-bottom: 20px;
}
.ex {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
}
.card {
    background: var(--bg-2);
    border: 1px solid var(--rule);
    border-radius: 10px;
    padding: 18px;
    min-width: 0;
    display: flex;
    flex-direction: column;
}
.card h3 {
    font-size: 1.1rem;
    margin: 4px 0 6px;
}
.src {
    font-size: 0.8rem;
    color: var(--muted);
}
.card ul {
    margin: 6px 0 0;
    padding-left: 18px;
    font-size: 0.86rem;
    color: var(--muted);
}
.more {
    margin-top: 20px;
    font-size: 0.9rem;
    color: var(--muted);
}
@media (max-width: 1100px) {
    .ex {
        grid-template-columns: minmax(0, 1fr);
    }
}
</style>
