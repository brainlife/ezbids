<template>
<div>
    <el-menu :default-active="$route.path" mode="horizontal" :router="true">
        <el-menu-item index="/upload">Upload</el-menu-item>
        <el-menu-item index="/preprocess" :disabled="!$root.session">Preprocess</el-menu-item>
        <el-menu-item index="/description" :disabled="!$root.analyzed">Description / README</el-menu-item>
        <el-menu-item index="/participants" :disabled="!$root.analyzed">Participants</el-menu-item>
        <el-menu-item index="/objects" :disabled="!$root.analyzed">DICOM / BIDS Mappings</el-menu-item>
        <el-menu-item index="/finalize" :disabled="!$root.validated">Finalize</el-menu-item>
    </el-menu>
    <!--
    <router-link to="/upload">Upload</router-link>
    <router-link to="/preprocess">Preprocess</router-link>
    <router-link to="/description">Description</router-link>
    <router-link to="/readme">Readme</router-link>
    <router-link to="/participants">Participants</router-link>
    <router-link to="/objects">Data Objects</router-link>
    -->
</div>
</template>

<script>

export default {
    /*
    props: [
        'conf'
    ],
    */
    data() {
        return {
            //active: "1",
        }
    },
    created() {
        /*
        switch(this.$route.path) {
        case "/upload": this.active = "1"; break;
        case "/preprocess": this.active = "2"; break;
        case "/description": this.active = "/description"; break;
        }
        */
    },
}


</script>
