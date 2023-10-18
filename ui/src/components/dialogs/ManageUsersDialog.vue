<template>
    <div>
        <div style="padding: 0 10px">
            <el-badge :value="3" style="width: 135px">
                <el-button @click="dialogIsVisible = true" style="display: flex; justify-content: center; width: 100%;" type="primary">
                    Sharing Settings
                    <font-awesome-icon :icon="['fa', 'users']" />
                </el-button>
            </el-badge>
        </div>
        <el-dialog title="Session Sharing Settings" v-model="dialogIsVisible" :before-close="handleClose">
            <div style="width: 100%">
                <h4>The following users can access this session:</h4>
                ...
                <h4>Share session with other brainlife users:</h4>
                <el-autocomplete style="width: 100%" clearable placeholder="Start typing to search for brainlife users"></el-autocomplete>
            </div>
            <template #footer>
                <el-button @click="handleClose" type="danger">Close Dialog</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script lang="ts">
import axios from 'axios'
import { defineComponent } from 'vue'

export default defineComponent({
    data() {
        return {
            dialogIsVisible: false,
            profiles: []
        }
    },
    methods: {
        handleClose() {
            this.dialogIsVisible = false
        }
    },
    mounted() {
        axios.get('http://localhost:8080/api/auth/profile/list').then((res) => {
            console.log(res)
            this.profiles = res.data.profiles
        }).catch((e) => {
            console.error(e)
        })
    }
})
</script>

<style scoped>
.muted {
    color: gray;
}
</style>