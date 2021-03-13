<template>
<div style="height: 100%;">
    <el-container style="height: 100%;">
        <div class="menu">
            <h1 style="font-size: 25pt"><span style="letter-spacing: -3px; opacity: 0.6;">ez</span>BIDS</h1>
            <div style="height: 300px; padding: 15px;" v-if="$root.currentPage">
                <el-steps direction="vertical" :active="$root.currentPage.idx">
                    <el-step v-for="p in $root.pages" :key="p.idx" :title="p.title"></el-step>
                </el-steps>
            </div>
        </div>
        <div class="main-content" v-if="$root.currentPage">
            <upload/>
            <description/>
            <subjects/>
            <series/>
            <participants/>
            <objects/>
            <deface/>
            <finalize/>
        </div>
        <div class="main-content" v-else>
            <p style="padding: 20px;">Initializing..</p>
        </div>
    </el-container>
</div>
</template>

<script>
//import themenu from './components/menu.vue'

import upload from '@/upload'
import description from '@/description'
import subjects from '@/subjects'
import series from '@/series'
import participants from '@/participants'
import objects from '@/objects'
import deface from '@/deface'
import finalize from '@/finalize'

export default {
    components: {
        upload,
        description,
        subjects,
        participants,
        series,
        objects,
        deface,
        finalize,
    },
}
</script>

<style>
body, html, textarea {
    font-family: Arial, sans-serif;
    color: #666;
    height: 100%;
    padding: 0;
    margin: 0;
}
textarea {
    font-family: Arial, sans-serif;
}
h1 {
    padding: 5px 20px;
    margin-bottom: 0;
    opacity: 0.8;
    font-size: 20pt;
}
h2, h3, h4 {
    margin: 0;
    margin-bottom: 10px;
}
p {
    line-height: 200%;
}
pre {
    font-size: 80%;
    white-space: pre-wrap;

}
small {
}
.el-main {
    /*there is something wrong bids structure page where the el-main doesn't get expaned all the way to the bottom*/
    overflow: inherit;
}

.el-table.table-align-top td {
    vertical-align: top;
}
.sub-title {
    opacity: 0.7;
}
.help-block {
    line-height: 1.5;
    opacity: 0.8;
    font-size: 95%;
    margin-top: 0;
}
.el-table .cell {
word-break: normal;
}
.page-action {
    position: fixed;
    box-sizing: border-box;
    background-color: #0002;
    padding: 10px;
    right: 0;
    left: 200px;
    bottom: 0;
    z-index: 1;
}
.menu {
    width: 200px; 
    position: fixed; 
    top: 0; 
    left: 0; 
    bottom: 0; 
    background-color: #0001;
    box-shadow: inset -3px 0 5px #9991;
}
.main-content {
    margin-left :200px;
    width: calc(100% - 200px);
}
.el-step .el-step__title {
    font-size: 14px;

}
</style>
