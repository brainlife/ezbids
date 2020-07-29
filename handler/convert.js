#!/usr/bin/env node
"use strict";
const fs = require('fs');
const mkdirp = require('mkdirp');
const async = require('async');
const root = process.argv[2];
if (!root)
    throw "please specify root directory";
const json = fs.readFileSync(root + "/finalized.json");
const info = JSON.parse(json);
console.log(info);
mkdirp.sync(root + "/bids");
fs.writeFileSync(root + "/bids/dataset_description.json", JSON.stringify(info.datasetDescription, null, 4));
fs.writeFileSync(root + "/bids/README.md", info.readme);
fs.writeFileSync(root + "/bids/participants.json", JSON.stringify(info.participantsColumn, null, 4));
//convert participants.json to tsv
console.log("outputting participants.json/tsv");
let keys = [];
for (let subject in info.participants) {
    let rec = info.participants[subject];
    for (let key in rec) {
        if (!keys.includes(key))
            keys.push(key);
    }
}
let tsv = [];
let tsvheader = [];
for (let key of keys) {
    tsvheader.push(key);
}
tsv.push(tsvheader);
for (let subject in info.participants) {
    let rec = info.participants[subject];
    let tsvrec = [];
    for (let key of keys) {
        tsvrec.push(rec[key]);
    }
    tsv.push(tsvrec);
}
let tsvf = fs.openSync(root + "/bids/participants.tsv", "w");
for (let rec of tsv) {
    fs.writeSync(tsvf, rec.join(",") + "\n");
}
fs.closeSync(tsvf);
//handle each objects
console.log("outputting objects");
async.forEach(info.objects, (o, next_o) => {
    if (!o.include)
        return next_o();
    //setup directory
    let path = "bids";
    if (o.entities.sub)
        path += "/sub-" + o.entities.sub;
    if (o.entities.ses)
        path += "/ses-" + o.entities.ses;
    path += "/" + o.type.split("/")[0]; //func, dwi, anat, etc..
    mkdirp.sync(root + "/" + path);
    //load series
    let series = info.series.find(s => s.SeriesDescription == o.SeriesDescription);
    //construct basename
    let tokens = [];
    for (let k in o.entities) {
        let sv = series.entities[k];
        let ov = o.entities[k];
        if (!sv && !ov)
            continue;
        tokens.push(k + "-" + (ov || sv)); //object entity takes precedence
    }
    const name = tokens.join("_");
    function handleItem(item, filename) {
        let goback = "";
        for (let i = 0; i < path.split("/").length; ++i) {
            goback += "../";
        }
        let fullpath = root + "/" + path + "/" + name + "_" + filename;
        console.log(item.name, fullpath);
        if (item.name == "json") {
            //we create sidecar from sidecar object
            fs.writeFileSync(fullpath, JSON.stringify(item.sidecar));
        }
        else {
            //assume to be normal files
            try {
                fs.lstatSync(fullpath);
                fs.unlinkSync(fullpath);
            }
            catch (err) {
                //console.log("link doesn't exist yet");
            }
            fs.symlinkSync(goback + item.path, fullpath);
        }
        /*
        if(jsonname && item.sidecar) {
            console.log(name+"_"+jsonname);
            fs.writeFileSync(root+"/"+path+"/"+name+"_"+jsonname, JSON.stringify(item.sidecar, null, 4));
        }
        */
    }
    //console.log(path, name, o.type);
    switch (o.type) {
        case "anat/T1w":
            o.items.forEach(item => {
                switch (item.name) {
                    case "nii.gz":
                        handleItem(item, "T1w.nii.gz");
                        break;
                    case "json":
                        handleItem(item, "T1w.json");
                        break;
                    default:
                        console.error("unknown item name", item.name);
                }
            });
            break;
        case "func/bold":
            o.items.forEach(item => {
                switch (item.name) {
                    case "nii.gz":
                        handleItem(item, "bold.nii.gz");
                        break;
                    case "json":
                        handleItem(item, "bold.json");
                        break;
                    default:
                        console.error("unknown item name", item.name);
                }
            });
            break;
        case "dwi/dwi":
            o.items.forEach(item => {
                switch (item.name) {
                    case "nii.gz":
                        handleItem(item, "dwi.nii.gz");
                        break;
                    case "bvec":
                        handleItem(item, "dwi.bvec");
                        break;
                    case "bval":
                        handleItem(item, "dwi.bval");
                        break;
                    case "json":
                        handleItem(item, "dwi.json");
                        break;
                    default:
                        console.error("unknown item name", item.name);
                }
            });
            break;
        default:
            console.error("unknown datatype:" + o.type);
    }
    next_o();
});
//# sourceMappingURL=convert.js.map