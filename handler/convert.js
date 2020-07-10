#!/usr/bin/env node

const fs = require('fs');
const mkdirp = require('mkdirp');
const async = require('async');

const root = process.argv[2];
if(!root) throw "please specify root directory";

const json = fs.readFileSync(root+"/finalized.json");
const info = JSON.parse(json);

fs.writeFileSync(root+"/bids/dataset_description.json", JSON.stringify(info.datasetDescription, null, 4));
fs.writeFileSync(root+"/bids/README.md", info.readme);
fs.writeFileSync(root+"/bids/participants.json", JSON.stringify(info.participantsColumn, null, 4));

//convert participants.json to tsv
let keys = [];
for(subject in info.participants) {
    let rec = info.participants[subject];
    for(key in rec) {
        if(!keys.includes(key)) keys.push(key);
    }
}
let tsv = [];
let tsvheader = [];
for(let key of keys) {
    tsvheader.push(key);
}
tsv.push(tsvheader);
for(let subject in info.participants) {
    let rec = info.participants[subject];
    let tsvrec = [];
    for(key of keys) {
        tsvrec.push(rec[key]);
    }
    tsv.push(tsvrec);
}

let tsvf = fs.openSync(root+"/participants.tsv", "w");
for(let rec of tsv) {
    fs.writeSync(tsvf, rec.join(",")+"\n");
}
fs.closeSync(tsvf);

//handle each objects
async.forEach(info.objects, (o, next_o)=>{
    if(!o.include) return next_o();

    //setup directory
    let path = "bids";
    if(o.hierarchy.subject) path += "/sub-"+o.hierarchy.subject;
    if(o.hierarchy.session) path += "/ses-"+o.hierarchy.subject;
    path += "/"+o.type.split("/")[0]; //func, dwi, anat, etc..
    mkdirp(root+"/"+path).then(()=>{
                
        //construct filepath
        let kv = {};
        for(let k in o.hierarchy) {
            let v = o.hierarchy[k];
            if(!v) continue;
            switch(k) {
            case "subject": 
                kv.sub = v;
                break;
            case "session": 
                kv.ses = v;
                break;
            default:
                kv[k] = v;
            }
        }

        let tokens = [];
        for(let k in kv) {
            tokens.push(k+"-"+kv[k]);
        }
        const name = tokens.join("_");
        //let format = o.type.split("/")[1];
        //console.log(path, name, format);

        function handleItem(item, filename, jsonname) {
            let goback = "";
            for(let i = 0;i < path.split("/").length; ++i) {
                goback += "../";
            }
            let linkpath = root+"/"+path+"/"+name+"_"+filename;
            try {
                fs.lstatSync(linkpath);
                fs.unlinkSync(linkpath);
            } catch (err) {
                //console.log("link doesn't exist yet");
            }
            console.log(linkpath);
            fs.symlinkSync(goback+item.path, linkpath);

            if(jsonname && item.sidecar) {
                console.log(name+"_"+jsonname);
                fs.writeFileSync(root+"/"+path+"/"+name+"_"+jsonname, JSON.stringify(item.sidecar, null, 4));
            }
        }

        switch(o.type) {
        case "anat/t1w":
            o.items.forEach(item=>{
                switch(item.id) {
                case "t1w":
                    handleItem(item, "T1w.nii.gz", "T1w.json");
                    break;
                }
            });
            break;
        case "func/bold":
            o.items.forEach(item=>{
                switch(item.id) {
                case "bold":
                    handleItem(item, "bold.nii.gz", "bold.json");
                    break;
                }
            });
            break;
        case "dwi":
            o.items.forEach(item=>{
                switch(item.id) {
                case "dwi":
                    handleItem(item, "dwi.nii.gz", "dwi.json");
                    break;
                case "bvec":
                    handleItem(item, "dwi.bvec");
                    break;
                case "bval":
                    handleItem(item, "dwi.bval");
                    break;
                }
            });
            break;
        default:
            console.error("unknown datatype:"+o.type);
        }

        /*
        let handler = handlers[o.type];
        if(!handler) {
            console.error("unknown datatype:"+o.type);
            return next_o();
        }
        handler(o, path, name, next_o);
        */


    });

    /*
    {
      include: true,
      description: 'FE_EPI_3echosTEST_Yiannis',
      date: '2019-08-02T12:34:33Z',
      hierarchy: { subject: '104', session: '', run: '', task: 'rest' },
      type: 'func/bold',
      task: '',
      labels: { dir: '' },
      items: [
        {
          id: 'bold',
          path: 'dcm2niix_ezBIDS/SUB102/DICOM_FE_EPI_3echosTEST_Yiannis_20181014181517_701_e1.nii',
          sidecar: [Object]
        }
      ],
      analysisResults: {
        VolumeCount: 70,
        messages: [ 'File appears to be functional multiecho' ],
        errors: [ 'N/A', 'Another' ],
        qc: {},
        filesize: 77988192
      },
      paths: [
        'dcm2niix_ezBIDS/SUB102/DICOM_FE_EPI_3echosTEST_Yiannis_20181014181517_701_e1.nii',
        'dcm2niix_ezBIDS/SUB102/DICOM_FE_EPI_3echosTEST_Yiannis_20181014181517_701_e1.json',
        'dcm2niix_ezBIDS/SUB102/DICOM_FE_EPI_3echosTEST_Yiannis_20181014181517_701_e2.nii',
        'dcm2niix_ezBIDS/SUB102/DICOM_FE_EPI_3echosTEST_Yiannis_20181014181517_701_e2.json',
        'dcm2niix_ezBIDS/SUB102/DICOM_FE_EPI_3echosTEST_Yiannis_20181014181517_701_e3.nii',
        'dcm2niix_ezBIDS/SUB102/DICOM_FE_EPI_3echosTEST_Yiannis_20181014181517_701_e3.json'
      ],
      validationErrors: []
    }
    */
});

const handler = {
    "anat/t1w": (o, path, name, next)=>{
           
    },
}
