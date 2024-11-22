<template>
    <!-- subtract 62px for the header and 10 vh for the footer -->
    <el-main class="main">
        <el-row class="hero-banner-container">
            <el-col :xs="0" :md="1" />
            <el-col :xs="24" :md="10" class="landing-page-col">
                <el-row>
                    <h1 class="hero-banner-title">
                        Convert neuroimaging data and associated metadata to the BIDS standard
                    </h1>
                </el-row>
                <el-row>
                    <p class="hero-banner-description">
                        ezBIDS requires neither coding proficiency nor knowledge of BIDS in order to get started. It is
                        the first BIDS tool to offer guided standardization, support for task events conversion, and
                        interoperability with
                        <a href="https://openneuro.org" class="link" target="_blank">OpenNeuro</a>
                        and
                        <a href="https://brainlife.io" class="link" target="_blank">brainlife.io</a>. Our recent
                        publication in <i>Scientific Data</i> can be found
                        <a href="https://www.nature.com/articles/s41597-024-02959-0" class="link" target="_blank"
                            >here</a
                        >.
                    </p>
                </el-row>
                <el-row>
                    <el-col :xs="24" :md="12">
                        <el-button
                            type="primary"
                            style="color: white !important; font-weight: bold"
                            class="hero-banner-button"
                            @click="onClickGetStarted"
                        >
                            GET STARTED
                        </el-button>
                    </el-col>
                    <el-col :xs="24" :md="12">
                        <el-button class="hero-banner-button" type="text" @click="openDocumentation">
                            <el-icon>
                                <font-awesome-icon :icon="['fas', 'arrow-up-right-from-square']" />
                            </el-icon>
                            See documentation
                        </el-button>
                    </el-col>
                </el-row>
            </el-col>
            <el-col :xs="0" :md="1" />
            <el-col :xs="24" :md="12" class="landing-page-col">
                <LandingPageAnimation />
            </el-col>
        </el-row>
        <el-row class="cards-container">
            <el-col :xs="24" :md="6" class="card-container">
                <el-card class="card">
                    <div class="card-content">
                        <el-icon class="card-icon">
                            <font-awesome-icon :icon="['fas', 'circle-check']" />
                        </el-icon>
                        No installation or programming requirements
                    </div>
                </el-card>
            </el-col>
            <el-col :xs="24" :md="6" class="card-container">
                <el-card class="card">
                    <div class="card-content">
                        <el-icon class="card-icon">
                            <font-awesome-icon :icon="['fas', 'circle-check']" />
                        </el-icon>
                        Handles both metadata as well as imaging/task events data
                    </div>
                </el-card>
            </el-col>
            <el-col :xs="24" :md="6" class="card-container">
                <el-card class="card">
                    <div class="card-content">
                        <el-icon class="card-icon">
                            <font-awesome-icon :icon="['fas', 'circle-check']" />
                        </el-icon>
                        Semi-automated inference and guidance for adherence to BIDS
                    </div>
                </el-card>
            </el-col>
            <el-col :xs="24" :md="6" class="card-container">
                <el-card class="card">
                    <div class="card-content">
                        <el-icon class="card-icon">
                            <font-awesome-icon :icon="['fas', 'circle-check']" />
                        </el-icon>
                        <span>
                            Multiple data management options: download BIDS data to local system, or transfer to either
                            <a href="https://openneuro.org" class="link" target="_blank">OpenNeuro</a>
                            or
                            <a href="https://brainlife.io" class="link" target="_blank">brainlife.io</a>.
                        </span>
                    </div>
                </el-card>
            </el-col>
        </el-row>
    </el-main>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import LandingPageAnimation from './LandingPageAnimation.vue';
import { hasJWT, authRequired } from './lib';
export default defineComponent({
    components: {
        LandingPageAnimation: LandingPageAnimation,
    },
    computed: {
        ...mapState(['config']),
    },
    methods: {
        openDocumentation() {
            window.open(`https://brainlife.io/docs/using_ezBIDS/`);
        },
        onClickGetStarted() {
            if (!authRequired() || hasJWT()) {
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
/* for screens smaller than 992px */
@media screen and (max-width: 992px) {
    .main {
        height: 100%;
    }

    .hero-banner-container {
        flex-wrap: wrap-reverse;
    }

    .cards-container {
        height: 100% !important;
    }

    .card-container {
        padding: 1.5rem;
    }

    .card {
        font-size: var(--el-font-size-small);
    }

    .card-content {
        display: flex;
        flex-direction: row;
        align-items: center;
        text-align: start;
    }

    .hero-banner-button {
        margin: 1rem 0;
        height: 50px;
        font-size: 1rem;
        width: 100%;
        color: #3782e5 !important;
    }

    .card-icon {
        margin-right: 20px !important;
    }
}

/* for screens larger than 992px */
@media screen and (min-width: 992px) {
    .main {
        height: calc(90vh - 62px);
    }

    .hero-banner-container {
        flex-wrap: wrap;
    }

    .hero-banner-button {
        margin: 0.5rem 0;
        height: 40px;
        font-size: var(--el-font-size-medium);
        width: 100%;
    }

    .hero-banner-title {
        font-size: 1.5rem;
        margin: 10px 0;
    }

    .hero-banner-description {
        font-size: var(--el-font-size-large);
        margin: 10px 0;
        line-height: 1.7;
    }

    .card-container {
        padding: 1.5rem;
    }

    .card-content {
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    .card {
        font-size: var(--el-font-large);
    }
}

/* for screen larger than 1200px */
@media screen and (min-width: 1200px) {
    .hero-banner-title {
        font-size: 1.5rem;
        margin: 10px 0;
    }

    .hero-banner-description {
        font-size: var(--el-font-size-large);
        margin: 10px 0;
        line-height: 1.7;
    }

    .card-container {
        padding: 2rem;
    }

    .card {
        font-size: var(--el-font-large);
    }
}

/* for screen larger than 1400px */
@media screen and (min-width: 1400px) {
    .hero-banner-title {
        font-size: 2rem;
        margin: 10px 0;
    }

    .card-container {
        padding: 2rem;
    }
}

/* for screen larger than 1400px */
@media screen and (min-width: 1600px) {
    .hero-banner-description {
        font-size: var(--el-font-size-extra-large);
        margin: 0px;
        line-height: 1.7;
    }

    .card {
        font-size: var(--el-font-size-extra-large);
    }
}

.link {
    color: #3782e5;
    text-decoration: none;
    display: inline;

    &:hover {
        text-decoration: underline;
        opacity: 0.8;
    }
}

.main {
    padding: 0 !important;
}

.hero-banner-container {
    height: 65%;
    align-items: center;
}

.cards-container {
    height: 35%;
    background-color: #20ab5c;
    align-items: center;
}

.card-container {
    height: 100%;
}

.card {
    text-align: center;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
}

.card-icon {
    width: 40px;
    height: 40px;
    font-size: 2rem;
    color: #20ab5c;
    display: flex;
    align-items: center;
    justify-content: center;
}

.landing-page-col {
    width: 100%;
    padding: 20px;
}

.avatar-container {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
}

.avatar {
    width: 200px;
    height: 200px;
    border-radius: 50%;
    margin-bottom: 1rem;
}
</style>
