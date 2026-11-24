<template>
    <span :class="['lockup', tone, size]">
        <picture>
            <source v-if="tone === 'auto'" :srcset="markOnDark" media="(prefers-color-scheme: dark)" />
            <img class="lockup-mark" :src="tone === 'dark' ? markOnDark : markOnLight" alt="brainlife.io" />
        </picture>
        <span class="lockup-text">
            <span class="lockup-name"><b class="ez">ez</b>BIDS</span>
            <span class="lockup-by">by brainlife<i>.io</i></span>
        </span>
    </span>
</template>

<script lang="ts">
/* The ezBIDS lockup: the brainlife.io app mark (light-blue · orange, landing-next/public/brand
   "App marks") with the ezBIDS wordmark and "by brainlife.io" stacked beneath it. One component for
   the landing header and footer and the converter sidebar, so the three stay the same. `tone` is the
   background it sits on ('auto' follows prefers-color-scheme, like the landing page). The font is inherited (Geist on the landing, DM Sans in the converter).
   Colors come from the mark itself (brainlife-lite src/assets/logo.svg and logo-on-dark.svg, the same
   files as landing-next/public/brand/brainlife-mark-lightblue-orange-app-on-*.svg): "ez" takes the
   left hemisphere #3b9fd0, "BIDS" the trunk ink #1d2230 (#eef3f6 on dark), and "by brainlife.io" is
   brainlife-lite's secondary text #718096 (landing hero muted #a9bac6 on dark). */
import { defineComponent, PropType } from 'vue';
import markOnLight from '../../assets/brand/brainlife-mark-lightblue-orange-app-on-light.svg';
import markOnDark from '../../assets/brand/brainlife-mark-lightblue-orange-app-on-dark.svg';

export default defineComponent({
    props: {
        tone: { type: String as PropType<'light' | 'dark' | 'auto'>, default: 'light' },
        size: { type: String as PropType<'sm' | 'md' | 'lg'>, default: 'md' },
    },
    data() {
        return { markOnLight, markOnDark };
    },
});
</script>

<style scoped>
.lockup {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    line-height: 1;
    text-decoration: none;
}
picture {
    display: block;
    flex: none;
}
.lockup-mark {
    display: block;
    height: 40px;
    width: auto;
    flex: none;
}
.lockup-text {
    display: flex;
    flex-direction: column;
    gap: 3px;
}
.lockup-name {
    font-weight: 600;
    font-size: 1.25rem;
    letter-spacing: -0.02em;
    color: #1d2230;
}
.lockup-name .ez {
    font-weight: inherit;
    color: #3b9fd0;
}
.lockup-by {
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.01em;
    color: #718096;
}
.lockup-by i {
    font-style: normal;
    opacity: 0.75;
}
@media (prefers-color-scheme: dark) {
    .auto .lockup-name {
        color: #eef3f6;
    }
    .auto .lockup-by {
        color: #a9bac6;
    }
}
.dark .lockup-name {
    color: #eef3f6;
}
.dark .lockup-by {
    color: #a9bac6;
}
.sm picture {
    display: block;
    flex: none;
}
.lockup-mark {
    height: 30px;
}
.sm .lockup-name {
    font-size: 1.05rem;
}
.sm .lockup-by {
    font-size: 0.66rem;
}
.lg picture {
    display: block;
    flex: none;
}
.lockup-mark {
    height: 44px;
}
.lg .lockup-name {
    font-size: 1.35rem;
}
</style>
