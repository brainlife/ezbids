
<template>
<el-container direction="vertical" style="padding-bottom: 0 !important">
    <LandingPageHeader />
    <LandingPageContent />
    <LandingPageFooter />
</el-container>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import LandingPageHeader from './LandingPageHeader.vue';
import LandingPageContent from './LandingPageContent.vue';
import LandingPageFooter from './LandingPageFooter.vue'

export default defineComponent({
    components: {
        LandingPageHeader: LandingPageHeader,
        LandingPageContent: LandingPageContent,
        LandingPageFooter: LandingPageFooter
    }
})
</script>

<style>
</style>