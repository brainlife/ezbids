<template>
    <header class="site-band">
        <div class="wrap site">
            <a class="brand" href="#" aria-label="ezBIDS home" @click.prevent="$router.push('/')">
                <BrandLockup tone="dark" />
            </a>
            <nav class="nav" aria-label="Primary">
                <a href="https://brainlife.io/docs/using_ezBIDS/">Docs</a>
                <a href="https://brainlife.io/docs/using_aimport/">aimport</a>
                <a href="https://brainlife.io/team/">Team</a>
                <button class="btn" @click="redirectToBrainlifeAuth">
                    {{ !hasAuth || hasJWT ? 'Get started' : 'Sign in' }}
                </button>
            </nav>
        </div>
    </header>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { hasJWT, authRequired } from '@/lib';
import BrandLockup from '@/components/brand/BrandLockup.vue';

export default defineComponent({
    components: { BrandLockup },
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
/* landing-next SiteHeader: a translucent band over the hero, logo left, links right */
.site-band {
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--hero);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--hero-line);
}
.site {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding-block: 12px;
}
.brand {
    text-decoration: none !important;
}
.nav {
    display: flex;
    align-items: center;
    gap: 22px;
    font-size: 0.95rem;
    font-weight: 500;
}
.nav a {
    color: var(--hero-ink);
    opacity: 0.92;
    line-height: 1;
}
.nav a:hover {
    opacity: 1;
    color: var(--hero-accent);
    text-decoration: none;
}
.nav .btn {
    color: var(--hero-ink);
    border-color: rgba(238, 243, 246, 0.35);
    padding: 8px 14px;
    margin-left: 6px;
    line-height: 1;
}
.nav .btn:hover {
    border-color: var(--hero-accent);
    color: var(--hero-accent);
}
@media (max-width: 760px) {
    .nav a {
        display: none;
    }
}
</style>
