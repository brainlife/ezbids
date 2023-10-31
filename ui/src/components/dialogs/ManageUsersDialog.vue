<template>
    <div v-if="shareSessionButtonIsVisible">
        <div style="padding: 0 10px">
            <el-badge :value="allowedUserProfiles.length === 0 ? undefined : allowedUserProfiles.length" style="width: 135px">
                <el-button @click="dialogIsVisible = true" class="share-session-button" type="primary">
                    Share session
                </el-button>
            </el-badge>
        </div>
        <el-dialog :append-to-body="true" title="Share session with other users" v-model="dialogIsVisible" :before-close="handleClose">
            <div style="width: 100%">
                <h3 style="margin-bottom: 0;">Sharing with</h3>
                <p style="color: rgb(167, 167, 167)">The following users have access to this session</p>
                <div>
                    <p style="color: rgb(217 190 46)" v-if="allowedUserProfiles.length === 0">No users added</p>
                    <div v-else>
                        <el-tag
                            style="margin: 4px"
                            size="large"
                            closable
                            v-for="allowedUser in allowedUserProfiles"
                            :key="allowedUser?.sub"
                            @close="handleRemoveProfile(allowedUser?.sub)"
                            
                        >
                            {{ allowedUser?.fullname || '' }} {{ `<${allowedUser?.email}>` }}
                        </el-tag>
                    </div>
                </div>
                <h3 style="margin-bottom: 0">Find users</h3>
                <p style="margin-top: 10px; color: rgb(167, 167, 167)">Use the dropdown to search for other brainlife users </p>
                <el-autocomplete
                    :trigger-on-focus="false"
                    style="width: 100%"
                    clearable
                    v-model="userInput"
                    :value-key="'fullname'"
                    @select="handleSelectProfile"
                    placeholder="start typing to see results"
                    :fetch-suggestions="handleFetchSuggestions"
                >
                    <template #default="{ item }">
                        <div>
                            <p style="margin: 0">{{ item.fullname }} {{ `<${item.email}>` }}</p>
                        </div>
                    </template>
                    <template #suffix>
                        <el-container v-loading="isLoading" class="autocomplete-loader">
                        </el-container>
                    </template>
                </el-autocomplete>
            </div>
            <template #footer>
                <el-button @click="handleClose" type="danger">Close Dialog</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script lang="ts">

interface Profile {
    active?: boolean;
    email?: string;
    fullname?: string;
    profile?: {
        public: {
            bio?: string;
            institution?: string;
        }
    },
    sub?: number;
    username?: string;
    _id: string;
}

import { defineComponent } from 'vue'
import { mapActions, mapState } from 'vuex';
import axios from '../../axios.instance';
import jwtDecode from 'jwt-decode';
import { ElNotification } from 'element-plus';
import { retrieveJWT } from '../../lib';

export default defineComponent({
    data() {
        return {
            dialogIsVisible: false,
            profiles: [] as Profile[],
            userInput: '',
            isLoading: false
        }
    },
    computed: {
        ...mapState(['session', 'config']),
        ...mapActions(['updateSessionAllowedUsers']),
        allowedUserProfiles() {
            const allowedUserList: number[] = this.session?.allowedUsers || [];
            return allowedUserList.map((allowedUserSub) => this.profiles.find((profile) => profile.sub === allowedUserSub));
        },
        shareSessionButtonIsVisible() {
            if (!this.session) return false;

            const jwt = retrieveJWT();
            if (!jwt) return false;

            const decoded: { sub: Partial<Profile> } = jwtDecode(jwt);
            if (!decoded?.sub) return false;

            return decoded.sub === this.session.ownerId
        }
    },
    methods: {
        handleClose() {
            this.dialogIsVisible = false
        },
        handleSelectProfile(profile: Profile) {
            if (!this.session || !this.session.allowedUsers) return;
            if (!profile?.sub || !profile?.email) return;

            this.userInput = '';
            const updatedUsers: number[] = [...this.session.allowedUsers, profile.sub];
            this.isLoading = true;

            axios.patch(`${this.config.apihost}/session/${this.session._id}`, {
                allowedUsers: updatedUsers
            }).then((res) => {
                this.$store.commit('updateSessionAllowedUsers', updatedUsers);
            }).catch((err) => {
                console.error(err)
                ElNotification({
                    title: 'There was an error sharing the session with other users',
                    type: 'error'
                })
            }).finally(() => {
                this.isLoading = false
            })
        },
        handleRemoveProfile(allowedUserSub?: number) {
            if (!allowedUserSub || !this.session?.allowedUsers) return;

            const updatedUsers: number[] = [...this.session.allowedUsers.filter((user: number) => user !== allowedUserSub)];
            this.isLoading = true;

            axios.patch(`${this.config.apihost}/session/${this.session._id}`, {
                allowedUsers: updatedUsers
            }).then((res) => {
                console.log(res)
                this.$store.commit('updateSessionAllowedUsers', updatedUsers);
            }).catch((err) => {
                console.error(err)
                ElNotification({
                    title: 'There was an error removing the user from the session',
                    type: 'error'
                })
            }).finally(() => {
                this.isLoading = false
            })
        },
        handleFetchSuggestions(queryString: string | undefined, cb: any) {
            if (!queryString) {
                cb([]);
                return;
            }
            const transformedQuery = queryString.toLocaleLowerCase();

            const results = this.profiles.filter((profile: Profile) => {
                const lowercaseEmail = (profile?.email || '').toLocaleLowerCase();
                const lowerCaseFullname = (profile?.fullname || '').toLocaleLowerCase();
                return lowercaseEmail.includes(transformedQuery) || lowerCaseFullname.includes(transformedQuery);
            });

            const alreadySharedWithList: number[] = [this.session?.ownerId , ...(this.session?.allowedUsers || [])]
            cb(results.filter((result) => result?.sub ? !alreadySharedWithList.includes(result.sub) : false));
            return;
        }
    },
    mounted() {
        axios.get<{ count: number; profiles: Profile[] }>(`${this.config.authhost}/profile/list`).then((res) => {
            this.profiles = res?.data?.profiles ? [...res.data.profiles] : []
        }).catch((e) => {
            console.error(e)
        })
    }
})
</script>

<style lang="scss">
.muted {
    color: gray;
}

.autocomplete-loader {
    width: 40px;
    height: 40px;
    .el-loading-mask {
        background-color: transparent !important;
    }
    svg {
        width: 30px !important;
    }
}

.share-session-button {
    display: flex;
    justify-content: center;
    width: 100%;
    margin-bottom: 10px;
    font-family: Merriweather Sans;
}
</style>