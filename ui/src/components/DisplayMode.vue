<template>
    <div>
        <h3 style="color: #e6a23c; display: flex; align-items: center; margin: 0">
            {{ isElectron ? 'Desktop' : 'Server' }}

            <el-tooltip>
                <template #content>
                    <p style="max-width: 300px">
                        {{
                            isElectron
                                ? 'ezBIDS is running solely in your computer. ezBIDS is not moving your data anywhere, and processing is occuring locally.'
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
    margin-left: 8px;
    &:hover {
        cursor: pointer;
    }
}
</style>
