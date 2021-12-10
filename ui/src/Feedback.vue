<template>
<div style="padding: 20px;">
    <h1>Thank you for using ezBIDS!</h1>
    <p>You can close this tab now. Or&nbsp;&nbsp;<el-button type="primary" @click="restart" size="small">Start Over</el-button>&nbsp;&nbsp;if you'd like to convert another dataset.</p>

    <h2>Feedbacks / Comments</h2>
    <p>ezBIDS is a brand new web service! Your feedback is extremely valuable to us. Please send us an email at <a href="mailto:ezbids@brainlife.io" target="mail">ezbids@brainlife.io</a> describing your experience with ezBIDS, any feedbacks / comments / suggestions.</p>
    <p>If you have experienced any issues while using ezBIDS, please submit an <a href="https://github.com/brainlife/ezbids/issues" target="github">Github Issues</a></p>

    <h2>Citations</h2>
    <p>Please use the following citation for ezBIDS.</p>
    <p class="citation">Avesani, P., McPherson, B., Hayashi, S. et al. The open diffusion data derivatives, brain data upcycling via integrated publishing of derivatives and reproducible open cloud services. Sci Data 6, 69 (2019). https://doi.org/10.1038/s41597-019-0073-y</p>

    <h2>Team Members</h2>
    <div class="avatars">
        <div class="avatar">
            <img src="./assets/images/DanLevitas.png" width="200"/>
            <br>
            <b><a href="mailto:dlevitas@iu.edu" target="mail">Dan Levitas</a></b><br>
            Software Engineer
        </div>
        <div class="avatar">
            <img src="./assets/images/franco.jpg" width="200"/>
            <br>
            <b><a href="mailto:pestilli@utexas.edu" target="mail">Franco Pestilli</a></b><br>
            Associate Professor
        </div>
        <div class="avatar">
            <img src="./assets/images/soichi.jpg" width="200"/>
            <br>
            <b><a href="mailto:hayashis@iu.edu" target="mail">Soichi Hayashi</a></b><br>
            Technical Lead
        </div>
    </div>

    <h2>Funded By</h2>
    <p>ezBIDS was made possible by the following funding sources.</p>

    <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1734853"><img src="https://img.shields.io/badge/NSF_BCS-1734853-blue.svg"></a>
    &nbsp;
    <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1636893"><img src="https://img.shields.io/badge/NSF_BCS-1636893-blue.svg"></a>
    &nbsp;
    <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1916518"><img src="https://img.shields.io/badge/NSF_ACI-1916518-blue.svg"></a>
    &nbsp;
    <a href="https://nsf.gov/awardsearch/showAward?AWD_ID=1912270"><img src="https://img.shields.io/badge/NSF_IIS-1912270-blue.svg"></a>
    &nbsp;
    <a href="https://grantome.com/grant/NIH/R01-EB029272-01"><img src="https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg"></a>
    &nbsp;

</div>
</template>

<script lang="ts">

//import { mapState, mapGetters, } from 'vuex'
import { defineComponent } from 'vue'
//import { ElNotification } from 'element-plus'

export default defineComponent({
    methods: {
        restart() {
            document.location.hash = "";
            document.location.reload();
        },
    },
});

</script>

<style lang="scss" scoped>
a {
    color: #409eff;
}
.citation {
    padding: 10px;
    background-color: #0002;
}
h2 {
    padding-bottom: 5px;
    border-bottom: 1px solid #0003;
    margin-bottom: 5px;
}
p {
    opacity: 0.8;
}
.avatars {
    .avatar {
        display: inline-block;
        width: 300px;
        padding: 10px;
        margin-bottom: 20px;
        img {
            border-radius: 50%;
            margin-bottom: 20px;
        }
        text-align: center;
        font-size: 125%;
        color: #0009;

    }
}
</style>


