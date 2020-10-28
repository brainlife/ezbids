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
mkdirp.sync(root + "/bids");
fs.writeFileSync(root + "/bids/dataset_description.json", JSON.stringify(info.datasetDescription, null, 4));
info.readme += `
## ezbids

This dataset was converted from DICOM to BIDS using ezbids (https://brainlife.io/ezbids)

`;
fs.writeFileSync(root + "/bids/README", info.readme);
fs.writeFileSync(root + "/bids/participants.json", JSON.stringify(info.participantsColumn, null, 4));
//convert participants.json to tsv
console.log("outputting participants.json/tsv");
let keys = ["participant_id"];
for (let key in info.participantsColumn) {
    keys.push(key);
}
let tsv = [];
let tsvheader = [];
for (let key of keys) {
    tsvheader.push(key);
}
tsv.push(tsvheader);
info.subjects.forEach(subject => {
    let tsvrec = [];
    tsvrec.push(subject.sub);
    for (let key in info.participantsColumn) {
        tsvrec.push(subject.phenotype[key]);
    }
    tsv.push(tsvrec);
});
let tsvf = fs.openSync(root + "/bids/participants.tsv", "w");
for (let rec of tsv) {
    fs.writeSync(tsvf, rec.join("\t") + "\n");
}
fs.closeSync(tsvf);
//handle each objects
console.log("outputting objects");
async.forEach(info.objects, (o, next_o) => {
    //if(!o.include) return next_o();
    if (o._type == "exclude")
        return next_o();
    let typeTokens = o._type.split("/");
    let modality = typeTokens[0]; //func, dwi, anat, etc..
    let suffix = typeTokens[1];
    //setup directory
    let path = "bids";
    path += "/sub-" + o._entities.sub;
    if (o._entities.ses)
        path += "/ses-" + o._entities.ses;
    path += "/" + modality;
    mkdirp.sync(root + "/" + path);
    //construct basename
    let tokens = [];
    for (let k in o._entities) {
        if (o._entities[k])
            tokens.push(k + "-" + o._entities[k]);
    }
    const name = tokens.join("_");
    function handleItem(item, filename) {
        let goback = "";
        for (let i = 0; i < path.split("/").length; ++i) {
            goback += "../";
        }
        let fullpath = root + "/" + path + "/" + name + "_" + filename;
        //console.log(item.name, fullpath);
        if (item.name == "json") {
            //we create sidecar from sidecar object (edited by the user)
            fs.writeFileSync(fullpath, JSON.stringify(item.sidecar, null, 4));
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
            //I need to use hardlink so that when archiver tries to create .zip in download API
            //the files will be found. As far as I know, archiver module can't de-reference 
            //symlinks
            //fs.symlinkSync(goback+item.path, fullpath);
            fs.linkSync(root + "/" + item.path, fullpath);
        }
    }
    switch (modality) {
        case "anat":
            /*
            - suffixes:
                - T1w
                - T2w
                - T1rho
                - T1map
                - T2map
                - T2star
                - FLAIR
                - FLASH
                - PD
                - PDmap
                - PDT2
                - inplaneT1
                - inplaneT2
                - angio
            */
            o.items.forEach(item => {
                switch (item.name) {
                    case "nii.gz":
                        handleItem(item, suffix + ".nii.gz");
                        break;
                    case "json":
                        //bids requires TaskName set on sidecar
                        handleItem(item, suffix + ".json");
                        break;
                    default:
                        console.error("unknown anat item name", item.name);
                }
            });
            break;
        case "func":
            /*
            - suffixes:
                - bold
                - cbv
                - phase
                - sbref
    
            */
            o.items.forEach(item => {
                switch (item.name) {
                    case "nii.gz":
                        handleItem(item, suffix + ".nii.gz");
                        break;
                    case "json":
                        item.sidecar.TaskName = o._entities.task;
                        handleItem(item, suffix + ".json");
                        break;
                    default:
                        console.error("unknown func item name", item.name);
                }
            });
            break;
        case "fmap":
            /*
            - suffixes:
                - phasediff
                - phase1
                - phase2
                - magnitude1
                - magnitude2
                - magnitude
                - fieldmap
            */
            o.items.forEach(item => {
                switch (item.name) {
                    case "nii.gz":
                        handleItem(item, suffix + ".nii.gz");
                        break;
                    case "json":
                        //handle IntendedFor
                        if (o.IntendedFor) {
                            item.sidecar.IntendedFor = [];
                            for (let idx of o.IntendedFor) {
                                console.log("intended for", idx);
                                const io = info.objects[idx];
                                //if intended object is not included, skip it
                                //if(io.included) continue;
                                if (io._type == "exclude")
                                    continue;
                                //doesn't make sense to intentend for its own object (I don't think this ever happens)
                                //if(io == o) continue;
                                console.log("intended for", io._type);
                                const iomodality = io._type.split("/")[0];
                                const suffix = io._type.split("/")[1];
                                //construct a path relative to the subject
                                let path = "";
                                if (io._entities.ses)
                                    path += "ses-" + io._entities.ses + "/";
                                path += iomodality + "/";
                                let tokens = [];
                                for (let k in io._entities) {
                                    if (io._entities[k])
                                        tokens.push(k + "-" + io._entities[k]);
                                }
                                path += tokens.join("_");
                                path += "_" + suffix + ".nii.gz"; //TODO - not sure if this is robust enough..
                                item.sidecar.IntendedFor.push(path);
                            }
                        }
                        handleItem(item, suffix + ".json");
                        break;
                    default:
                        console.error("unknown fmap item name", item.name);
                }
            });
            break;
        case "dwi":
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
                        console.error("unknown dwi item name", item.name);
                }
            });
            break;
        default:
            console.error("unknown datatype:" + o._type);
    }
    next_o();
});
//# sourceMappingURL=convert.js.map