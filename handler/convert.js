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
const datasetName = info.datasetDescription.Name;
mkdirp.sync(root + "/bids/" + datasetName);
fs.writeFileSync(root + "/bids/" + datasetName + "/finalized.json", JSON.stringify(info, null, 4)); //copy the finalized.json
fs.writeFileSync(root + "/bids/" + datasetName + "/dataset_description.json", JSON.stringify(info.datasetDescription, null, 4));
fs.writeFileSync(root + "/bids/" + datasetName + "/.bidsignore", `
**/excluded
**/*_MP2RAGE.*
finalized.json
`);
info.readme += `
## ezbids

This dataset was converted from DICOM to BIDS using ezBIDS (https://brainlife.io/ezbids)

`;
fs.writeFileSync(root + "/bids/" + datasetName + "/README", info.readme);
fs.writeFileSync(root + "/bids/" + datasetName + "/participants.json", JSON.stringify(info.participantsColumn, null, 4));
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
    tsvrec.push("sub-" + subject.subject);
    for (let key in info.participantsColumn) {
        tsvrec.push(subject.phenotype[key]);
    }
    tsv.push(tsvrec);
});
let tsvf = fs.openSync(root + "/bids/" + datasetName + "/participants.tsv", "w");
for (let rec of tsv) {
    fs.writeSync(tsvf, rec.join("\t") + "\n");
}
fs.closeSync(tsvf);
//handle each objects
console.log("outputting objects");
async.forEach(info.objects, (o, next_o) => {
    /*
    if(o._exclude) {
        o._type = "excluded/obj"+o.idx;
        o._entities.description = o._SeriesDescription; //inject seriesdesc to filename
    }
    */
    let typeTokens = o._type.split("/");
    let modality = typeTokens[0]; //func, dwi, anat, etc.. (or exclude)
    let suffix = typeTokens[1]; //t1w, bold, or "objN" for exclude)
    //construct basename
    let tokens = [];
    //for(let k in o._entities) {
    for (let k in info.entityMappings) {
        const sk = info.entityMappings[k];
        if (o._entities[k]) {
            tokens.push(sk + "-" + o._entities[k]);
        }
    }
    if (o._exclude) {
        //excluded object doesn't have to be validated, so some of the item might collide..
        //let's prevent it by setting some artificial tag
        tokens.push("ezbids-" + o.idx);
    }
    const name = tokens.join("_");
    function composePath(derivatives) {
        let path = "bids/" + datasetName;
        if (derivatives)
            path += "/derivatives/" + derivatives;
        path += "/sub-" + o._entities.subject;
        if (o._entities.session)
            path += "/ses-" + o._entities.session;
        if (o._exclude) {
            path += "/excluded";
        }
        else {
            path += "/" + modality;
        }
        return path;
    }
    function handleItem(item, filename, derivatives = null) {
        const path = composePath(derivatives);
        mkdirp.sync(root + "/" + path);
        //setup directory
        let fullpath = root + "/" + path + "/" + name + "_" + filename;
        if (item.name == "json") {
            //we create sidecar from sidecar object (edited by the user)
            item.content = JSON.stringify(item.sidecar, null, 4);
        }
        if (item.content) {
            //if item has content to write, then use it instead of normal file
            fs.writeFileSync(fullpath, item.content);
        }
        else {
            //otherwise, assume to be normal files (link from the source)
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
            fs.linkSync(root + "/" + item.path, fullpath);
        }
    }
    function handleAnat() {
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
        //find manufacturer (used by UNIT1 derivatives)
        let manufacturer = "UnknownManufacturer";
        o.items.forEach(item => {
            if (item.sidecar && item.sidecar.Manufacturer)
                manufacturer = item.sidecar.Manufacturer;
        });
        o.items.forEach(item => {
            let derivatives = null;
            if (suffix == "UNIT1")
                derivatives = manufacturer;
            switch (item.name) {
                case "nii.gz":
                    if (o.defaced && o.defaceSelection == "defaced") {
                        item.path = item.path + ".defaced.nii.gz";
                        console.log("using defaced version of t1w", item.path);
                    }
                    handleItem(item, suffix + ".nii.gz", derivatives);
                    break;
                case "json":
                    handleItem(item, suffix + ".json", derivatives);
                    break;
                default:
                    console.error("unknown anat item name", item.name);
            }
        });
    }
    function handleFunc() {
        /*
        - suffixes:
            - bold
            - cbv
            - phase
            - sbref

        */
        if (suffix == "events") {
            //we handle events a bit differently.. we need to generate events.tsv from items content
            const tsv = o.items.find(o => o.name == "tsv");
            const sidecar = o.items.find(o => o.name == "json");
            console.log("handling events");
            console.log("tsv");
            console.dir(tsv);
            console.log("sidecar");
            console.dir(sidecar);
            console.log("info.events");
            console.dir(info.events);
            const columns = info.events.columns;
            //compose headers
            const headers = [];
            if (columns.onset)
                headers.push("onset");
            if (columns.duration)
                headers.push("duration");
            if (columns.sample)
                headers.push("sample");
            if (columns.trialType)
                headers.push("trial_type");
            if (columns.responseTime)
                headers.push("response_time");
            if (columns.value)
                headers.push("value"); //??
            if (columns.HED)
                headers.push("HED");
            tsv.content = headers.join("\t") + "\n";
            function fixUnit(v, unit) {
                if (unit == "mm")
                    return v / 100; //convert to cm
                return v; //assume cm..
            }
            //emit all values
            tsv.events.forEach(event => {
                const values = [];
                if (columns.onset)
                    values.push(fixUnit(event[columns.onset], columns.onsetUnit));
                if (columns.duration)
                    values.push(fixUnit(event[columns.duration], columns.durationUnit));
                if (columns.sample)
                    values.push(event[columns.sample]);
                if (columns.trialType)
                    values.push(event[columns.trialType]);
                if (columns.responseTime)
                    values.push(fixUnit(event[columns.responseTime], columns.responseTimeUnit));
                if (columns.value)
                    values.push(event[columns.value]);
                if (columns.HED)
                    values.push(event[columns.HED]);
                tsv.content += values.join("\t") + "\n";
            });
            console.log(tsv.content);
            //add stuff to sidecar
            //sidecar.sidecar.TaskName = o._entities.task;
            sidecar.sidecar.trial_type = {
                LongName: info.events.trialTypes.longName,
                Description: info.events.trialTypes.desc,
                Levels: info.events.trialTypes.levels,
            };
            //now save
            handleItem(tsv, "events.tsv");
            handleItem(sidecar, "events.json");
        }
        else {
            //normal func stuff..
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
        }
    }
    function handleFmap() {
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
                            //this should not happen, but ezBIDS.json could be corrupted..
                            if (!io) {
                                console.error("can't find object with ", idx);
                                continue;
                            }
                            //if intended object is excluded, skip it
                            if (io._type == "exclude")
                                continue;
                            //doesn't make sense to intentend for its own object (I don't think this ever happens)
                            //if(io == o) continue;
                            console.log("intended for", io._type);
                            const iomodality = io._type.split("/")[0];
                            const suffix = io._type.split("/")[1];
                            //construct a path relative to the subject
                            let path = "";
                            if (io._entities.session)
                                path += "ses-" + io._entities.session + "/";
                            path += iomodality + "/";
                            let tokens = [];
                            //for(let k in io._entities) {
                            for (let k in info.entityMappings) {
                                const sk = info.entityMappings[k];
                                if (io._entities[k])
                                    tokens.push(sk + "-" + io._entities[k]);
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
    }
    function handleDwi() {
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
        if (!o.items.find(item => item.name == "bvec")) {
            console.log("bvec is missing.. assuming that this is b0, and setup empty bvec/bval");
            const path = composePath(false);
            const zeros = [];
            for (let j = 0; j < o.analysisResults.NumVolumes; ++j) {
                zeros.push(0);
            }
            const bvec = `${zeros.join(" ")}\n${zeros.join(" ")}\n${zeros.join(" ")}\n`;
            fs.writeFileSync(root + "/" + path + "/" + name + "_dwi.bvec", bvec);
            const bval = zeros.join(" ") + "\n";
            fs.writeFileSync(root + "/" + path + "/" + name + "_dwi.bval", bval);
        }
    }
    //now handle different modality
    switch (modality) {
        case "anat":
            handleAnat();
            break;
        case "func":
            handleFunc();
            break;
        case "fmap":
            handleFmap();
            break;
        case "dwi":
            handleDwi();
            break;
        /*
        case "excluded":
            o.items.forEach((item, idx)=>{
                //sub-OpenSciJan22_desc-localizer_obj5-0.json
                //TODO - whty do I need to add idx?
                handleItem(item, suffix+"-"+idx+"."+item.name);
            });
            break;
        */
        default:
            console.error("unknown datatype:" + o._type);
    }
    next_o();
});
//# sourceMappingURL=convert.js.map