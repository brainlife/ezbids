<template>
    <header class="site-header">
        <div class="wrap bar">
            <div class="brand-row">
                <a href="https://brainlife.io/about/" target="_blank" aria-label="brainlife.io">
                    <img class="mark" :src="brainlifeMark" alt="" />
                </a>
                <a class="brand" href="#" @click.prevent="$router.push('/')">
                    ezBIDS <span class="by mono">by brainlife.io</span>
                </a>
            </div>
            <nav class="nav">
                <a class="mono" href="https://brainlife.io/docs/using_ezBIDS/" target="_blank">Docs</a>
                <a class="mono" href="https://brainlife.io/team/" target="_blank">Team</a>
                <button class="btn p" @click="redirectToBrainlifeAuth">
                    {{ !hasAuth || hasJWT ? 'Get started' : 'Log in / register' }}
                </button>
            </nav>
        </div>
    </header>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { hasJWT, hasAuth } from './lib';
import brainlifeMark from './assets/brainlife-mark.svg';

export default defineComponent({
    data() {
        return { brainlifeMark };
    },
    computed: {
        ...mapState(['config']),
        hasAuth() {
            return hasAuth();
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
            if (!hasAuth() || hasJWT()) {
                this.$router.push('/convert');
                return;
            }

            sessionStorage.setItem('auth_redirect', `${window.location.href}convert`);
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
.site-header {
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--hero);
    border-bottom: 1px solid var(--hero-line);
}
.bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 60px;
}
.brand-row {
    display: flex;
    align-items: center;
    gap: 12px;
}
.mark {
    height: 34px;
    width: auto;
    display: block;
}
.brand {
    color: var(--hero-ink) !important;
    font-weight: 600;
    font-size: 1.1rem;
    text-decoration: none !important;
}
.by {
    font-size: 0.66rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--hero-muted);
    margin-left: 8px;
}
.nav {
    display: flex;
    align-items: center;
    gap: 18px;
}
.nav a {
    color: var(--hero-muted);
    font-size: 0.78rem;
}
.nav .btn.p {
    background: var(--hero-accent);
    border-color: var(--hero-accent);
    color: var(--hero-accent-ink);
    padding: 7px 14px;
}
@media (max-width: 600px) {
    .by,
    .nav a {
        display: none;
    }
}
</style>
