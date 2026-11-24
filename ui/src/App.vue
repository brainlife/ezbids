<template>
    <div>
        <RouterView />
        <ExternalPageDialog />
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import ExternalPageDialog from '@/components/dialogs/ExternalPageDialog.vue';
import { interceptExternalLinks, openExternal } from '@/externalPage';

/* Nothing opens a new window: links to other sites open in ExternalPageDialog over the app (a <webview>
   in the desktop app). electron/inAppBrowsing.ts routes any window.open that slips through to it too. */
export default defineComponent({
    components: { ExternalPageDialog },
    mounted() {
        document.addEventListener('click', interceptExternalLinks);
        window.ezbidsInApp?.onOpen((url) => openExternal(url));
    },
    unmounted() {
        document.removeEventListener('click', interceptExternalLinks);
    },
});
</script>

<style lang="scss">
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300..700&display=swap');

html,
body,
#app,
#app-container {
    height: 100%;
}

body {
    margin: 0;
    font-family:
        'DM Sans',
        -apple-system,
        BlinkMacSystemFont,
        'Segoe UI',
        sans-serif;
    font-size: 14px;
    color: #2d3748;
    background: #f5f5f5;
    -webkit-font-smoothing: antialiased;
}
</style>
