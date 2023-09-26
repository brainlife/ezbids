<template>
    <el-container direction="vertical" class="container">
        <LandingPageHeader />
        <el-main style="color: white;">
            <el-row style="height: 100%;">
                <el-col :span="1"></el-col>
                <el-col :span="22" style="display: flex; align-items: center; justify-content: center; width: 100%; height: 100%;">
                    <div class="not-found-message">
                        <h1>Page Not found</h1>
                        <p>The page you are looking for does not exist.</p>
                    </div>
                </el-col>
                <el-col :span="1"></el-col>
            </el-row>
        </el-main>
        <LandingPageFooter />
    </el-container>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import LandingPageFooter from './LandingPageFooter.vue';
import LandingPageHeader from './LandingPageHeader.vue';

export default defineComponent({
    components: {
    LandingPageFooter: LandingPageFooter,
    LandingPageHeader: LandingPageHeader
}
})
</script>
<style>
.container {
    height: 100vh;
}

.not-found-message {
    background-color: #20ab5c;
    padding: 2rem;
    border-radius: 4px;
    font-size: var(--el-font-size-extra-large);
}

.background-stripe {
    transform: skewY(-12deg);
    height: 50vh;
}
</style>

<!-- 3782e5 -->