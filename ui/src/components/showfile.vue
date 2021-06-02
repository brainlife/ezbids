<template>
<pre v-html="content" :style="{maxHeight, height}"/>
</template>

<script>

const Convert = require('ansi-to-html');
const convert = new Convert();

export default {
    props: {
        path: String,
        tall: {
            type: Boolean,
            default: false
        },
    },
    data() {
        return {
            content: null,
            maxHeight: "200px",
            height: "200px",
        }
    },
    mounted() {
        console.log("fetching file", this.path);
        fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/'+this.path).then(res=>res.text()).then(data=>{
            this.content = convert.toHtml(data);
        });

        if(this.tall) {
            console.log("using tall");
            this.maxHeight = "400px";
            this.height = "400px";
        }
    },
}


</script>
<style scoped>
pre {
    background-color: #333;
    color: white;
    padding: 10px;
    margin: 0;
    overflow: auto;
}
</style>
