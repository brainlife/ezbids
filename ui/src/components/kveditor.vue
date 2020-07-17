<template>
<div>
    <!-- this doesn't handle nested / array types
    <el-form label-width="200px" size="mini">
        <el-form-item :label="key" v-for="(value, key) in kv" :key="key" style="margin: 2px 0;">
            <el-input v-model="kv[key]"/>
        </el-form-item>
    </el-form>
    -->
    <el-input type="textarea" rows="10" v-model="item.sidecar_json" @blur="change"/>
</div>
</template>

<script>

export default {
    props: [
        //'kv'
        'item'
    ],
    mounted() {
        //this.json = JSON.stringify(this.kv, null, 4); 
    },
    data() {
        return {
            //json: "{}",
        }
    },
    methods: {
        change() {
            console.log("blured");
            this.$emit("change");
        }
    }
}


</script>
