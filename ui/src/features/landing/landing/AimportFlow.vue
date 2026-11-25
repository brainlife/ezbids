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
            <span class="n mono">07</span>
            <span class="t">Upload</span>
            <span class="d"
                >Only the validated, de-identified dataset, after you say yes: BIDS, or brainlife datatypes ready for
                Apps.</span
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
                    t: 'Point at a folder',
                    d: 'DICOM, NIfTI, EEG/MEG recordings, microscopy images, in any layout. It is read, never changed.',
                },
                {
                    t: 'Scan',
                    d: 'dcm2niix, the ezBIDS heuristics and the recording and microscopy readers work out what each file is.',
                },
                {
                    t: 'Plan, with AI suggestions',
                    d: 'An optional model checks each series from de-identified text, never headers or pixels.',
                },
                {
                    t: 'You review and edit',
                    d: 'Names, subjects, sessions, defacing, event names, metadata files. Nothing is written until you approve.',
                },
                {
                    t: 'Convert, de-identify, validate',
                    d: 'Identifiers stripped, faces removed, dates shifted, events coded; BIDS v1.11.2 validator on your machine.',
                },
                {
                    t: 'Look in the QA viewer',
                    d: 'Neuroglancer for images (defaced vs original), a trace viewer for recordings; mark bad channels.',
                },
            ],
        };
    },
});
</script>

<style scoped>
.flow {
    display: grid;
    grid-template-columns: 1fr auto minmax(170px, 0.22fr);
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
    grid-template-columns: repeat(6, 1fr);
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
    font-size: 0.95rem;
    line-height: 1.25;
}
.d {
    font-size: 0.8rem;
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
@media (max-width: 1300px) {
    .steps {
        grid-template-columns: repeat(3, 1fr);
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
