<template>
    <main>
        <section class="hero">
            <div class="wrap hero-grid">
                <div class="hero-copy">
                    <div class="eyebrow hero-eyebrow">ezBIDS · brainlife.io</div>
                    <h1>Neuroimaging data to BIDS, from scanner folders to shareable datasets.</h1>
                    <p class="lede">
                        ezBIDS maps raw data and its metadata to the Brain Imaging Data Structure with guidance at every
                        step, no coding and no BIDS expertise required. Its new local importer, aimport, adds an AI
                        agent and removes identifying information on your own computer before anything is uploaded.
                    </p>
                    <div class="cta">
                        <button class="btn p" @click="onClickGetStarted">Get started</button>
                        <a class="btn ghost" href="https://brainlife.io/docs/using_ezBIDS/"> Documentation </a>
                        <a class="btn ghost" href="https://brainlife.io/docs/using_aimport/"> About aimport </a>
                    </div>
                    <p class="cite">
                        Levitas et al., <i>Scientific Data</i> 11, 179 (2024) ·
                        <a href="https://www.nature.com/articles/s41597-024-02959-0">read the paper</a>
                    </p>
                </div>
                <div class="hero-art" aria-label="A scanner export organised into a BIDS dataset">
                    <div class="tree">
                        <div class="tree-h mono">scanner export</div>
                        <pre class="mono">
PATIENT_042/
  20240611/
    T1_MPRAGE_SAG_0005/
      IM-0001-0001.dcm
      … 176 files
    EP2D_BOLD_REST_0007/
      IM-0002-0001.dcm
      … 9,600 files
    DTI_64DIR_0011/</pre
                        >
                    </div>
                    <div class="tree-arrow mono" aria-hidden="true">→</div>
                    <div class="tree out">
                        <div class="tree-h mono">BIDS v1.11.2</div>
                        <pre class="mono">
dataset_description.json
participants.tsv
sub-01/
  ses-1/
    anat/sub-01_ses-1_T1w.nii.gz
    func/sub-01_ses-1_task-rest_bold.nii.gz
    dwi/sub-01_ses-1_dwi.nii.gz
        sub-01_ses-1_dwi.bval
        sub-01_ses-1_dwi.bvec</pre
                        >
                    </div>
                </div>
            </div>
        </section>
        <div class="stripe" aria-hidden="true"></div>
        <div class="wrap">
            <dl class="stats">
                <div v-for="s in stats" :key="s.label" class="stat">
                    <dt class="v">{{ s.value }}</dt>
                    <dd>
                        {{ s.label }} <span class="note">· {{ s.note }}</span>
                    </dd>
                </div>
            </dl>
            <p class="funding">Free for researchers · part of brainlife.io, funded by NIH and NSF</p>
        </div>

        <section>
            <div class="wrap">
                <div class="sec-head">
                    <div class="eyebrow">Scales</div>
                    <h2>From nanometres to years, one standard.</h2>
                    <p>
                        The modalities BIDS describes span about eight orders of magnitude in space and thirteen in
                        time, with single acquisitions from kilobytes to terabytes. These are the typical ranges of the
                        data ezBIDS and aimport handle, on logarithmic axes.
                    </p>
                </div>
                <div class="legend">
                    <span><i class="sw now"></i>Supported now</span>
                    <span><i class="sw next"></i>In progress (aimport phases 2–4)</span>
                </div>
                <div class="charts">
                    <ScaleChart
                        eyebrow="Space"
                        caption="Smallest resolved element"
                        :ranges="space"
                        :ticks="spaceTicks"
                    />
                    <ScaleChart
                        eyebrow="Time"
                        caption="Sampling interval of a recording"
                        :ranges="time"
                        :ticks="timeTicks"
                    />
                    <ScaleChart eyebrow="Data" caption="Size of one acquisition" :ranges="size" :ticks="sizeTicks" />
                </div>
                <p class="foot mono">
                    Typical values, order of magnitude. Counts from the BIDS v1.11.2 schema and aimport's
                    bids_brainlife_map.yaml.
                </p>
            </div>
        </section>

        <section class="band">
            <div class="wrap">
                <div class="sec-head">
                    <div class="eyebrow">Coverage</div>
                    <h2>Every BIDS datatype, on the way to brainlife.io.</h2>
                    <p>
                        ezBIDS converts MRI, PET and MEG today. aimport extends it datatype by datatype, and BIDS file
                        types are mapped to brainlife.io datatypes (or drafts of new ones) so the data is ready for Apps
                        as soon as it lands.
                    </p>
                </div>
                <div class="legend">
                    <span><i class="sw now"></i>Supported now</span>
                    <span><i class="sw next"></i>In progress</span>
                </div>
                <div class="grid">
                    <div v-for="d in datatypes" :key="d.id" :class="['dt', d.status]">
                        <div class="dt-top">
                            <span class="dt-id mono">{{ d.id }}</span>
                            <span class="dt-mod mono">{{ d.modality }}</span>
                        </div>
                        <div class="dt-name">{{ d.name }}</div>
                        <div class="dt-meta mono">
                            <span>{{ d.suffixes ? `${d.suffixes} suffixes` : 'tables + sidecars' }}</span>
                            <span>{{ d.where }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section>
            <div class="wrap">
                <div class="sec-head">
                    <div class="eyebrow">New · aimport</div>
                    <h2>An AI agent that never sees your participants.</h2>
                    <p>
                        aimport runs ezBIDS on your own computer, driven from the <span class="mono">bl</span> command
                        line. The agent proposes, you decide, and only validated, de-identified data is uploaded.
                    </p>
                </div>
                <AimportFlow />
                <ul class="facts">
                    <li>
                        <b>Bring your own model.</b> Claude, OpenAI, or Qwen through Ollama, so nothing leaves the
                        machine at all.
                    </li>
                    <li>
                        <b>Metadata too.</b> Participants, phenotype, sessions, scans, README, CHANGES and LICENSE are
                        kept, edited or dropped in review.
                    </li>
                    <li>
                        <b>A pseudonym key you keep.</b> One file per project, never uploaded, so a later import of the
                        same person reuses their ID.
                    </li>
                </ul>
            </div>
        </section>

        <section class="band">
            <div class="wrap">
                <div class="sec-head">
                    <div class="eyebrow">ezBIDS on the web</div>
                    <h2>Guided conversion in the browser.</h2>
                </div>
                <div class="cards">
                    <div v-for="c in cards" :key="c.t" class="card">
                        <div class="t">{{ c.t }}</div>
                        <p>{{ c.d }}</p>
                    </div>
                </div>
            </div>
        </section>
    </main>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { hasJWT, authRequired } from '@/lib';
import ScaleChart from '@/features/landing/landing/ScaleChart.vue';
import AimportFlow from '@/features/landing/landing/AimportFlow.vue';
import { STATS, DATATYPES, SPACE, TIME, SIZE } from '@/features/landing/landing/data';

export default defineComponent({
    components: { ScaleChart, AimportFlow },
    data() {
        return {
            stats: STATS,
            datatypes: DATATYPES,
            space: SPACE,
            time: TIME,
            size: SIZE,
            spaceTicks: [
                { v: 1e-9, label: '1 nm' },
                { v: 1e-6, label: '1 µm' },
                { v: 1e-3, label: '1 mm' },
                { v: 1e-1, label: '10 cm' },
            ],
            timeTicks: [
                { v: 1e-5, label: '10 µs' },
                { v: 1e-3, label: '1 ms' },
                { v: 1, label: '1 s' },
                { v: 3600, label: '1 h' },
                { v: 3.15e8, label: '10 yr' },
            ],
            sizeTicks: [
                { v: 1e3, label: '1 kB' },
                { v: 1e6, label: '1 MB' },
                { v: 1e9, label: '1 GB' },
                { v: 1e12, label: '1 TB' },
                { v: 1e14, label: '100 TB' },
            ],
            cards: [
                {
                    t: 'Nothing to install',
                    d: 'Upload a folder in the browser; ezBIDS runs dcm2niix and its heuristics on the server.',
                },
                {
                    t: 'Imaging, events and metadata',
                    d: 'Task events, participants and sidecars are converted along with the images.',
                },
                {
                    t: 'Guided, not guessed',
                    d: 'Each series gets a proposed BIDS name you accept or correct, checked against the specification.',
                },
                {
                    t: 'Share where you work',
                    d: 'Download the dataset, publish to OpenNeuro, or send it to a brainlife.io project.',
                },
            ],
        };
    },
    computed: {
        ...mapState(['config']),
    },
    methods: {
        onClickGetStarted() {
            if (!authRequired() || hasJWT()) {
                this.$router.push('/dashboard');
                return;
            }

            sessionStorage.setItem('auth_redirect', `${window.location.href}dashboard`);
            window.location.href = (
                this.config as {
                    apihost: string;
                    authSignIn: string;
                    authSignOut: string;
                    debug: boolean;
                }
            ).authSignIn;
        },
    },
});
</script>

<style scoped>
.hero {
    background: var(--hero);
    color: var(--hero-ink);
    padding-block: 40px 64px;
}
.hero-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
    gap: clamp(24px, 4vw, 64px);
    align-items: center;
}
.hero .hero-eyebrow {
    color: var(--hero-accent);
    margin-bottom: 18px;
}
.hero h1 {
    font-size: clamp(1.9rem, 3.4vw + 0.6rem, 3.3rem);
    letter-spacing: -0.03em;
    max-width: 16ch;
    margin-bottom: 20px;
}
.lede {
    font-size: 1.05rem;
    color: var(--hero-muted);
    max-width: 52ch;
}
.cta {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 28px 0 18px;
}
.hero .btn.p {
    background: var(--hero-accent);
    border-color: var(--hero-accent);
    color: var(--hero-accent-ink);
}
.hero .btn.ghost {
    color: var(--hero-ink);
    border-color: rgba(238, 243, 246, 0.3);
}
.cite {
    font-size: 0.82rem;
    color: var(--hero-muted);
}
.hero .cite a {
    color: var(--hero-accent);
}
.hero-art {
    display: grid;
    grid-template-columns: minmax(0, 0.8fr) auto minmax(0, 1.35fr);
    gap: 12px;
    align-items: center;
}
.tree {
    border: 1px solid var(--hero-line);
    border-radius: 10px;
    padding: 12px 14px;
    background: rgba(238, 243, 246, 0.03);
    min-width: 0;
}
.tree.out {
    border-color: var(--hero-accent);
}
.tree-h {
    font-size: 0.66rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--hero-muted);
    margin-bottom: 8px;
}
.tree pre {
    margin: 0;
    font-size: 0.66rem;
    line-height: 1.6;
    color: var(--hero-ink);
    overflow-x: auto;
}
.tree-arrow {
    color: var(--hero-accent);
    font-size: 1.4rem;
}
/* landing-next: the four-colour stripe under the hero, then the numbers on the page background */
.stripe {
    height: 6px;
    background: linear-gradient(
        90deg,
        var(--blue) 0 25%,
        var(--red) 25% 50%,
        var(--orange) 50% 75%,
        var(--yellow) 75% 100%
    );
}
.stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 18px 28px;
    padding-block: 34px 10px;
    margin: 0;
}
.stat dd {
    margin: 6px 0 0;
    font-size: 0.82rem;
    color: var(--muted);
}
.v {
    font-size: clamp(1.5rem, 1.2vw + 1rem, 2rem);
    font-weight: 600;
    letter-spacing: -0.03em;
    line-height: 1;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
}
.note {
    color: var(--muted);
    opacity: 0.85;
}
.funding {
    font-size: 0.85rem;
    color: var(--muted);
    padding-bottom: 26px;
}
.charts {
    display: grid;
    grid-template-columns: 1fr;
    gap: 16px;
    max-width: 1000px;
}
.foot {
    margin-top: 14px;
    font-size: 0.7rem;
    color: var(--muted);
}
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 230px), 1fr));
    gap: 10px;
}
.dt {
    background: var(--bg-2);
    border: 1px solid var(--rule);
    border-left: 4px solid var(--c-now);
    border-radius: 8px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.dt.next {
    border-left: 4px dashed var(--c-next);
}
.dt-top {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
}
.dt-id {
    font-weight: 600;
}
.dt-mod {
    color: var(--muted);
}
.dt-name {
    font-weight: 600;
    font-size: 0.95rem;
}
.dt-meta {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
    font-size: 0.68rem;
    color: var(--muted);
}
.facts {
    list-style: none;
    padding: 0;
    margin: 24px 0 0;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    font-size: 0.9rem;
    color: var(--muted);
}
.facts b {
    color: var(--ink);
}
.cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}
.card {
    background: var(--bg-2);
    border: 1px solid var(--rule);
    border-radius: 10px;
    padding: 18px;
}
.card .t {
    font-weight: 600;
    margin-bottom: 6px;
}
.card p {
    font-size: 0.88rem;
    color: var(--muted);
}
/* between the one-column layout and wide screens the two trees stack, so the paths fit */
@media (min-width: 993px) and (max-width: 1340px) {
    .hero-art {
        grid-template-columns: 1fr;
    }
    .tree-arrow {
        transform: rotate(90deg);
        justify-self: center;
    }
}
@media (max-width: 992px) {
    .hero-grid {
        grid-template-columns: 1fr;
    }
    .facts,
    .cards {
        grid-template-columns: 1fr 1fr;
    }
}
@media (max-width: 600px) {
    .hero-art {
        grid-template-columns: 1fr;
    }
    .tree-arrow {
        transform: rotate(90deg);
        justify-self: center;
    }
    .facts,
    .cards {
        grid-template-columns: 1fr;
    }
}
</style>
