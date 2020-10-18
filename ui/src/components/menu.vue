<template>
<div>
    <el-menu :default-active="value" 
        @select="handleSelect">
        <el-menu-item index="upload">Upload</el-menu-item>
        <el-menu-item index="description" :disabled="!$root.session">Description / README
            <el-tag type="danger" effect="dark" v-if="$root.descErrors > 0" size="mini">{{$root.descErrors}}</el-tag>
        </el-menu-item>
        <el-menu-item index="subjects" :disabled="!$root.analyzed">Subjects
            <el-tag type="danger" effect="dark" v-if="$root.subjectErrors > 0" size="mini">{{$root.subjectErrors}}</el-tag>
        </el-menu-item>
        <el-menu-item index="sessions" :disabled="!$root.analyzed">Sessions
            <el-tag type="danger" effect="dark" v-if="$root.sessionErrors > 0" size="mini">{{$root.sessionErrors}}</el-tag>
        </el-menu-item>
        <el-menu-item index="series" :disabled="!$root.analyzed">Series 
            <el-tag type="danger" effect="dark" v-if="$root.seriesErrors > 0" size="mini">{{$root.seriesErrors}}</el-tag>
        </el-menu-item>
        <el-menu-item index="participants" :disabled="!$root.analyzed">Participants
            <el-tag type="danger" effect="dark" v-if="$root.participantErrors > 0" size="mini">{{$root.participantErrors}}</el-tag>
        </el-menu-item>
        <el-menu-item index="objects" :disabled="!$root.analyzed || $root.seriesErrors > 0">BIDS Structure
            <el-tag type="danger" effect="dark" v-if="$root.objectErrors > 0" size="mini">{{$root.objectErrors}}</el-tag>
        </el-menu-item>
        <el-menu-item index="finalize" :disabled="!$root.analyzed || $root.objectErrors > 0 || $root.seriesErrors > 0">Finalize</el-menu-item>
    </el-menu>
</div>
</template>

<script>

export default {
    props: [
        'value'
    ],
    data() {
        return {
        }
    },
    methods: {
        handleSelect(key) {
            this.$emit("input", key);
        }
    },
    created() {
    },
}

</script>

<style scoped>
</style>
