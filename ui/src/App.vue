<template>
<div id="app">
    <el-container>
        <el-header height="110px">
            <h1>ezBIDS</h1>
            <themenu v-model="page"/>
        </el-header>
        <el-main>
            <upload v-show="page == 'upload'"/>
            <description v-show="page == 'description'"/>
            <participants v-show="page == 'participants'"/>
            <objects v-show="page == 'objects'"/>
        </el-main>
    </el-container>
</div>
</template>

<script>
import themenu from './components/menu.vue'

import upload from '@/upload'
import description from '@/description'
import participants from '@/participants'
import objects from '@/objects'

export default {
    //store,
    components: {
        themenu,
        upload,
        description,
        participants,
        objects,
    },
    data() {
        return {
            page: "upload",
        }
    },
    created() {
        console.log("App");
    },
}
</script>

<style>
body, html, textarea {
    font-family: Avenir, Helvetica, Arial, sans-serif;
    color: #666;
}
.el-header {
    position: fixed;
    left: 0;
    right: 0;
    top: 0;
    z-index: 3000;
    background-color: white;
    height: 100px;
}
.el-main {
    margin-top: 100px;
}
h1 {
    margin-bottom: 0;
}

.el-table td.vtop {
    vertical-align: top;
}
.sub-title {
    opacity: 0.7;
}
</style>
