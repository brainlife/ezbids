<template>
    <div class="flow" role="list" aria-label="How aimport moves data from your computer to brainlife.io">
        <div class="local">
            <div class="zone mono">Your computer · nothing identifying leaves it</div>
            <ol class="steps">
                <li v-for="(s, i) in steps" :key="s.t" class="step" role="listitem">
                    <span class="n mono">{{ String(i + 1).padStart(2, '0') }}</span>
                    <span class="t">{{ s.t }}</span>
                    <span class="d">{{ s.d }}</span>
                </li>
            </ol>
        </div>
        <div class="arrow" aria-hidden="true">
            <svg viewBox="0 0 40 24"><path d="M2 12h32M26 4l8 8-8 8" /></svg>
        </div>
        <div class="remote" role="listitem">
            <div class="zone mono">brainlife.io</div>
            <span class="t">Upload</span>
            <span class="d"
                >Only the validated, de-identified dataset: BIDS, or brainlife datatypes ready for Apps.</span
            >
        </div>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
    data() {
        return {
            steps: [
                {
                    t: 'Scan',
                    d: 'MRI as DICOM or NIfTI (dcm2niix and the ezBIDS heuristics), microscopy images and EEG, MEG, iEEG, NIRS or EMG recordings.',
                },
                {
                    t: 'Agent review',
                    d: 'Claude, OpenAI or a local Qwen model checks every series. It sees summaries with identifiers replaced by [x], never images or headers.',
                },
                {
                    t: 'You approve',
                    d: 'A plan of names, subjects, sessions, defacing and metadata files. Nothing is written until you approve it.',
                },
                {
                    t: 'De-identify',
                    d: 'Identifying fields dropped, subjects pseudonymised, dates shifted, faces removed losslessly.',
                },
                {
                    t: 'Validate',
                    d: 'BIDS validator (v1.11.2) and the brainlife datatype validators, run on your machine; image and trace viewers to check the result.',
                },
            ],
        };
    },
});
</script>

<style scoped>
.flow {
    display: grid;
    grid-template-columns: 1fr auto minmax(180px, 0.28fr);
    gap: 14px;
    align-items: stretch;
}
.local,
.remote {
    border-radius: 10px;
    padding: 16px;
}
.local {
    border: 1.5px dashed var(--c-now);
    background: color-mix(in srgb, var(--c-now) 6%, transparent);
}
.remote {
    border: 1px solid var(--line);
    background: var(--bg-2);
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.zone {
    font-size: 0.66rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 12px;
}
.steps {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
}
.step {
    background: var(--bg-2);
    border: 1px solid var(--rule);
    border-radius: 8px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.n {
    font-size: 0.7rem;
    color: var(--accent);
}
.t {
    font-weight: 600;
    font-size: 0.98rem;
}
.d {
    font-size: 0.82rem;
    color: var(--muted);
    line-height: 1.45;
}
.arrow {
    display: flex;
    align-items: center;
}
.arrow svg {
    width: 40px;
    fill: none;
    stroke: var(--muted);
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}
@media (max-width: 1100px) {
    .steps {
        grid-template-columns: repeat(2, 1fr);
    }
}
@media (max-width: 760px) {
    .flow {
        grid-template-columns: 1fr;
    }
    .arrow {
        justify-content: center;
        transform: rotate(90deg);
    }
    .steps {
        grid-template-columns: 1fr;
    }
}
</style>
