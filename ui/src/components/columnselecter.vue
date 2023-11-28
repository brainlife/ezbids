<template>
    <el-select v-model="column" size="small" clearable placeholder="Select column">
        <el-option v-for="(key, idx) in columnKeys" :key="idx" :label="key" :value="key">
            <div style="display: inline-block; min-width: 100px">{{ key }}</div>
            <small>{{ composeSampleValue(key) }}</small>
        </el-option>
    </el-select>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
    props: ['modelValue', 'columnKeys', 'sampleValues'],
    emits: ['update:modelValue'],
    data() {
        return {
            //json: "{}",
        };
    },

    computed: {
        column: {
            get() {
                return this.modelValue;
            },
            set(v: string) {
                this.$emit('update:modelValue', v);
            },
        },
    },
    mounted() {},

    methods: {
        /*
        change(v) {
            this.$emit("update:modelValue", v);
        },
        */

        composeSampleValue(key: string) {
            const samples = this.sampleValues[key].join(', ');
            if (samples.length > 30) return samples.substring(0, 30) + ' ...';
            return samples;
        },
    },
});
</script>
