<template>
<div class="datatype" style="display: inline;">
    <span :style="{'backgroundColor': color}" class="bull">&nbsp;</span> {{type}}
    <el-tag v-for="(v,k) in sessionEntities" :key="k" size="mini" effect="plain" type="info" 
        style="margin-right: 3px;"><small>{{k}}-</small><b>{{v}}</b></el-tag>
</div>
</template>

<script lang="ts">

import { mapState } from 'vuex'
import { defineComponent } from 'vue'

export default defineComponent({
    props: [ 'type', 'series_idx', 'entities' ],
    data() {
        return {
            something: "whatever", 
        }
    },
    
    method: {
    },

    computed: {
        ...mapState(["ezbids"]),

        sessionEntities() {
            let ents = {} as any;

            let series = this.ezbids.series[this.series_idx];
            if(!series) return {};
            for(let key in series.entities) {
                if(series.entities[key] == "") continue;
                ents[key] = series.entities[key];
            }
            
            for(let key in this.entities) {
                if(key == "subject") continue; 
                if(key == "session") continue; 
                if(this.entities[key] == "") continue;
                ents[key] = this.entities[key];
            }
            return ents;
        },

        color() {
            if(this.type == "exclude") return "hsl(0, 100%, 40%)";
            const hash = this.type.split("").reduce(function(a:number,b:string){a=((a<<5)-a)+b.charCodeAt(0);return a&a},0);          
            let numhash = Math.abs(hash+12)%360;   
            return "hsl("+(numhash%360)+", 50%, 55%)"; 
        },
    },
});

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
    position: relative;
    top: 3px;
}
</style>
