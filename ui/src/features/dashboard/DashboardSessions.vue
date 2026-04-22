<template>
    <section class="dashboard-card dashboard-sessions" aria-labelledby="dashboard-sessions-title">
        <h2 id="dashboard-sessions-title" class="dashboard-section-title">Previous sessions</h2>
        <p v-if="!sessions.length" class="dashboard-muted">
            No sessions yet. After you upload data, sessions appear here on this device.
        </p>
        <el-scrollbar v-else class="dashboard-session-scroll">
            <ul class="dashboard-session-list">
                <li
                    v-for="s in sessions"
                    :key="s._id"
                    class="dashboard-session-item"
                    style="margin-bottom: 0.5rem; padding-right: 8px"
                >
                    <el-button class="dashboard-session-button" @click="$emit('open-session', s._id)">
                        <p class="dashboard-session-id">ID: {{ s._id }}</p>
                        <div class="dashboard-session-field" style="margin-bottom: 0.5rem">
                            <div style="display: flex; align-items: center; line-height: normal">
                                <span class="dashboard-session-label">Status</span>
                                <span
                                    style="text-transform: uppercase; font-size: 0.7rem; margin-left: 8px"
                                    class="dashboard-session-value"
                                    :class="statusClass(s.status)"
                                >
                                    {{ s.status || 'Unknown' }}
                                </span>
                            </div>
                            <span class="dashboard-session-value dashboard-session-message-text">
                                {{ s.status_msg || 'No status message' }}
                            </span>
                        </div>
                        <div class="dashboard-session-grid">
                            <div style="display: flex; flex-wrap: wrap">
                                <p class="dashboard-session-field">
                                    <span class="dashboard-session-label">Created</span>
                                    <span class="dashboard-session-value">{{ formatSessionDate(s.create_date) }}</span>
                                </p>
                                <p class="dashboard-session-field">
                                    <span class="dashboard-session-label">Updated</span>
                                    <span class="dashboard-session-value">{{ formatSessionDate(s.update_date) }}</span>
                                </p>
                            </div>
                            <p class="dashboard-session-field">
                                <span class="dashboard-session-label">DICOM count</span>
                                <span class="dashboard-session-value">{{ formatDicomCount(s.dicomCount) }}</span>
                            </p>
                        </div>
                    </el-button>
                </li>
            </ul>
        </el-scrollbar>
    </section>
</template>

<script lang="ts">
import axios from 'axios';
import { defineComponent } from 'vue';
import { mapState } from 'vuex';

type RecentEntry = {
    _id: string;
    create_date: string;
    update_date?: string;
    status?: string;
    status_msg?: string;
    dicomCount?: number;
};

export default defineComponent({
    name: 'DashboardSessions',
    emits: ['open-session'],
    data() {
        return {
            sessions: [] as RecentEntry[],
        };
    },
    computed: {
        ...mapState(['config']),
    },
    async mounted() {
        try {
            const sessions = (await axios.get<RecentEntry[]>(`${this.config.apihost}/sessions`))?.data ?? [];
            this.sessions = sessions.sort((a, b) => {
                const aDate = Date.parse(a.update_date || a.create_date || '');
                const bDate = Date.parse(b.update_date || b.create_date || '');
                const aTime = Number.isNaN(aDate) ? 0 : aDate;
                const bTime = Number.isNaN(bDate) ? 0 : bDate;
                return bTime - aTime;
            });
        } catch (error) {
            console.error(error);
        }
    },
    methods: {
        formatSessionDate(iso?: string) {
            if (!iso) return 'N/A';
            try {
                return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
            } catch {
                return iso;
            }
        },
        formatDicomCount(count?: number) {
            return typeof count === 'number' ? count.toLocaleString() : 'N/A';
        },
        statusClass(status?: string) {
            const normalized = status?.trim().toLowerCase();
            if (normalized === 'finished') return 'dashboard-status-success';
            if (normalized === 'failed' || normalized === 'failure') return 'dashboard-status-failure';
            return 'dashboard-status-pending';
        },
    },
});
</script>

<style scoped lang="scss">
.dashboard-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(15, 23, 42, 0.08);
    border: 1px solid rgba(226, 232, 240, 0.9);
    align-self: stretch;
    box-sizing: border-box;
    width: 100%;
    max-width: 100%;
    min-width: 0;
}

.dashboard-sessions {
    padding: 1.25rem 1.25rem 1rem;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow-y: auto;
    max-height: 100%;
}

.dashboard-section-title {
    margin: 0 0 1rem;
    font-size: 1.1rem;
    font-weight: 700;
    color: #2d3748;
}

.dashboard-muted {
    color: #718096;
    line-height: 1.55;
    margin: 0 0 0.75rem;
}

.dashboard-session-scroll {
    flex: 1;
    min-height: 0;
    min-width: 0;
    width: 100%;
    max-width: 100%;
}

.dashboard-session-list {
    list-style: none;
    margin: 0;
    padding: 0;
    min-height: 0;
    min-width: 0;
    max-height: 500px;
    overflow-y: auto;
}

.dashboard-session-item {
    min-width: 0;
}

.dashboard-session-item:last-child {
    border-bottom: none;
}

.dashboard-session-button {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    box-sizing: border-box;
    text-align: left;
    justify-content: flex-start;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 0.6rem;
    height: auto;
    padding: 0.8rem 0.9rem;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    background: #f8fafc;
    overflow-wrap: anywhere;
}

.dashboard-session-button:hover {
    border-color: #cbd5e1;
    background: #f1f5f9;
}

.dashboard-session-id {
    margin: 0;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
    font-size: 0.75rem;
    color: #475569;
    margin-bottom: 0.8rem;
    word-break: break-all;
}

.dashboard-session-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem 0.8rem;
}

.dashboard-session-field {
    margin: 0.25rem 0;
    gap: 0.25rem;
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.dashboard-session-label {
    font-size: 0.7rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.dashboard-session-value {
    font-size: 0.84rem;
    color: #1e293b;
}

.dashboard-status-success {
    color: #15803d;
}

.dashboard-status-failure {
    color: #b91c1c;
}

.dashboard-status-pending {
    color: #ff8c00;
}

.dashboard-session-message {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
}

.dashboard-session-message-text {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: rgb(129, 138, 152);
}
</style>
