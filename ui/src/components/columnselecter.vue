<template>
<el-select v-model="modelValue" size="small" clearable placeholder="Select column">
    <el-option v-for="(key, idx) in columnKeys" :key="idx" :label="key" :value="key">
        <div style="display: inline-block; min-width: 100px">{{key}}</div>
        <small>{{composeSampleValue(key)}}</small>
    </el-option>
</el-select>
</template>

<script>

export default {
    props: [
        'modelValue', 'columnKeys', 'sampleValues',
    ],
    mounted() {
    },
    data() {
        return {
            //json: "{}",
        }
    },
    methods: {
        /*
        change(v) {
            this.$emit("update:modelValue", v);
        },
        */

        composeSampleValue(key) {
            const samples = this.sampleValues[key].join(', ');
            if(samples.length > 30) return samples.substring(0, 30)+" ...";
            return samples;
        },
     }
}


</script>
