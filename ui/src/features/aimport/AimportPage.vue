<template>
    <div class="aimport-root">
        <header class="aimport-header">
            <div class="aimport-logo">
                <a href="https://brainlife.io" target="_blank" rel="noopener noreferrer" aria-label="brainlife.io">
                    <img src="@/assets/brainlife-mark-light.svg" class="aimport-logo-mark" alt="brainlife.io" />
                </a>
                <h1>ezBIDS <span class="aimport-by">by brainlife.io</span></h1>
                <el-tag size="small" type="warning" class="aimport-beta">AI import (beta)</el-tag>
            </div>
            <el-button size="small" @click="$router.push({ name: 'dashboard' })">Back to dashboard</el-button>
        </header>

        <main class="aimport-main">
            <el-steps :active="stepIndex" finish-status="success" align-center class="aimport-steps">
                <el-step title="Folder" />
                <el-step title="Scan" />
                <el-step title="Review plan" />
                <el-step title="Convert & validate" />
                <el-step title="Check & result" />
            </el-steps>

            <el-alert v-if="error" type="error" :title="error" show-icon class="aimport-alert" @close="error = ''" />

            <!-- 1. folder -->
            <section v-if="!inputDir" class="aimport-card">
                <h2>Import a folder with AI help, on this computer</h2>
                <p class="aimport-sub">
                    Pick a folder of DICOM or NIfTI data. aimport works out each series, converts to BIDS, removes
                    identifiers and defaces anatomical images. Everything runs on this computer; nothing is
                    uploaded. No AI model is used unless one is configured, so by default nothing is sent anywhere.
                </p>
                <div class="aimport-row">
                    <span class="aimport-label">Project ID</span>
                    <el-input v-model="projectId" class="aimport-project" placeholder="my-project" />
                    <small>names the pseudonym key, so a later import of the same person gets the same ID</small>
                </div>
                <el-button type="primary" size="large" :loading="starting" @click="pickFolder">
                    Choose folder…
                </el-button>
            </section>

            <template v-else>
                <section class="aimport-card aimport-folder">
                    <div>
                        <span class="aimport-label">Folder</span>
                        <code>{{ inputDir }}</code>
                        <span class="aimport-label">Project</span>
                        <code>{{ projectId }}</code>
                    </div>
                    <el-button size="small" :disabled="busy" @click="reset">Choose another folder</el-button>
                </section>

                <!-- 2. scan -->
                <section v-if="stage === 'idle' || stage === 'failed'" class="aimport-card">
                    <el-alert
                        v-if="stage === 'failed'"
                        type="error"
                        :title="status.message || 'failed'"
                        :closable="false"
                        show-icon
                    />
                    <p class="aimport-sub">Scan reads the folder, runs ezBIDS and builds a plan for you to review.</p>
                    <el-button type="primary" @click="scan">Scan folder</el-button>
                </section>

                <section v-if="stage === 'scanning' || stage === 'executing'" class="aimport-card aimport-busy">
                    <font-awesome-icon icon="spinner" pulse size="2x" />
                    <div>
                        <h3>{{ stage === 'scanning' ? 'Scanning' : 'Converting, defacing and validating' }}</h3>
                        <p class="aimport-sub">{{ status.message }}</p>
                    </div>
                </section>

                <!-- 3. plan review -->
                <section v-if="stage === 'planned' && plan" class="aimport-card">
                    <div class="aimport-plan-head">
                        <h2>Review the plan</h2>
                        <span class="aimport-sub">
                            {{ includedCount }} of {{ plan.entries.length }} series will be written. Every field can be
                            edited; nothing is written until you approve.
                        </span>
                    </div>
                    <el-alert
                        v-for="w in plan.warnings"
                        :key="w"
                        type="warning"
                        :title="w"
                        :closable="false"
                        class="aimport-alert"
                    />
                    <el-table :data="plan.entries" size="small" class="aimport-table" :row-class-name="rowClass">
                        <el-table-column label="Status" width="120">
                            <template #default="{ row }">
                                <el-tag :type="statusTag(row)" size="small">{{ statusLabel(row) }}</el-tag>
                            </template>
                        </el-table-column>
                        <el-table-column label="Series (de-identified)" min-width="150">
                            <template #default="{ row }">
                                <span class="aimport-desc">{{ row.description }}</span>
                            </template>
                        </el-table-column>
                        <el-table-column label="BIDS fields (sub, ses, datatype, suffix, entities)" min-width="470">
                            <template #default="{ row }">
                                <div class="aimport-bids">
                                    <label>sub-</label>
                                    <el-input
                                        v-model="row.subject"
                                        size="small"
                                        class="w-sub"
                                        @change="edit(row, { subject: row.subject })"
                                    />
                                    <label>ses-</label>
                                    <el-input
                                        v-model="row.session"
                                        size="small"
                                        class="w-sub"
                                        @change="edit(row, { session: row.session || null })"
                                    />
                                    <el-input
                                        v-model="row.datatype"
                                        size="small"
                                        class="w-dt"
                                        placeholder="datatype"
                                        @change="edit(row, { datatype: row.datatype || null })"
                                    />
                                    <el-input
                                        v-model="row.suffix"
                                        size="small"
                                        class="w-dt"
                                        placeholder="suffix"
                                        @change="edit(row, { suffix: row.suffix || null })"
                                    />
                                    <el-input
                                        v-model="entityText[row.id]"
                                        size="small"
                                        class="w-ent"
                                        placeholder="task=rest run=1"
                                        @change="editEntities(row, entityText[row.id])"
                                    />
                                </div>
                            </template>
                        </el-table-column>
                        <el-table-column label="Deface" width="70" align="center">
                            <template #default="{ row }">
                                <el-checkbox v-model="row.deface" @change="edit(row, { deface: row.deface })" />
                            </template>
                        </el-table-column>
                        <el-table-column label="Exclude" width="75" align="center">
                            <template #default="{ row }">
                                <el-checkbox
                                    v-model="row.exclude"
                                    @change="edit(row, { exclude: row.exclude })"
                                />
                            </template>
                        </el-table-column>
                        <el-table-column label="Why" min-width="220">
                            <template #default="{ row }">
                                <el-tooltip :content="row.reason" placement="top" :show-after="300">
                                    <span class="aimport-reason">
                                        <el-tag size="small" type="info">{{ row.source }}</el-tag>
                                        {{ row.agent_note || row.reason }}
                                    </span>
                                </el-tooltip>
                            </template>
                        </el-table-column>
                    </el-table>

                    <div class="aimport-approve">
                        <div class="aimport-row">
                            <span class="aimport-label">Dataset name</span>
                            <el-input
                                v-model="plan.dataset_name"
                                class="aimport-project"
                                @change="editPlan({ dataset_name: plan.dataset_name })"
                            />
                        </div>
                        <div class="aimport-row">
                            <span class="aimport-label">Defacing</span>
                            <el-select v-model="defaceMethod" size="small" class="aimport-select">
                                <el-option label="allineate face mask (ezBIDS desktop)" value="allineate" />
                                <el-option label="pydeface (needs FSL: not in the desktop app)" value="pydeface" disabled />
                                <el-option label="quickshear (needs ROBEX: not in the desktop app)" value="quickshear" disabled />
                            </el-select>
                        </div>
                        <el-button type="primary" size="large" :loading="approving" @click="approveAndRun">
                            Approve and convert
                        </el-button>
                    </div>
                </section>

                <!-- 5. result -->
                <section v-if="(stage === 'validated' || stage === 'invalid') && status.validation" class="aimport-card">
                    <el-alert
                        v-if="stage === 'validated'"
                        type="success"
                        :closable="false"
                        show-icon
                        :title="`BIDS validation passed: 0 errors, ${status.validation.warning_count} warnings`"
                    />
                    <el-alert
                        v-else
                        type="error"
                        :closable="false"
                        show-icon
                        :title="`BIDS validation found ${status.validation.error_count} errors: fix the plan and convert again. This output must not be uploaded.`"
                    />
                    <p class="aimport-sub">
                        @bids/validator {{ status.validation.validator_version }}, BIDS
                        {{ status.validation.bids_version }}. Output folder:
                        <code>{{ status.output_dir }}</code>
                    </p>
                    <div class="aimport-actions">
                        <el-button type="primary" @click="openViewer">Open QA viewer</el-button>
                        <el-button @click="showOutput">Show output folder</el-button>
                        <el-button @click="backToPlan">Edit the plan</el-button>
                    </div>

                    <h3 v-if="status.validation.errors.length">Errors</h3>
                    <ul class="aimport-issues">
                        <li v-for="(i, n) in status.validation.errors" :key="'e' + n">
                            <b>{{ i.code }}</b> {{ i.message }} <code v-for="f in i.files" :key="f">{{ f }}</code>
                        </li>
                    </ul>

                    <h3>Files written</h3>
                    <ul class="aimport-files">
                        <li v-for="f in writtenFiles" :key="f"><code>{{ f }}</code></li>
                    </ul>

                    <el-collapse>
                        <el-collapse-item :title="`Warnings (${groupedWarnings.length} kinds)`">
                            <ul class="aimport-issues">
                                <li v-for="w in groupedWarnings" :key="w.code">
                                    <b>{{ w.code }}</b> × {{ w.count }}
                                </li>
                            </ul>
                        </el-collapse-item>
                    </el-collapse>
                    <p class="aimport-later">Uploading the result to brainlife.io comes in a later version.</p>
                </section>
            </template>
        </main>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { engine, EngineError, Plan, PlanEntry, Stage, Status } from './aimportClient';

const POLL_MS = 1500;

export default defineComponent({
    name: 'AimportPage',

    data() {
        return {
            inputDir: '' as string,
            projectId: 'my-project',
            starting: false,
            approving: false,
            status: { stage: 'idle' } as Status,
            plan: null as Plan | null,
            defaceMethod: 'allineate',
            error: '',
            timer: 0 as number,
            entityText: {} as Record<string, string>,
        };
    },

    computed: {
        stage(): Stage {
            return this.status.stage;
        },
        busy(): boolean {
            return this.stage === 'scanning' || this.stage === 'executing';
        },
        stepIndex(): number {
            if (!this.inputDir) return 0;
            return { idle: 1, failed: 1, scanning: 1, planned: 2, executing: 3, validated: 5, invalid: 4 }[this.stage];
        },
        includedCount(): number {
            return this.plan ? this.plan.entries.filter((e) => !e.exclude).length : 0;
        },
        writtenFiles(): string[] {
            return Object.values(this.status.manifest || {})
                .flat()
                .sort();
        },
        groupedWarnings(): { code: string; count: number }[] {
            const counts: Record<string, number> = {};
            for (const w of this.status.validation?.warnings || []) counts[w.code] = (counts[w.code] || 0) + 1;
            return Object.entries(counts).map(([code, count]) => ({ code, count }));
        },
    },

    watch: {
        plan(plan: Plan | null) {
            this.entityText = {};
            for (const e of plan?.entries || []) this.entityText[e.id] = this.entitiesText(e);
        },
    },

    beforeUnmount() {
        window.clearTimeout(this.timer);
    },

    methods: {
        fail(err: unknown) {
            this.error = err instanceof EngineError || err instanceof Error ? err.message : String(err);
        },

        async pickFolder() {
            this.error = '';
            const dir = await engine.pickFolder();
            if (!dir) return;
            this.starting = true;
            try {
                const res = await engine.start(dir);
                if (!res.ok) throw new Error(res.error || 'could not start the AI import engine');
                this.inputDir = res.inputDir || dir;
                await this.refresh();
            } catch (err) {
                this.fail(err);
            } finally {
                this.starting = false;
            }
        },

        reset() {
            window.clearTimeout(this.timer);
            this.inputDir = '';
            this.plan = null;
            this.status = { stage: 'idle' };
        },

        async refresh() {
            window.clearTimeout(this.timer);
            try {
                this.status = await engine.status();
                if (this.stage === 'planned' && !this.plan) this.plan = await engine.plan();
            } catch (err) {
                this.fail(err);
                return;
            }
            if (this.busy) this.timer = window.setTimeout(() => this.refresh(), POLL_MS);
        },

        async scan() {
            this.error = '';
            this.plan = null;
            try {
                await engine.scan(this.projectId);
                await this.refresh();
            } catch (err) {
                this.fail(err);
            }
        },

        async editPlan(body: Record<string, unknown>) {
            this.error = '';
            try {
                this.plan = await engine.edit(body);
            } catch (err) {
                this.fail(err);
                this.plan = await engine.plan(); // a refused edit changes nothing: show the plan as it is
            }
        },

        edit(row: PlanEntry, change: Record<string, unknown>) {
            return this.editPlan({ edits: [{ id: row.id, ...change }] });
        },

        editEntities(row: PlanEntry, text: string) {
            const entities: Record<string, string> = {};
            for (const part of text.split(/[\s,]+/).filter(Boolean)) {
                const [k, v] = part.split('=');
                if (k && v) entities[k] = v;
            }
            return this.edit(row, { entities });
        },

        entitiesText(row: PlanEntry): string {
            return Object.entries(row.entities || {})
                .map(([k, v]) => `${k}=${v}`)
                .join(' ');
        },

        statusLabel(row: PlanEntry): string {
            if (row.exclude) return 'excluded';
            return { ok: 'ok', unknown: 'unknown', unsupported: 'unsupported', excluded_by_default: 'excluded' }[
                row.status
            ];
        },

        statusTag(row: PlanEntry): string {
            if (row.exclude) return 'info';
            return row.status === 'ok' ? 'success' : 'warning';
        },

        rowClass({ row }: { row: PlanEntry }): string {
            return row.exclude ? 'aimport-row-excluded' : '';
        },

        async approveAndRun() {
            this.error = '';
            this.approving = true;
            try {
                await engine.approve(this.defaceMethod);
                await engine.execute();
                this.plan = null;
                await this.refresh();
            } catch (err) {
                this.fail(err);
            } finally {
                this.approving = false;
            }
        },

        async backToPlan() {
            this.plan = await engine.plan();
            this.status = { ...this.status, stage: 'planned' };
        },

        async openViewer() {
            const res = await engine.openViewer();
            if (!res.ok) this.fail(res.error || 'could not open the QA viewer');
        },

        async showOutput() {
            await engine.showOutput();
        },
    },
});
</script>

<style scoped lang="scss">
.aimport-root {
    min-height: 100vh;
    background: var(--app-bg);
    color: var(--ink);
}
/* the dashboard's light top bar, with the brainlife.io mark top-left */
.aimport-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 64px;
    padding: 0 1.25rem 0 1.5rem;
    background: var(--nav-bg);
    border-bottom: 1px solid var(--line);
}
.aimport-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    a {
        display: flex;
    }
    h1 {
        margin: 0;
        color: var(--ink);
        font-size: 1.3rem;
        font-weight: 600;
        letter-spacing: -0.01em;
    }
}
.aimport-logo-mark {
    height: 38px;
    width: auto;
}
.aimport-by {
    margin-left: 4px;
    font-size: 0.75rem;
    font-weight: 400;
    color: var(--ink-2);
}
.aimport-beta {
    margin-left: 6px;
}
.aimport-main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
.aimport-steps {
    margin-bottom: 0.25rem;
}
.aimport-card {
    background: var(--panel-bg);
    border-radius: var(--panel-radius);
    border: 1px solid var(--line);
    padding: 1.25rem 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    align-items: flex-start;
    h2,
    h3 {
        margin: 0;
    }
}
.aimport-folder {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    code {
        margin-right: 1rem;
    }
}
.aimport-busy {
    flex-direction: row;
    align-items: center;
    gap: 1rem;
    color: var(--ink);
}
.aimport-sub {
    color: var(--ink-2);
    margin: 0;
    font-size: 0.9rem;
}
.aimport-label {
    font-weight: 600;
    font-size: 0.85rem;
    margin-right: 0.5rem;
    color: var(--ink-2);
}
.aimport-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    small {
        color: var(--ink-3);
    }
}
.aimport-project {
    width: 220px;
}
.aimport-select {
    width: 330px;
}
.aimport-alert {
    margin: 0;
}
.aimport-plan-head {
    display: flex;
    align-items: baseline;
    gap: 1rem;
}
.aimport-table {
    width: 100%;
}
.aimport-bids {
    display: flex;
    align-items: center;
    gap: 2px;
    label {
        color: var(--ink-3);
        font-size: 0.8rem;
    }
    white-space: nowrap;
    .w-sub {
        width: 58px;
    }
    .w-dt {
        width: 100px;
        margin-left: 4px;
    }
    .w-ent {
        width: 170px;
        margin-left: 4px;
    }
}
.aimport-desc {
    font-family: monospace;
    font-size: 0.8rem;
}
.aimport-reason {
    font-size: 0.8rem;
    color: var(--ink-2);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.aimport-approve {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    flex-wrap: wrap;
    width: 100%;
    justify-content: flex-end;
}
.aimport-actions {
    display: flex;
    gap: 0.5rem;
}
.aimport-files,
.aimport-issues {
    margin: 0;
    padding-left: 1.2rem;
    font-size: 0.8rem;
    code {
        margin-left: 0.3rem;
    }
}
.aimport-later {
    color: var(--ink-3);
    font-size: 0.8rem;
    margin: 0;
}
:deep(.aimport-row-excluded) {
    opacity: 0.55;
}
</style>
