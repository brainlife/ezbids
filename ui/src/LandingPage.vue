<template>
    <el-container direction="vertical" class="landing-page-container">
        <LandingPageHeader />
        <LandingPageContent />
        <LandingPageFooter />
    </el-container>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import LandingPageHeader from './LandingPageHeader.vue';
import LandingPageContent from './LandingPageContent.vue';
import LandingPageFooter from './LandingPageFooter.vue';

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
    padding-bottom: 0 !important;
    height: 100%;
    /* can't let the user make the window too small or else everything gets squished */
    min-height: 750px;
}
</style>
