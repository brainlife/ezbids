<template>
    <div>
        <h3 class="display-mode">
            {{ isElectron ? 'Desktop' : 'Server' }}

            <el-tooltip>
                <template #content>
                    <p style="max-width: 300px">
                        {{
                            isElectron
                                ? 'ezBIDS is running solely in your computer. ezBIDS is not moving your data anywhere, and processing is occurring locally.'
                                : 'ezBIDS will be storing and processing your data on a secure server.'
                        }}
                    </p>
                </template>
                <font-awesome-icon class="question-icon" :icon="['fas', 'question-circle']" />
            </el-tooltip>
        </h3>
    </div>
</template>
<script lang="ts">
import { defineComponent } from 'vue';
export default defineComponent({
    computed: {
        isElectron() {
            return window.env.IS_ELECTRON === 'true';
        },
    },
});
</script>

<style scoped>
/* a small tonal chip (brainlife-lite's tonal look): where ezBIDS runs */
.display-mode {
    display: inline-flex;
    align-items: center;
    margin: 0;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.02em;
    color: #7a5a14;
    background: rgba(201, 169, 79, 0.2);
}
.question-icon {
    margin-left: 6px;
    opacity: 0.8;
    &:hover {
        cursor: pointer;
    }
}
</style>
