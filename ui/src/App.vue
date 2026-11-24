<template>
    <div>
        <RouterView />
    </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({});
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
