<template>
    <div class="dashboard-root">
        <header class="dashboard-header">
            <div class="brainlife-lite dashboard-logo-bar" style="padding-right: 10px">
                <div class="dashboard-logo-inner">
                    <h1 class="dashboard-logo-title"><span class="dashboard-logo-ez">ez</span>BIDS</h1>
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
                <DashboardSessions :recent-sessions="recentSessions" @open-session="openSession" />

                <DashboardInstructions />
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
    background: linear-gradient(160deg, #f7fafc 0%, #edf2f7 45%, #e2e8f0 100%);
    color: #1a202c;
}

.dashboard-header {
    display: flex;
    align-items: stretch;
    box-shadow: 0 1px 0 rgba(0, 0, 0, 0.06);
}

.brainlife-lite {
    background-color: #2d3748;
}

.aside-width {
    width: 160px;
    min-width: 160px;
    max-width: 160px;
}

.dashboard-logo-bar {
    display: flex;
    align-items: center;
    padding-left: 2rem;
}

.dashboard-logo-inner {
    display: flex;
    align-items: center;
    width: 100%;
    height: 100%;
}

.dashboard-logo-title {
    color: white;
    margin: 0;
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}

.dashboard-logo-ez {
    letter-spacing: -3px;
    opacity: 0.6;
}

.dashboard-header-main {
    flex: 1;
    background: #2d3748;
}

.dashboard-app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 64px;
    max-height: 64px;
    box-sizing: border-box;
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
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    align-items: start;
    min-height: 320px;
}

@media (max-width: 900px) {
    .dashboard-bottom {
        grid-template-columns: 1fr;
    }
}
</style>
