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
@import url('https://fonts.googleapis.com/css2?family=Merriweather+Sans:wght@400;700&family=Merriweather:wght@400;700');

html,
body,
#app,
#app-container {
    height: 100%;
}

body {
    margin: 0;
    font-family: 'Merriweather Sans', Georgia, sans-serif;
    font-size: 14px;
    color: #333;
}
</style>
