
<template>
    <el-main style="padding: 0 !important">
        <el-row class="hero-banner-container" style="align-items: center;">
            <el-col :xs="0" :md="1" />
            <el-col :xs="24" :md="10" class="landing-page-col">
                <el-row>
                    <h1 style="font-size: 2.5rem;">Convert neuroimaging data and associated metadata to the BIDS standard</h1>
                </el-row>
                <el-row>
                    <p style="font-size: var(--el-font-size-extra-large); line-height: 1.7">
                        ezBIDS requires neither coding proficiency nor knowledge of BIDS in order to get started. It is the
                        first BIDS tool to offer guided standardization, support for task events conversion, and
                        interoperability with OpenNeuro and brainlife.io.
                    </p>
                </el-row>
                <el-row>
                    <el-col :xs="24" :md="12">
                        <el-button @click="goToConvertPage" type="primary" class="hero-banner-button" style="font-weight: bold;">GET STARTED</el-button>
                    </el-col>
                    <el-col :xs="24" :md="12">
                        <el-button class="hero-banner-button" @click="openDocumentation" type="text">
                            <el-icon>
                                <font-awesome-icon :icon="[ 'fas', 'arrow-up-right-from-square' ]" />
                            </el-icon>
                            See documentation
                        </el-button>
                    </el-col>
                </el-row>
            </el-col>
            <el-col :xs="0" :md="1" />
            <el-col :xs="24" :md="12" style="width: 100%" class="landing-page-col">
                <LandingPageAnimation />
            </el-col>
        </el-row>
        <el-row class="cards-container">
            <el-col :xs="12" :md="6">
                <el-card class="card">
                    <div style="width: 100%; color: #20ab5c">
                        <el-icon style="width: 40px; height: 40px; font-size: 2rem;">
                            <font-awesome-icon :icon="['fas', 'circle-check']" />
                        </el-icon>
                    </div>
                    No installation or programming requirements
                </el-card>
            </el-col>
            <el-col :xs="12" :md="6">
                <el-card class="card">
                    <div style="width: 100%; color: #20ab5c">
                        <el-icon style="width: 40px; height: 40px; font-size: 2rem;">
                            <font-awesome-icon :icon="['fas', 'circle-check']" />
                        </el-icon>
                    </div>
                    Handles both metadata as well as imaging/task events data
                </el-card>
            </el-col>
            <el-col :xs="12" :md="6">
                <el-card class="card">
                    <div style="width: 100%; color: #20ab5c">
                        <el-icon style="width: 40px; height: 40px; font-size: 2rem;">
                            <font-awesome-icon :icon="['fas', 'circle-check']" />
                        </el-icon>
                    </div>
                    Semi-automated inference and guidance for adherence to BIDS
                </el-card>
            </el-col>
            <el-col :xs="12" :md="6">
                <el-card class="card">
                    <div style="width: 100%; color: #20ab5c">
                        <el-icon style="width: 40px; height: 40px; font-size: 2rem;">
                            <font-awesome-icon :icon="['fas', 'circle-check']" />
                        </el-icon>
                    </div>
                    Multiple data management options: download BIDS data to local system, or transfer to either OpenNeuro or
                    brainlife.io.
                </el-card>
            </el-col>
        </el-row>
    </el-main>
</template>
    
<script lang="ts">
import { defineComponent } from 'vue';
import LandingPageAnimation from './LandingPageAnimation.vue';
export default defineComponent({
    components: {
        LandingPageAnimation: LandingPageAnimation
    },
    methods: {
        openDocumentation() {
            window.open(`https://brainlife.io/docs/using_ezBIDS/`)
        },
        goToConvertPage() {
            router.push('/convert');
        }
    }
})
</script>

<style scoped>

/* for screens smaller than 992px */
@media screen and (max-width: 992px) {
    .hero-banner-container {
        flex-wrap: wrap-reverse;
    }

    .card {
        height: 200px;
        font-size: var(--el-font-size-small);
        margin: 1rem;
    }
}

/* for screens larger than 992px */
@media screen and (min-width: 992px) {
    .hero-banner-container {
        flex-wrap: wrap;
    }

    .card {
        height: 200px;
        font-size: var(--el-font-size-large);
        margin: 2rem;
    }
}

.hero-banner-container {
    margin-bottom: 2rem;
}

.hero-banner-button {
    margin: 1rem 0;
    height: 50px;
    font-size: 1rem;
    width: 100%;
}

.cards-container {
    background-color: #20ab5c;
    align-items: center;
}

.card {
    text-align: center;
}

.card-icon {
    width: 40px;
    height: 40px;
    font-size: 2rem;
}

.landing-page-col {
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
    margin-bottom: 1rem
}

</style>