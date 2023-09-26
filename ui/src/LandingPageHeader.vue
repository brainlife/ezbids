
<template>
    <el-affix>
        <el-header style="background-color: white; height: 62px; padding: 0">
            <el-row style="align-items: center;">
                <el-col :span="1" />
                <el-col :span="22">
                    <el-menu style="margin: 0 auto; border-bottom: 1px solid transparent !important;" :ellipsis="false" mode="horizontal">
                        <el-menu-item index="0" style="font-size: 2rem; color: #3482e9">ezBIDS</el-menu-item>
                        <div style="flex-grow: 1"></div>
                        <el-menu-item @click="openBrainLifeTeamPage" index="1" style="font-size: var(--el-font-size-extra-large); color: #3482e9">
                            <el-icon>
                                <font-awesome-icon :icon="[ 'fas', 'arrow-up-right-from-square' ]" />
                            </el-icon>
                            TEAM
                        </el-menu-item>
                        <el-menu-item index="2" style="font-size: var(--el-font-size-extra-large); color: #3482e9">
                            <RouterLink style="text-decoration: none;" to="/convert">GET STARTED</RouterLink>
                        </el-menu-item>
                    </el-menu>
                </el-col>
                <el-col :span="1" />
            </el-row>
        </el-header>
    </el-affix>
</template>
    
<script lang="ts">
import { defineComponent } from 'vue';
import { RouterLink } from 'vue-router';

export default defineComponent({
    components: {
        RouterLink: RouterLink
    },
    methods: {
        openBrainLifeTeamPage() {
            window.open("https://brainlife.io/team/", "_blank");
        }
    }
})
</script>