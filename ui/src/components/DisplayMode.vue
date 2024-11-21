<template>
    <div v-if="ezbidsProcessingMode !== undefined">
        <h1 style="color: #e6a23c; margin-left: 1rem; display: flex; align-items: center">
            {{ ezbidsProcessingMode }}

            <el-tooltip>
                <template #content>
                    <p style="max-width: 300px">
                        {{
                            ezbidsProcessingMode === 'EDGE'
                                ? 'ezBIDS is running locally in the browser. ezBIDS is not moving your data anywhere, and all your data is being processed locally.'
                                : 'The data is too large to be processed locally and ezBIDS must store your data in the server in order to process it.'
                        }}
                    </p>
                </template>
                <font-awesome-icon class="question-icon" :icon="['fas', 'question-circle']" />
            </el-tooltip>
        </h1>
    </div>
</template>
<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';

export default defineComponent({
    computed: {
        ...mapState(['ezbidsProcessingMode']),
    },
});
</script>

<style scoped>
.question-icon {
    color: white;
    width: 18px;
    height: 18px;
    margin-left: 8px;
    &:hover {
        cursor: pointer;
    }
}
</style>
