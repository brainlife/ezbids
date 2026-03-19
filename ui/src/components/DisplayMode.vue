<template>
    <div>
        <h3 style="color: #e6a23c; margin-left: 1rem; display: flex; align-items: center">
            {{ isElectron ? 'ezBIDS Desktop' : 'ezBIDS Server' }}

            <el-tooltip>
                <template #content>
                    <p style="max-width: 300px">
                        {{
                            isElectron
                                ? 'ezBIDS is running solely in your computer. ezBIDS is not moving your data anywhere, and everything is being processed locally.'
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
.question-icon {
    width: 18px;
    height: 18px;
    margin-left: 8px;
    &:hover {
        cursor: pointer;
    }
}
</style>
