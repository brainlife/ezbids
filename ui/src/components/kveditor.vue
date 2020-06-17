<template>
<div>
    <el-form label-width="200px" size="mini">
        <el-form-item :label="key" v-for="(value, key) in kv" :key="key" style="margin: 2px 0;">
            <el-input v-model="kv[key]"/>
        </el-form-item>
    </el-form>
</div>
</template>

<script>

export default {
    props: [
        'kv'
    ],
    data() {
        return {
            something: "whatever", 
        }
    }
}


</script>
