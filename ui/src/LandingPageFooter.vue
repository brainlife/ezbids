
<template>
    <el-footer class="footer">
        <el-row style="height: 100%">
            <el-col :span="1"></el-col>
            <el-col :span="23" class="disclaimer">
                © Pestillilab. All rights reserved.
            </el-col>
        </el-row>
    </el-footer>
</template>
    
<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({});
</script>

<style scoped>
.footer {
    padding: 0;
    background-color: #3782e5;
    color: white;
    height: 10vh;
}

.disclaimer {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
}
</style>