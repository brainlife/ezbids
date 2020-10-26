<template>
<div class="datatype" :class="{exclude: o._type == 'exclude'}" style="display: inline-block;">
    <span :style="{'background-color': color}" class="bull">&nbsp;</span> {{$root.getType(o)||'(Exclude)'}}
    <el-tag v-for="(v,k) in entities" :key="k" size="mini" type="info"><small>{{k}}-</small><b>{{v}}</b></el-tag>
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
    method: {
    },
    computed: {
        entities() {
            let ents = {};

            let series = this.$root.findSeries(this.o);
            for(let key in series.entities) {
                if(series.entities[key] == "") continue;
                ents[key] = series.entities[key];
            }
            
            for(let key in this.o.entities) {
                if(key == "sub") continue; 
                if(key == "ses") continue; 
                if(this.o.entities[key] == "") continue;
                ents[key] = this.o.entities[key];
            }
            return ents;
        },

        color() {
            const hash = this.o._type.split("").reduce(function(a,b){a=((a<<5)-a)+b.charCodeAt(0);return a&a},0); 
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
.exclude {
    opacity: 0.2;
}
</style>
