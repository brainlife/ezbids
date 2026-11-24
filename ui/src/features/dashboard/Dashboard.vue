<template>
    <div class="dashboard-root">
        <header class="dashboard-header">
            <div class="brainlife-lite dashboard-logo-bar" style="padding-right: 10px">
                <div class="dashboard-logo-inner">
                    <a href="https://brainlife.io" target="_blank" rel="noopener noreferrer" aria-label="brainlife.io">
                        <img src="@/assets/brainlife-mark-light.svg" class="dashboard-logo-mark" alt="brainlife.io" />
                    </a>
                    <h1 class="dashboard-logo-title">ezBIDS <span class="dashboard-logo-by">by brainlife.io</span></h1>
                </div>
            </div>
            <div class="dashboard-header-main">
                <div class="app-header dashboard-app-header">
                    <DisplayMode />
                    <div class="menu-footer">
                        <ManageUsersDialog />
                    </div>
                </div>
            </div>
        </header>

        <main class="dashboard-main">
            <DashboardUpload />

            <div class="dashboard-bottom">
                <div class="dashboard-bottom-item">
                    <DashboardSessions :recent-sessions="recentSessions" @open-session="openSession" />
                </div>
                <div class="dashboard-bottom-item">
                    <DashboardInstructions />
                </div>
            </div>
        </main>
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import DashboardInstructions from '@/features/dashboard/DashboardInstructions.vue';
import DashboardSessions from '@/features/dashboard/DashboardSessions.vue';
import DashboardUpload from '@/features/dashboard/DashboardUpload.vue';

type RecentEntry = { _id: string; create_date: string; status?: string; update_date?: string };

const RECENT_KEY = 'ezbids_recent_sessions';

export default defineComponent({
    name: 'EzbidsDashboard',

    components: {
        DashboardInstructions,
        DashboardSessions,
        DashboardUpload,
    },

    data() {
        return {
            recentSessions: [] as RecentEntry[],
        };
    },

    created() {
        this.loadRecentSessions();
    },

    methods: {
        loadRecentSessions() {
            try {
                this.recentSessions = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
            } catch {
                this.recentSessions = [];
            }
        },

        openSession(id: string) {
            this.$router.push({ name: 'convert', hash: '#' + id });
        },
    },
});
</script>

<style scoped lang="scss">
.dashboard-root {
    min-height: 100vh;
    background: var(--app-bg);
    color: var(--ink);
}

/* light top bar like brainlife-lite's navigation, with the brainlife.io mark top-left */
.dashboard-header {
    display: flex;
    align-items: stretch;
    background: var(--nav-bg);
    border-bottom: 1px solid var(--line);
}

.brainlife-lite {
    background-color: transparent;
}

.aside-width {
    width: 160px;
    min-width: 160px;
    max-width: 160px;
}

.dashboard-logo-bar {
    display: flex;
    align-items: center;
    padding-left: 1.5rem;
}

.dashboard-logo-inner {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    height: 100%;

    a {
        display: flex;
    }
}

.dashboard-logo-mark {
    height: 38px;
    width: auto;
    display: block;
}

.dashboard-logo-title {
    color: var(--ink);
    margin: 0;
    font-size: 1.3rem;
    font-weight: 600;
    letter-spacing: -0.01em;
}

.dashboard-logo-by {
    margin-left: 4px;
    font-size: 0.75rem;
    font-weight: 400;
    letter-spacing: 0;
    color: var(--ink-2);
}

.dashboard-header-main {
    flex: 1;
    background: transparent;
}

.dashboard-app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 64px;
    max-height: 64px;
    box-sizing: border-box;
    padding-left: 12px;
}

.menu-footer {
    padding: 8px;
    display: flex;
    justify-content: flex-end;
    align-items: center;
}

.dashboard-main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.75rem 1.5rem 2.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.dashboard-bottom {
    display: flex;
    align-items: stretch;
    gap: 1.5rem;
    min-height: 320px;
    width: 100%;
    min-width: 0;

    .dashboard-bottom-item {
        flex: 1 1 0;
        min-width: 0;
        max-width: 100%;
        display: flex;
        flex-direction: column;
    }
}

@media (max-width: 900px) {
    .dashboard-bottom {
        flex-direction: column;
    }
}
</style>
