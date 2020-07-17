<template>
<div class="datatype" :class="{exclude: !o.include}" style="display: inline-block;">
    <span :style="{'background-color': color}" class="bull">&nbsp;</span> {{o.type}}
    <el-tag v-for="(v,k) in o.labels" :key="k" size="mini" type="info"><small>{{k}}</small> <b>{{v.toUpperCase()}}</b></el-tag>
</div>
</template>

<script>

export default {
    props: [ 'o' ],
    data() {
        return {
            something: "whatever", 
        }
    },
    computed: {
        color() {
            const hash = this.o.type.split("").reduce(function(a,b){a=((a<<5)-a)+b.charCodeAt(0);return a&a},0); 
            const numhash = Math.abs(hash+12)%360;
            return "hsl("+(numhash%360)+", 50%, 55%)"; 
        },
        /*
        specialHierarchy() {
            const kv = {};
            let ignore = ["subject", "session", "run"];
            for(let k in this.o.hierarchy) {
                if(ignore.includes(k)) continue;
                kv[k] = this.o.hierarchy[k]; 
            }
            return kv;
        }
        */
    },
}

</script>
<style scoped>
.datatype {
font-size: 90%;
}
.bull {
    width: 8px;
    height: 8px;
    display: inline-block;
    border-radius: 50%;
}
.exclude {
    opacity: 0.2;
}
</style>
