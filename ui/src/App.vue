<template>
<div id="app">
    <el-container>
        <!--
        <el-header height="110px">
            <h1><span style="letter-spacing: -3px; opacity: 0.6;">ez</span>BIDS</h1>
            <themenu v-model="$root.page"/>
        </el-header>
        -->
        <el-aside width="200px">
            <h1><span style="letter-spacing: -3px; opacity: 0.6;">ez</span>BIDS</h1>
            <themenu v-model="$root.page"/>
        </el-aside>
        <el-main>
            <upload v-show="$root.page == 'upload'"/>
            <description v-show="$root.page == 'description'"/>
            <subjects v-show="$root.page == 'subjects'"/>
            <sessions v-show="$root.page == 'sessions'"/>
            <series v-show="$root.page == 'series'"/>
            <participants v-show="$root.page == 'participants'"/>
            <objects v-show="$root.page == 'objects'"/>
            <finalize v-show="$root.page == 'finalize'"/>
        </el-main>
    </el-container>
</div>
</template>

<script>
import themenu from './components/menu.vue'

import upload from '@/upload'
import description from '@/description'
import subjects from '@/subjects'
import sessions from '@/sessions'
import series from '@/series'
import participants from '@/participants'
import objects from '@/objects'
import finalize from '@/finalize'

export default {
    //store,
    components: {
        themenu,
        upload,
        description,
        subjects,
        sessions,
        series,
        participants,
        objects,
        finalize,
    },
    data() {
        return {
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
/*
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
*/
h1 {
    padding: 5px 20px;
    margin-bottom: 0;
    opacity: 0.8;
    font-size: 20pt;
}

.el-table td.vtop {
    vertical-align: top;
}
.sub-title {
    opacity: 0.7;
}
</style>
