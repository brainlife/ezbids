<template>
    <div class="lv3 landing-page-container">
        <LandingPageHeader />
        <LandingPageContent />
        <LandingPageFooter />
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import LandingPageHeader from './LandingPageHeader.vue';
import LandingPageContent from './LandingPageContent.vue';
import LandingPageFooter from './LandingPageFooter.vue';
import './landing/landing.css';

export default defineComponent({
    components: {
        LandingPageHeader: LandingPageHeader,
        LandingPageContent: LandingPageContent,
        LandingPageFooter: LandingPageFooter,
    },
});
</script>

<style>
.landing-page-container {
    height: 100%;
    overflow-y: auto;
}
</style>
