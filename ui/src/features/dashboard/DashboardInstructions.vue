<template>
    <section class="instructions-panel" aria-labelledby="instructions-panel-title">
        <h2 id="instructions-panel-title" class="instructions-panel__title">Instructions &amp; resources</h2>
        <div class="instructions-panel__body">
            <h3 class="instructions-panel__subheading">Not sure what to do?</h3>
            <p class="instructions-panel__muted">
                If you are new to ezBIDS, you can learn more by watching our
                <a
                    class="instructions-panel__link"
                    href="https://brainlife.io/docs/tutorial/ezBIDS/"
                    target="_blank"
                    rel="noopener noreferrer"
                    ><strong>ezBIDS tutorial</strong></a
                >
                and taking a look at our
                <a
                    class="instructions-panel__link"
                    href="https://brainlife.io/docs/using_ezBIDS/"
                    target="_blank"
                    rel="noopener noreferrer"
                    ><strong>user documentation</strong></a
                >.
            </p>
            <p class="instructions-panel__muted">
                If uploading anonymized data, please organize subject data into <i>sub-</i>formatted folder names (e.g.
                <strong>sub-01</strong>). If you have multi-session data, place in <i>ses-</i>formatted folders (e.g.
                <strong>ses-A</strong>) within the subject folders.
            </p>
            <p class="instructions-panel__muted">See below for a brief ezBIDS tutorial video.</p>
            <div class="instructions-panel__video">
                <iframe
                    class="instructions-panel__iframe"
                    src="https://www.youtube.com/embed/L8rWA8qgnpo"
                    title="ezBIDS tutorial video"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowfullscreen
                />
            </div>
        </div>
    </section>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
    name: 'DashboardInstructions',
});
</script>

<style scoped lang="scss">
.instructions-panel {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(15, 23, 42, 0.08);
    border: 1px solid rgba(226, 232, 240, 0.9);
    padding: 1.25rem 1.5rem 1.5rem;
    min-height: 0;
    flex: 1 1 auto;
}

.instructions-panel__title {
    margin: 0 0 1rem;
    font-size: 1.1rem;
    font-weight: 700;
    color: #2d3748;
}

.instructions-panel__body {
    overflow-y: auto;
}

.instructions-panel__subheading {
    margin: 0 0 0.5rem;
    font-size: 1rem;
    color: #2d3748;
}

.instructions-panel__muted {
    color: #718096;
    line-height: 1.55;
    margin: 0 0 0.75rem;
}

.instructions-panel__link {
    color: #2b6cb0;
    text-decoration: none;
}

.instructions-panel__link:hover {
    text-decoration: underline;
}

.instructions-panel__video {
    position: relative;
    width: 100%;
    max-width: 640px;
    margin-top: 0.5rem;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    aspect-ratio: 16 / 9;
    background: #000;
}

.instructions-panel__iframe {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: 0;
}
</style>
