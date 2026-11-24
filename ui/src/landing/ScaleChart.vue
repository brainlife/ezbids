<template>
    <figure class="scale-chart">
        <figcaption>
            <span class="eyebrow">{{ eyebrow }}</span>
            <span class="cap">{{ caption }}</span>
        </figcaption>
        <div class="scroll">
            <svg
                :viewBox="`0 0 ${W} ${height}`"
                role="img"
                :aria-label="`${eyebrow}: ${caption}`"
                preserveAspectRatio="xMinYMin meet"
                @mouseleave="hover = null"
            >
                <g class="grid">
                    <line v-for="t in ticks" :key="t.v" :x1="x(t.v)" :x2="x(t.v)" :y1="0" :y2="plotH" />
                </g>
                <g v-for="(r, i) in ranges" :key="r.label" @mouseenter="hover = i" @focus="hover = i" tabindex="0">
                    <rect class="hit" :x="0" :y="i * ROW" :width="W" :height="ROW" />
                    <text
                        class="row-label"
                        :x="LABEL_W - 12"
                        :y="i * ROW + ROW / 2"
                        text-anchor="end"
                        dominant-baseline="middle"
                    >
                        {{ r.label }}
                    </text>
                    <rect
                        :class="['bar', r.status, { on: hover === i }]"
                        :x="x(r.lo)"
                        :y="i * ROW + (ROW - BAR) / 2"
                        :width="Math.max(x(r.hi) - x(r.lo), 6)"
                        :height="BAR"
                        rx="4"
                    />
                </g>
                <g class="axis">
                    <line :x1="LABEL_W" :x2="W - PAD_R" :y1="plotH" :y2="plotH" />
                    <text v-for="t in ticks" :key="t.v" :x="x(t.v)" :y="plotH + 18" text-anchor="middle">
                        {{ t.label }}
                    </text>
                </g>
            </svg>
        </div>
        <div v-if="hover !== null" class="tip" role="status">
            <b>{{ ranges[hover].label }}</b>
            <span>{{ ranges[hover].note }}</span>
            <span class="tip-status">{{ ranges[hover].status === 'now' ? 'Supported now' : 'In progress' }}</span>
        </div>
        <details class="table-view">
            <summary>Show as a table</summary>
            <table>
                <thead>
                    <tr>
                        <th>{{ rowHead }}</th>
                        <th>Typical range</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="r in ranges" :key="r.label">
                        <td>{{ r.label }}</td>
                        <td>{{ r.note }}</td>
                        <td>{{ r.status === 'now' ? 'Supported now' : 'In progress' }}</td>
                    </tr>
                </tbody>
            </table>
        </details>
    </figure>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';
import type { Range } from './data';

// a ranged-bar chart on a log10 axis: one row per modality, a bar from lo to hi
export default defineComponent({
    props: {
        eyebrow: { type: String, required: true },
        caption: { type: String, required: true },
        rowHead: { type: String, default: 'Modality' },
        ranges: { type: Array as PropType<Range[]>, required: true },
        ticks: { type: Array as PropType<{ v: number; label: string }[]>, required: true },
    },
    data() {
        return { hover: null as number | null, W: 960, ROW: 26, BAR: 10, LABEL_W: 150, PAD_R: 16 };
    },
    computed: {
        plotH(): number {
            return this.ranges.length * this.ROW;
        },
        height(): number {
            return this.plotH + 28;
        },
        domain(): [number, number] {
            const vs = this.ticks.map((t) => Math.log10(t.v));
            return [Math.min(...vs), Math.max(...vs)];
        },
    },
    methods: {
        x(v: number): number {
            const [a, b] = this.domain;
            return this.LABEL_W + ((Math.log10(v) - a) / (b - a)) * (this.W - this.LABEL_W - this.PAD_R);
        },
    },
});
</script>

<style scoped>
.scale-chart {
    margin: 0;
    position: relative;
    background: var(--bg-2);
    border: 1px solid var(--rule);
    border-radius: 10px;
    padding: 18px 18px 12px;
}
figcaption {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 12px;
}
.cap {
    font-size: 0.95rem;
    font-weight: 600;
}
svg {
    width: 100%;
    min-width: 560px; /* small screens scroll the chart sideways; the table view is the alternative */
    height: auto;
    display: block;
    overflow: visible;
}
.scroll {
    overflow-x: auto;
}
.grid line {
    stroke: var(--rule);
    stroke-width: 1;
}
.axis line {
    stroke: var(--line);
}
.axis text,
.row-label {
    font-family: var(--mono);
    font-size: 11px;
    fill: var(--muted);
}
.row-label {
    font-family: var(--font);
    font-size: 12.5px;
    fill: var(--ink);
}
.hit {
    fill: transparent;
}
g:focus {
    outline: none;
}
g:focus .row-label {
    text-decoration: underline;
}
.bar {
    stroke-width: 2;
}
.bar.now {
    fill: var(--c-now);
    stroke: var(--c-now);
}
.bar.next {
    fill: var(--c-next-fill);
    stroke: var(--c-next);
    stroke-dasharray: 4 3;
}
.bar.on {
    filter: brightness(1.12);
}
.tip {
    position: absolute;
    right: 18px;
    top: 14px;
    max-width: 60%;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 0.8rem;
    display: flex;
    flex-direction: column;
    pointer-events: none;
}
.tip-status {
    font-family: var(--mono);
    font-size: 0.68rem;
    color: var(--muted);
}
.table-view {
    margin-top: 8px;
    font-size: 0.82rem;
}
.table-view summary {
    cursor: pointer;
    color: var(--link);
    font-family: var(--mono);
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
}
th,
td {
    text-align: left;
    padding: 4px 6px;
    border-bottom: 1px solid var(--rule);
}
</style>
