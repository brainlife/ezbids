<template>
    <el-affix>
        <el-header class="header">
            <el-row style="align-items: center">
                <el-col :xs="0" :md="1" />
                <el-col :xs="24" :md="22">
                    <el-menu class="menu" :ellipsis="false" mode="horizontal">
                        <el-menu-item index="0" class="menu-item brand-item">
                            <img src="@/assets/brainlife-mark-light.svg" class="brand-mark" alt="brainlife.io" />
                            <span class="brand-name">ezBIDS</span>
                            <span class="brand-by">by brainlife.io</span>
                        </el-menu-item>
                        <div style="flex-grow: 1"></div>
                        <el-menu-item index="1" class="menu-item" @click="openBrainLifeTeamPage">
                            <el-icon>
                                <font-awesome-icon :icon="['fas', 'arrow-up-right-from-square']" />
                            </el-icon>
                            TEAM
                        </el-menu-item>
                        <el-menu-item index="2" class="menu-item">
                            <el-button type="primary" class="header-cta" @click="redirectToBrainlifeAuth">{{
                                !hasAuth || hasJWT ? 'GET STARTED' : 'LOG IN / REGISTER'
                            }}</el-button>
                        </el-menu-item>
                    </el-menu>
                </el-col>
                <el-col :xs="0" :md="1" />
            </el-row>
        </el-header>
    </el-affix>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { hasJWT, authRequired } from '@/lib';

export default defineComponent({
    computed: {
        ...mapState(['config']),
        hasAuth() {
            return authRequired();
        },
        hasJWT() {
            return hasJWT();
        },
    },
    methods: {
        openBrainLifeTeamPage() {
            window.open('https://brainlife.io/team/', '_blank');
        },
        redirectToBrainlifeAuth() {
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
/* for screens smaller than 992px */
@media screen and (max-width: 992px) {
    .menu-item {
        font-size: var(--el-font-size-small) !important;
    }
}

/* brainlife-lite's light top bar: the brainlife.io mark top-left, quiet links, one primary action */
.header {
    background-color: var(--nav-bg);
    border-bottom: 1px solid var(--line);
    height: 64px;
    padding: 0;
}

.menu {
    margin: 0 auto;
    background: transparent;
    border-bottom: 1px solid transparent !important;
}

.menu-item {
    font-size: 0.95rem;
    font-weight: 500;
    letter-spacing: 0.02em;
    color: var(--ink-2);
}

.menu-item.is-active,
.menu-item:hover {
    color: var(--el-color-primary) !important;
    background: transparent !important;
    border-bottom-color: transparent !important;
}

.brand-item {
    gap: 10px;
    color: var(--ink) !important;
}

.brand-mark {
    height: 38px;
    width: auto;
}

.brand-name {
    font-size: 1.3rem;
    font-weight: 600;
    letter-spacing: -0.01em;
}

.brand-by {
    font-size: 0.75rem;
    font-weight: 400;
    color: var(--ink-2);
}

.header-cta {
    font-family: inherit;
}
</style>
