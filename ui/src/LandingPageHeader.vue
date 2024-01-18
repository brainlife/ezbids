<template>
    <el-affix>
        <el-header class="header">
            <el-row style="align-items: center">
                <el-col :xs="0" :md="1" />
                <el-col :xs="24" :md="22">
                    <el-menu class="menu" :ellipsis="false" mode="horizontal">
                        <el-menu-item index="0" class="menu-item">ezBIDS</el-menu-item>
                        <div style="flex-grow: 1"></div>
                        <el-menu-item index="1" class="menu-item" @click="openBrainLifeTeamPage">
                            <el-icon>
                                <font-awesome-icon :icon="['fas', 'arrow-up-right-from-square']" />
                            </el-icon>
                            TEAM
                        </el-menu-item>
                        <el-menu-item index="2" class="menu-item">
                            <el-button
                                type="text"
                                style="font-size: var(--el-font-size-extra-large); font-family: unset; color: #3482e9"
                                @click="redirectToBrainlifeAuth"
                                >{{ !hasAuth || hasJWT ? 'GET STARTED' : 'LOG IN / REGISTER' }}</el-button
                            >
                        </el-menu-item>
                    </el-menu>
                </el-col>
                <el-col :xs="0" :md="1" />
            </el-row>
        </el-header>
    </el-affix>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { mapState } from 'vuex';
import { hasJWT, hasAuth } from './lib';

export default defineComponent({
    computed: {
        ...mapState(['config']),
        hasAuth() {
            return hasAuth();
        },
        hasJWT() {
            return hasJWT();
        },
    },
    methods: {
        openBrainLifeTeamPage() {
            window.open('https://brainlife.io/team/', '_blank');
        },
        redirectToBrainlifeAuth() {
            if (!hasAuth() || hasJWT()) {
                this.$router.push('/convert');
                return;
            }

            sessionStorage.setItem('auth_redirect', `${window.location.href}convert`);
            window.location.href = (
                this.config as {
                    apihost: string;
                    authSignIn: string;
                    authSignOut: string;
                    debug: boolean;
                }
            ).authSignIn;
        },
    },
});
</script>

<style scoped>
/* for screens smaller than 992px */
@media screen and (max-width: 992px) {
    .menu-item {
        font-size: var(--el-font-size-small) !important;
    }
}

.header {
    background-color: white;
    height: 62px;
    padding: 0;
}

.menu {
    margin: 0 auto;
    border-bottom: 1px solid transparent !important;
}

.menu-item {
    font-size: var(--el-font-size-extra-large);
    color: #3482e9;
}
</style>
