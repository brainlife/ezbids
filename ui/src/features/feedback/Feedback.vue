<template>
    <div class="feedback-page">
        <header class="feedback-hero">
            <h1 class="feedback-hero__title">Thank you for using ezBIDS!</h1>
            <p class="feedback-hero__text">
                You can close this tab now, or start over if you would like to convert another dataset.
            </p>
            <el-button size="default" @click="restart">Back to Dashboard</el-button>
        </header>

        <section class="feedback-card">
            <h2>Feedback and Comments</h2>
            <p>
                ezBIDS is a brand new web service and your feedback is extremely valuable. Please email
                <a href="mailto:pestilli@utexas.edu" target="mail">pestilli@utexas.edu</a> with your experience,
                comments, or suggestions.
            </p>
            <p>
                If you ran into an issue while using ezBIDS, please open a
                <a href="https://github.com/brainlife/ezbids/issues" target="github">GitHub issue</a>.
            </p>
        </section>

        <section class="feedback-card">
            <h2>Funded By</h2>
            <p>ezBIDS was made possible by the following funding sources.</p>
            <div class="funding-badges">
                <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1734853"
                    ><img src="https://img.shields.io/badge/NSF_BCS-1734853-blue.svg"
                /></a>
                <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1636893"
                    ><img src="https://img.shields.io/badge/NSF_BCS-1636893-blue.svg"
                /></a>
                <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1916518"
                    ><img src="https://img.shields.io/badge/NSF_ACI-1916518-blue.svg"
                /></a>
                <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1912270"
                    ><img src="https://img.shields.io/badge/NSF_IIS-1912270-blue.svg"
                /></a>
                <a href="https://grantome.com/grant/NIH/R01-EB029272-01"
                    ><img src="https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg"
                /></a>
            </div>
        </section>

        <section class="feedback-card">
            <h2>ezBIDS Team</h2>
            <div class="avatars">
                <div class="avatar">
                    <img src="@/assets/images/DanLevitas.png" alt="Dan Levitas" />
                    <b><a href="mailto:dlevitas@iu.edu" target="mail">Dan Levitas</a></b>
                    <span>Software Engineer</span>
                </div>
                <div class="avatar">
                    <img src="@/assets/images/franco.jpg" alt="Franco Pestilli" />
                    <b><a href="mailto:pestilli@utexas.edu" target="mail">Franco Pestilli</a></b>
                    <span>Associate Professor</span>
                </div>
                <div class="avatar">
                    <img src="@/assets/images/soichi.jpg" alt="Soichi Hayashi" />
                    <b><a href="mailto:hayashis@iu.edu" target="mail">Soichi Hayashi</a></b>
                    <span>Technical Lead</span>
                </div>
                <div class="avatar">
                    <img src="@/assets/images/Anibal.png" alt="Anibal S. Heinsfeld" />
                    <b><a href="mailto:anibalsolon@utexas.edu" target="mail">Anibal S. Heinsfeld</a></b>
                    <span>Software Engineer</span>
                </div>
                <div class="avatar">
                    <img src="@/assets/images/DheerajBhatia.png" alt="Dheeraj Bhatia" />
                    <b><a href="mailto:dheeraj.bhatia@austin.utexas.edu" target="mail">Dheeraj Bhatia</a></b>
                    <span>Software Engineer</span>
                </div>
                <div class="avatar">
                    <img src="@/assets/images/NickLee.jpeg" alt="Nick Lee" />
                    <b><a href="mailto:niconal902@gmail.com" target="mail">Nick Lee</a></b>
                    <span>Software Engineer</span>
                </div>
            </div>
        </section>
    </div>
</template>

<script lang="ts">
//import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue';
//import { ElNotification } from 'element-plus'

export default defineComponent({
    methods: {
        restart() {
            this.$router.push('/dashboard');
        },
    },
});
</script>

<style lang="scss" scoped>
a {
    color: #409eff;
}

.feedback-page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0.5rem 1.25rem 2.75rem;
}

.feedback-hero {
    margin-bottom: 1.25rem;
    padding: 1.35rem 1.5rem 1.5rem;
    border-radius: 10px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-fill-color-blank, #fff);
    box-shadow: 0 1px 2px rgb(0 0 0 / 4%);
}

.feedback-hero__title {
    margin: 0 0 0.65rem;
    font-size: 1.45rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--el-text-color-primary, #303133);
}

.feedback-hero__text {
    margin: 0 0 1rem;
    line-height: 1.6;
    color: var(--el-text-color-regular, #606266);
}

.feedback-card {
    padding: 1.1rem 1.25rem;
    border-radius: 12px;
    border: 1px solid var(--el-border-color-lighter, #ebeef5);
    background: var(--el-bg-color, #fff);
    margin-bottom: 1rem;
}

.feedback-card h2 {
    margin: 0 0 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
    font-size: 1.1rem;
}

.funding-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

p {
    opacity: 0.9;
    line-height: 1.6;
}

.avatars {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 0.9rem;

    .avatar {
        padding: 0.9rem 0.75rem 1rem;
        border-radius: 10px;
        border: 1px solid var(--el-border-color-lighter, #ebeef5);
        background: #fafafa;
        text-align: center;
        font-size: 1rem;
        color: #0009;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.35rem;

        img {
            border-radius: 50%;
            width: 120px;
            height: 120px;
            object-fit: cover;
            border: 3px solid #fff;
            box-shadow: 0 1px 4px rgb(0 0 0 / 12%);
        }

        b {
            margin-top: 0.35rem;
        }

        span {
            font-size: 0.92rem;
            color: #606266;
        }
    }
}
</style>
