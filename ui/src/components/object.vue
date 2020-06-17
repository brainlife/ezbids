<template>
<div>
    <el-input v-model="obj.description" size="small">
        <template slot="prepend">Description</template>
    </el-input>
    <!--

    <h4>Sidecar</h4>
    <el-input type="textarea" :rows="5" v-model="sidecar" size="small"/>
    
    <h4>paths</h4>
    <time>{{new Date(obj.date).toLocaleString()}}</time>
    <pre v-for="(path, idx) in obj.paths" :key="idx">{{path}}</pre>
    -->
    <pre>{{obj}}</pre>
</div>
</template>

<script>

export default {
    props: [
        'obj'

        //read only things
        //date: new Date("17:27:31.710000"),
        //paths //list of all paths for this object
        //analysis-results
    ],
    computed: {
        /*
        include:  {
            get() {
                return this.obj.include;
            },
            set(v) {
                return this.obj.include = v;
            }
        },
        description:  {
            get() {
                return this.obj.description;
            },
            set(v) {
                return this.obj.description = v;
            }
        }
        */
    },
    data() {
        return {
            /*
            //active: "1",
            include: true,
            description: "",
            "bids-hierarchy": {
                subject: "101",
                session: "",
                run: "01"
            },
            bids: {
                type: "anat",
                task: "",
                modality: "t1w",
                labels: {
                    dir: ""
                },
                path: {
                  //"anat": "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub101/dicom_st1w_3d_tfe_sag_20181014171638_201.nii"
                }
            },
            sidecar: "", //parsed from bids-sidecar
            */
        }
    },
    created() {
        /*
        switch(this.$route.path) {
        case "/upload": this.active = "1"; break;
        case "/preprocess": this.active = "2"; break;
        case "/description": this.active = "/description"; break;
        }
        */
        //this.loadObj();
    },

    methods: {
        /*
        loadObj() {
            this.include = this.obj.include;
            this.description = this.obj.description;
            this.date = this.obj.date;
            Object.assign(this["bids-hierarchy"], this.obj["bids-hierarchy"]);
            Object.assign(this["bids"], this.obj["bids"]);
            //Object.assign(this["bids-sidecar"], this.obj["bids-sidecar"]);
            this.sidecar = JSON.stringify(this.obj["bids-sidecar"], null, 4);
        },
        */
    },
}

</script>
