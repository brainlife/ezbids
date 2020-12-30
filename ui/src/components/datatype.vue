<template>
<div class="datatype" style="display: inline-block;">
    <span :style="{'background-color': color}" class="bull">&nbsp;</span> {{type}}
    <el-tag v-for="(v,k) in sessionEntities" :key="k" size="mini" type="info" style="margin-right: 3px;"><small>{{k}}-</small><b>{{v}}</b></el-tag>
</div>
</template>

<script>
export default {
    props: [ 'type', 'series_id', 'entities' ],
    data() {
        return {
            something: "whatever", 
        }
    },
    method: {
    },
    computed: {
        sessionEntities() {
            let ents = {};

            let series = this.$root.findSeries({series_id: this.series_id});
            for(let key in series.entities) {
                if(series.entities[key] == "") continue;
                ents[key] = series.entities[key];
            }
            
            for(let key in this.entities) {
                if(key == "sub") continue; 
                if(key == "ses") continue; 
                if(this.entities[key] == "") continue;
                ents[key] = this.entities[key];
            }
            return ents;
        },

        color() {
            const hash = this.type.split("").reduce(function(a,b){a=((a<<5)-a)+b.charCodeAt(0);return a&a},0); 
            const numhash = Math.abs(hash+12)%360;
            return "hsl("+(numhash%360)+", 50%, 55%)"; 
        },
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
</style>
