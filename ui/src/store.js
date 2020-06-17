import Vue from 'vue'
import Vuex from 'vuex'

Vue.use(Vuex)

export default new Vuex.Store({
    strict: process.env.NODE_ENV !== 'production',
    state: {
        ezBIDSVersion: "0.0.1",
        dataset_description: {
            "Name": "soichi",
            "BIDSVersion": "1.2.0",
            "License": "",
            "Authors": [ "" ],
            "Acknowledgments": "",
            "howtoacknowledge": "",
            "funding": "",
            "referencesandlinks": [ "" ],
            "datasetdoi": ""
        },
        README: "....",
        participants: {
            "subjects": [ 101, 102 ],
            "sessions": [ "", "" ],
            "education": {
                "longname": "education level",
                "description": "education level, self-rated by participant",
                "levels": {
                    "1": "finished primary school",
                    "2": "finished secondary school",
                    "3": "student at university",
                    "4": "has degree from university"
                }
            },
            "bmi": {
                "longname": "body mass index",
                "units": "kilograms per squared meters",
                "termurl": "http://purl.bioontology.org/ontology/snomedct/60621009"
            }
        },
        "site": "ayios_therissos",
        "objects": [
            {
                "include": true,
                "description": "st1w_3d_tfe_sag",
                "date": "2019-08-02T12:34:33Z",
                "bids-hierarchy": {
                    "subject": "101",
                    "session": "",
                    "run": "01"
                },
                "bids": {
                    "type": "anat",
                    "task": "",
                    "modality": "t1w",
                    "labels": {
                        "dir": ""
                    },
                    "path": {
                        "anat": "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub101/dicom_st1w_3d_tfe_sag_20181014171638_201.nii"
                    }
                },
                "unique-headers": {
                    "seriesnumber": "....",
                    "studyname": "....................",
                    "description": "...................."
                },
                "bids-sidecar": {
                    "something": 123,
                    "another": 567,
                },
                "analysis-results": {
                    "volumecount": 1,
                    "messages": [
                    "file appears to be a t1w anatomical"
                    ],
                    "errors": [
                        "n/a"
                    ],
                    "qc": { },
                    "filesize": 22282592
                },
                "paths": [
                    "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub101/dicom_st1w_3d_tfe_sag_20181014171638_201.nii",
                    "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub101/dicom_st1w_3d_tfe_sag_20181014171638_201.json"
                ]
            },
            {
                "include": true,
                "description": "fe_epi_3echostest_yiannis",
                "date": "2019-08-02T12:34:33Z",
                "bids-hierarchy": {
                    "subject": "102",
                    "session": "",
                    "run": "01"
                },
                "bids": {
                    "type": "func",
                    "task": "",
                    "modality": "multiecho",
                    "labels": {
                        "dir": ""
                    },
                    "path": {
                        "func": "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub102/dicom_fe_epi_3echostest_yiannis_20181014181517_701_e1.nii"
                    }
                },
                "unique-headers": {
                    "seriesnumber": "....",
                    "studyname": "....................",
                    "description": "...................."
                },
                "bids-sidecar": {
                    "something": 123,
                    "another": 567,
                },
                "analysis-results": {
                    "volumecount": 70,
                    "messages": [
                        "file appears to be functional multiecho"
                    ],
                    "errors": [
                        "n/a"
                    ],
                    "qc": {},
                    "filesize": 77988192
                },
                "paths": [
                    "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub102/dicom_fe_epi_3echostest_yiannis_20181014181517_701_e1.nii",
                    "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub102/dicom_fe_epi_3echostest_yiannis_20181014181517_701_e1.json",
                    "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub102/dicom_fe_epi_3echostest_yiannis_20181014181517_701_e2.nii",
                    "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub102/dicom_fe_epi_3echostest_yiannis_20181014181517_701_e2.json",
                    "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub102/dicom_fe_epi_3echostest_yiannis_20181014181517_701_e3.nii",
                    "/media/data/dlevitas/sample_data/dcm2niix_ezbids/sub102/dicom_fe_epi_3echostest_yiannis_20181014181517_701_e3.json"
                ]
            }
        ]
    },
    mutations: {
        //TODO .. causes mutation violation..
        load(state, url) {
            console.log("todo", state, url);
            /*
            console.log("loading json", url);
            fetch(url).then(res=>res.json()).then(conf=>{
                Object.assign(state, conf);
            });
            */
        },
        
        updateDatasetDescription(state, desc) {
            Object.assign(state.dataset_description, desc);
        },

        updateREADME(state, v) {
            state.README = v;
        },    
    }
})
