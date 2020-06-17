<template>
<div id="app">
    <!--
    <ezBidsEditor :conf="conf"/>
    -->
    <el-container>
        <el-header height="110px">
            <h1>ezBIDS</h1>
            <themenu/>
        </el-header>
        <el-main>
            <router-view/>
        </el-main>
    </el-container>
</div>
</template>

<script>
//import EzBidsEditor from './components/EzBidsEditor.vue'
import themenu from './components/menu.vue'

import store from './store'

export default {
    store,
    components: {
        //EzBidsEditor
        themenu,
    },
    data() {
        return {
            /*
            site: "unknown site",
            datasetDescription: {},
            readme: "Enter README.md",
            participants: { "sub1": {}, "sub2": {} },
            participantsColumn: { "columnA": {}, "columnB": {} },
            */
        }
    },
    created() {
        //this.$root.loadData("ezbids_reference.json");
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
/*
.el-header, .el-footer {
    background-color: #B3C0D1;
    color: #333;
    text-align: center;
    line-height: 60px;
}
.el-main {
    background-color: #E9EEF3;
    color: #333;
    text-align: center;
    line-height: 160px;
}
body > .el-container {
    margin-bottom: 40px;
}
*/
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
