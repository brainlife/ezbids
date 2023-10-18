<template>
    <el-affix>
        <el-header class="header">
            <el-row style="align-items: center;">
                <el-col :xs="0" :md="1" />
                <el-col :xs="24" :md="22">
                    <el-menu class="menu" :ellipsis="false" mode="horizontal">
                        <el-menu-item index="0" class="menu-item">ezBIDS</el-menu-item>
                        <div style="flex-grow: 1"></div>
                        <el-menu-item @click="openBrainLifeTeamPage" index="1" class="menu-item">
                            <el-icon>
                                <font-awesome-icon :icon="['fas', 'arrow-up-right-from-square']" />
                            </el-icon>
                            TEAM
                        </el-menu-item>
                        <el-menu-item index="2" class="menu-item">
                            <el-button
                                @click="redirectToBrainlifeAuth"
                                type="text"
                                style="font-size: var(--el-font-size-extra-large); font-family: unset; color: #3482e9;"
                                >{{ hasJWT ? "GET STARTED" : "LOG IN / REGISTER"}}</el-button
                            >
                            <!-- <RouterLink style="text-decoration: none;" to="/convert">LOG IN / REGISTER</RouterLink> -->
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
import { RouterLink } from 'vue-router';
import { mapState } from 'vuex';
import { hasJWT } from './lib';

export default defineComponent({
    computed: {
        ...mapState(['config']),
        hasJWT() {
            return hasJWT();
        }
    },
    components: {
        RouterLink: RouterLink,
    },
    methods: {
        openBrainLifeTeamPage() {
            window.open('https://brainlife.io/team/', '_blank');
        },
        redirectToBrainlifeAuth() {
            if (hasJWT()) {
                this.$router.push('/convert')
                return;
            }

            sessionStorage.setItem('auth_redirect', window.location.href);
            window.location.href = (this.config as {
                apihost: string;
                authSignIn: string;
                authSignOut: string;
                debug: boolean;
            }).authSignIn;
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
