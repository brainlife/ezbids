<template>
<pre v-html="content"/>
</template>

<script>

const Convert = require('ansi-to-html');
const convert = new Convert();

export default {
    props: {
        path: String,
        bgColor: String,
    },
    mounted() {
        console.log("fetching file", this.path);
        fetch(this.$root.apihost+'/download/'+this.$root.session._id+'/'+this.path).then(res=>res.text()).then(data=>{
            this.content = convert.toHtml(data);
        });
    },
    data() {
        return {
            content: null,
        }
    },
}


</script>
<style>
pre {
    background-color: #333;
    color: white;
    padding: 10px;
    margin: 0;
    max-height: 200px;
    overflow: auto;
}
</style>
