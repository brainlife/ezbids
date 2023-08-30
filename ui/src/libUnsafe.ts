// @ts-nocheck

import { objectToString } from "@vue/shared";
import { isPlainObject } from "vue/node_modules/@vue/shared";

//deepEqual and isPrimitive functions come from https://stackoverflow.com/a/45683145
export function deepEqual(obj1, obj2) {
    //Determines if two arrays are equal or not. Better then JSON.stringify
    //because this accounts for different ordering; only cares about whether
    //keys and values match.

    if(obj1 === obj2) // it's just the same object. No need to compare.
        return true;

    if(isPrimitive(obj1) && isPrimitive(obj2)) // compare primitives
        return obj1 === obj2;

    if(Object.keys(obj1).length !== Object.keys(obj2).length)
        return false;

    // compare objects with same number of keys
    for(let key in obj1)
    {
        if(!(key in obj2)) return false; //other object doesn't have this prop
        if(!deepEqual(obj1[key], obj2[key])) return false;
    }

    return true;
}

export function isPrimitive(obj) {
    return (obj !== Object(obj));
}

export function setVolumeThreshold($root) {
    /*
    Determine volume threshold for all func/bold acquisitions in dataset and set
    to exclude if the number of volumes does not meet the volume threshold. Threshold 
    calculated based on the expected number of volumes collected in a 1-minute time frame,
    with the formula (60-sec / tr), where tr == RepetitionTime
    */
    $root.objects.forEach(o=> {

        //update analysisResults.warnings in case user went back to Series and adjusted things
        if(o._type == "func/bold") {
            let tr = o.items[0].sidecar.RepetitionTime
            let numVolumes = o.analysisResults.NumVolumes
            let numVolumes1min = Math.floor(60 / tr)
            // let numVolumes1min = 5
            if(numVolumes <= numVolumes1min) {
                o.exclude = true
                o.analysisResults.warnings = [`This func/bold sequence contains ${numVolumes} volumes, which is \
                less than the threshold value of ${numVolumes1min} volumes, calculated by the expected number of \
                volumes in a 1 min time frame. This acquisition will thus be excluded from BIDS conversion unless \
                unexcluded. Please modify if incorrect.`]
            }
        }
    });
}


export function setSectionIDs($root) {
    /*
    Set section_id value for each acquisition, beginning with value of 1. A section is
    ezBIDS jargin for each time participant comes out and then re-enters scanner. Each time
    a non-adjacent localizer is detected, the section_id value is increased by 1. The
    section_id value helps for determining fmap IntendedFor mapping, where field maps
    cannot be applied to acquisitions from different sections.
    */

    $root._organized.forEach(subGroup=>{
        subGroup.sess.forEach(sesGroup=>{
            let protocol = sesGroup.objects
            let sectionID = 1
            let obj_idx = 0
            let message = ""
            let previousMessage = ""
            protocol.forEach(obj=> {
                if($root.series[protocol[obj_idx].series_idx]) {
                    message = $root.series[protocol[obj_idx].series_idx].message
                }

                if(obj_idx != 0 && $root.series[protocol[obj_idx - 1].series_idx]) {
                    previousMessage = $root.series[protocol[obj_idx - 1].series_idx].message
                }

                if(obj_idx != 0 && message.includes("localizer") && (previousMessage == "" || !previousMessage.includes("localizer"))) {
                    sectionID++;
                    obj.analysisResults.section_id = sectionID
                }else{
                    obj.analysisResults.section_id = sectionID
                }
                obj_idx++
            })
        });
    });
}

export function funcQA($root) {
    /*
    1). If func/bold acquisition is excluded, warn users that corresponding
    func/sbref, and func/bold (part-phase) should all excluded as well,
    if they exist.

    2). Warn users about func/sbref if its PhaseEncodingDirection (PED) is different
    from the corresponding func/bold PED.
    */
    $root.objects.forEach(o=> {
        // #1

        //update analysisResults.warnings in case user went back to Series and adjusted things
        if(o._type == "func/bold" && o.exclude == false && (!o._entities.mag || o._entities.mag == "mag")) {
            let funcBoldEntities = o._entities
            let goodFuncSBRef = $root.objects.filter(e=>e._type == "func/sbref" && deepEqual(e._entities, funcBoldEntities))
            let goodFuncBoldPhase = $root.objects.filter(e=>e._type == "func/bold" && e._entities.mag == "phase" && deepEqual(Object.keys(e._entities).filter(e=>e != "part"), funcBoldEntities))

            for(const good of [goodFuncSBRef, goodFuncBoldPhase]) {
                good.forEach(g=>{
                    g.analysisResults.warnings = []
                })
            }
        }

        //now check for corresponding func/bold == exclude, and go from there
        if(o._type == "func/bold" && o.exclude == true && (!o._entities.mag || o._entities.mag == "mag" || o._entities.mag == "part")) {
            let funcBoldEntities = o._entities
            let badFuncSBRef = $root.objects.filter(e=>e._type == "func/sbref" && deepEqual(e._entities, funcBoldEntities))
            let badFuncBoldPhase = $root.objects.filter(e=>e._type == "func/bold" && e._entities.mag == "phase" && deepEqual(Object.keys(e._entities).filter(e=>e != "part"), funcBoldEntities))

            for(const bad of [badFuncSBRef, badFuncBoldPhase]) {
                bad.forEach(b=>{
                    b.exclude = true
                    b.analysisResults.warnings = [`The corresponding func/bold (#${o.series_idx}) to this acquisition \
                    has been set to exclude from BIDS conversion. Since this func/sbref is linked, it will also be \
                    excluded from conversion. Please modify if incorrect.`]
                })
            }
        }

        // #2
        if(o._type == "func/bold" && o.exclude == false && (!o._entities.mag || o._entities.mag == "mag")) {
            let boldEntities = o._entities
            let boldPED = o.items[0].sidecar.PhaseEncodingDirection
            let badSBRef = $root.objects.filter(e=>e._type == "func/sbref" && deepEqual(e._entities, boldEntities) &&
                                                e.items[0].sidecar.PhaseEncodingDirection != boldPED).map(e=>e.idx)
            badSBRef.forEach(bad=> {
                // $root.objects[bad].exclude = true
                $root.objects[bad].analysisResults.warnings = [`Functional sbref has a different PhaseEncodingDirection than its corresponding functional bold (#${o.series_idx}). This is likely a data error, therefore this sbref should be excluded from BIDS conversion.`]
            })
        }

        // // #3
        // if(o._type == "func/bold" && o.exclude == false) {
        //     let boldOrientations = $root.objects.map(o=>o.analysisResults.orientation)

        // }

    })
}

export function fmapQA($root) {
    /* Generate warning(s) duplicate field maps (or not enough) are detected.

    TODO: generate warning(s) if Pepolar field maps don't have opposite phase encoding directions
    */

    $root._organized.forEach(subGroup=>{
        subGroup.sess.forEach(sesGroup=>{

            // Determine unique sectionIDs
            let allSectionIDs = sesGroup.objects.map(e=>e.analysisResults.section_id)
            let sectionIDs = Array.from(new Set(allSectionIDs))

            // Loop through sections
            sectionIDs.forEach(s=> {
                let section = sesGroup.objects.filter(o=>o.analysisResults.section_id == s && !o._exclude && o._type != "exclude")

                // https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#types-of-fieldmaps

                // case #1: Phase-difference map and at least one magnitude image
                let fmapMagPhasediffObjs = section.filter(function (o) {
                    return o._type == "fmap/magnitude1" ||
                    o._type == "fmap/magnitude2" ||
                    o._type == "fmap/phasediff"
                });

                let fmapMagPhasediffCheck = fmapMagPhasediffObjs.filter(o=>o._type == "fmap/phasediff") //since cases 1 & 2 can have "fmap/magnitude1", check for "fmap/phasediff to determine case 1"
                if(!fmapMagPhasediffCheck.length) {
                    fmapMagPhasediffObjs = []
                }


                // case #2: Two phase maps and two magnitude maps
                let fmapMagPhaseObjs = section.filter(function (o) {
                    return o._type == "fmap/magnitude1" ||
                    o._type == "fmap/magnitude2" ||
                    o._type == "fmap/phase1" ||
                    o._type == "fmap/phase2"
                });

                let fmapMagPhaseCheck = fmapMagPhaseObjs.filter(o=>o._type == "fmap/phase1") //since cases 1 & 2 can have "fmap/magnitude1", check for "fmap/phase1 to determine case 2"
                if(!fmapMagPhaseCheck.length) {
                    fmapMagPhaseObjs = []
                }


                // case #3: Direct field mapping
                let fmapDirectObjs = section.filter(function (o) {
                    return o._type == "fmap/magnitude" ||
                    o._type == "fmap/fieldmap"
                })


                //case #4: Multiple phase encoding direction ("pepolar")
                let fmapPepolar = section.filter(o=>o._type == "fmap/epi")

                /*
                In addition to the fmap cases listed above, other field maps exist.
                For list of these [quantitative MRI] field maps, see
                https://github.com/bids-standard/bids-specification/blob/master/src/schema/rules/datatypes/fmap.yaml and
                https://bids-specification.readthedocs.io/en/stable/99-appendices/11-qmri.html
                */

                let fmapM0scan = section.filter(o=>o._type == "fmap/m0scan") //pair
                let fmapTB1DAM = section.filter(o=>o._type == "fmap/TB1DAM") //pair
                let fmapTB1EPI = section.filter(o=>o._type == "fmap/TB1EPI") //pair
                let fmapTB1AFI = section.filter(o=>o._type == "fmap/TB1AFI") //pair
                let fmapTB1TFL = section.filter(o=>o._type == "fmap/TB1TFL") //pair
                let fmapTB1RFM = section.filter(o=>o._type == "fmap/TB1RFM") //pair
                let fmapRB1COR = section.filter(o=>o._type == "fmap/RB1COR") //pair
                let fmapTB1SRGE = section.filter(o=>o._type == "fmap/TB1SRGE") //pair
                let fmapTB1map = section.filter(o=>o._type == "fmap/TB1map") //single
                let fmapRB1map = section.filter(o=>o._type == "fmap/RB1map") //single


                /* Check for duplicate fmaps (or not enough fmaps). If so, generate validation
                warning for the duplicate(s) or missing field maps. ezBIDS assumes that the duplicates
                are the first fmap [sets], and then the last fmap(s) in the section are what user want.
                If not, they can ignore the warning(s) or make modifications as they see fit.
                */

                if(fmapMagPhasediffObjs.length) {
                    // for case #1, there can be a pair (magnitude1, phasediff) or a triplet (magnitude1, magnitude2, phasediff)
                    if(fmapMagPhasediffObjs.length == 1) {
                        fmapMagPhasediffObjs.forEach(o=>{
                            o.analysisResults.warnings.push("There doesn't appear to be a full field map pair (magnitude1, phasediff) or triplet (magnitude1, magnitude2, phasediff). It is highly recommended that this acquistion be excluded from BIDS conversion, as it doesn't form a complete pair/triplet.")
                        })
                    }
                    if(fmapMagPhasediffObjs.length > 3) {
                        fmapMagPhasediffObjs.forEach(o=>{
                            o.analysisResults.warnings.push("There appear to be too many field maps of this kind, the max allowed for this kind of field map is a triplet (magnitude1, magnitude2, phasediff). There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.")
                        })
                    }
                }

                if(fmapMagPhaseObjs.length) {
                    // for case #2, there must be a set of 4 (phase1, phase2, magnitude1, magnitude2)
                    if(fmapMagPhaseObjs.length < 4) {
                        fmapMagPhaseObjs.forEach(o=>{
                            o.analysisResults.warnings.push("There doesn't appear to be a full field map set (phase1, phase2, magnitude1, magnitude2) for this kind of field maps. It is highly recommended that this fmap acquisition be excluded from BIDS conversion, as it is incomplete (i.e. doesn't form complete set of 4).")
                        })
                    }
                    if(fmapMagPhaseObjs.length > 4) {
                        fmapMagPhaseObjs.forEach(o=>{
                            o.analysisResults.warnings.push("There appear to be too many field maps of this kind, only a set (phase1, phase2, magnitude1, magnitude2) is allowed for this kind of field map. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.")
                        })
                    }
                }

                if(fmapDirectObjs.length) {
                    // for case #3, there must be a pair (magnitude, fieldmap)
                    if(fmapDirectObjs.length < 2) {
                        fmapDirectObjs.forEach(o=>{
                            o.analysisResults.warnings.push("There doesn't appear to be a field map pair (magnitude, fieldmap) for this kind of field map. It is highly recommended that this fmap acquisition be excluded from BIDS conversion, as it is incomplete (i.e. doesn't form pair).")
                        })
                    }
                    if(fmapDirectObjs.length > 2) {
                        fmapDirectObjs.forEach(o=>{
                            o.analysisResults.warnings.push("There appear to be too many field maps of this kind, only a pair (magnitude, fieldmap) is allowed for this kind of field map. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.")
                        })
                    }
                }

                if(fmapDirectObjs.length) {
                    // for case #4, there must be a pair (epi, epi)
                    if(fmapPepolar.length < 2) {
                        fmapPepolar.forEach(o=>{
                            o.analysisResults.warnings.push("There doesn't appear to be a pair for this kind of field map. It is highly recommended that this fmap acquisition be excluded from BIDS conversion, as it is incomplete (i.e. doesn't form pair).")
                        })
                    }
                    if(fmapPepolar.length > 2) {
                        fmapPepolar.forEach(o=>{
                            o.analysisResults.warnings.push("There appear to be too many field maps of this kind, only a pair is allowed for this kind of field map. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.")
                        })
                    }
                }

                // several of the quantitative MRI field maps come in pairs, so validate them the same way
                for(const fmap of [fmapM0scan, fmapTB1EPI, fmapTB1AFI, fmapTB1TFL, fmapTB1RFM, fmapRB1COR, fmapTB1SRGE, fmapTB1DAM]) {
                    if(fmap.length) {
                        if(fmap.length < 2) {
                            fmap.forEach(o=>{
                                o.analysisResults.warnings.push("There doesn't appear to be a pair for this kind of field map. It is highly recommended that this fmap acquisition be excluded from BIDS conversion, as it is incomplete (i.e. doesn't form pair).")
                            })
                        }
                        if(fmap.length > 2) {
                            fmap.forEach(o=>{
                                o.analysisResults.warnings.push("There appear to be too many field maps of this kind, only a pair is allowed for this kind of field map. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.")
                            })
                        }
                    }
                }
                // some of the quantitative MRI field maps come as a single acquisition, so validate them the same way
                for(const fmap of [fmapTB1map, fmapRB1map]) {
                    if(fmap.length) {
                        if(fmap.length > 1) {
                            fmap.forEach(o=>{
                                o.analysisResults.warnings.push("There appear to be too many field maps of this kind, only a single acquisition for this kind of field map is allowed. There may be duplicates, in which case the duplicate(s) should be excluded from BIDS conversion.")
                            })
                        }
                    }
                }
            });
        });
    });
}


export function setRun($root) {
    // Set run entity label if not already specified at Series level

    // Loop through subjects

    $root._organized.forEach(subGroup=>{

        // Loop through sessions
        subGroup.sess.forEach(sesGroup=>{
            // Determine series_idx values
            let allSeriesIndices = sesGroup.objects.map(e=>e.series_idx)
            let uniqueSeriesIndices = Array.from(new Set(allSeriesIndices))

            uniqueSeriesIndices.forEach(si=>{
                let seriesObjects = sesGroup.objects.filter(e=>e.series_idx == si && !e._exclude)
                let run = 1
                if(seriesObjects.length > 1) {
                    seriesObjects.forEach(obj=>{
                        obj.entities.run = run.toString()
                        run++
                    });
                }
            });
        });
    });
}


export function setIntendedFor($root) {
    // Apply fmap intendedFor mapping, based on user specifications on Series page.

    // Loop through subjects
    $root._organized.forEach(subGroup=>{

        subGroup.sess.forEach(sesGroup=>{

            // Determine unique sectionIDs
            let allSectionIDs = sesGroup.objects.map(e=>e.analysisResults.section_id)
            let sectionIDs = Array.from(new Set(allSectionIDs))

            // Loop through sections
            sectionIDs.forEach(s=> {
                let section = sesGroup.objects.filter(e=>e.analysisResults.section_id == s && !e._exclude && e._type != "exclude")

                section.forEach(obj=>{
                    //add IntendedFor information
                    if(obj._type.startsWith("fmap/")) {
                        Object.assign(obj, {IntendedFor: []})
                        let correspindingSeriesIntendedFor = $root.series[obj.series_idx].IntendedFor
                        correspindingSeriesIntendedFor.forEach(i=>{
                            let IntendedForIDs = section.filter(o=>o.series_idx == i && o._type != "func/events").map(o=>o.idx)
                            obj.IntendedFor = obj.IntendedFor.concat(IntendedForIDs)
                        });
                    }

                    // check B0FieldIdentifier and B0FieldSource information
                    if(obj._type && !obj._type.includes('exclude') && !obj._type.includes('events')) {
                        Object.assign(obj, {B0FieldIdentifier: []})
                        Object.assign(obj, {B0FieldSource: []})
                                                
                        if("B0FieldIdentifier" in $root.series[obj.series_idx]) {
                            let correspindingSeriesB0FieldIdentifier = $root.series[obj.series_idx].B0FieldIdentifier
                            for(const k in correspindingSeriesB0FieldIdentifier) {
                                const v = correspindingSeriesB0FieldIdentifier[k]
                                obj.B0FieldIdentifier.push(v)
                            }
                        }

                        if("B0FieldSource" in $root.series[obj.series_idx]) {
                            let correspindingSeriesB0FieldSource = $root.series[obj.series_idx].B0FieldSource
                            for(const k in correspindingSeriesB0FieldSource) {
                                const v = correspindingSeriesB0FieldSource[k]
                                obj.B0FieldSource.push(v)
                            }
                        }
                    }
                });
            });
        });
    });
}

function findMostCommonValue(arr){
    /* Function comes from https://stackoverflow.com/a/20762713

    This function acts as a mode (i.e. finds the most common value
    in an array).
    */

    return arr.sort((a,b) =>
          arr.filter(v => v===a).length
        - arr.filter(v => v===b).length
    ).pop();
}

export function validate_Entities_B0FieldIdentifier_B0FieldSource(entities, B0FieldIdentifier, B0FieldSource/*: Series*/) {     
    const errors = [];                                                                                      
    //validate entity (only alpha numeric values)                                                               
    for(const k in entities) {
        const v = entities[k];                                                                                
        if(v && !/^[a-zA-Z0-9]*$/.test(v)) {                                                                    
            errors.push("Entity label "+k+" contains non-alphanumeric character");                        
        }                                                                                                       
    }
    
    //validate B0FieldIdentifier (only alpha numeric values and dash [-] and underscore [_])
    for(const k in B0FieldIdentifier) {
        const v = B0FieldIdentifier[k];                                                                                
        if(v && !/^[a-zA-Z0-9-_]*$/.test(v)) {                                                                    
            errors.push("B0FieldIdentifier (#"+k+"-indexed selection) contains non-alphanumeric character(s). \
            The (dash [-] and underscore [_] characters are acceptable)");                        
        }                                                                                                       
    }

    //validate B0FieldSource (only alpha numeric values and dash [-] and underscore [_])
    for(const k in B0FieldSource) {
        const v = B0FieldSource[k];                                                                                
        if(v && !/^[a-zA-Z0-9-_]*$/.test(v)) {                                                                    
            errors.push("B0FieldSource (#"+k+"-indexed selection) contains non-alphanumeric character(s). \
            The (dash [-] and underscore [_] characters are acceptable)");                        
        }                                                                                                       
    }
    return errors;                                                                                          
}

export function dwiQA($root) {
    /*
    DWI acquisitions are typically acquired in two ways:

    1). Flipped PED pairs.
    2). One or more DWI acquisitions with one PED and a corresponding b0/fieldmap with opposite PED.

    This QA checks to see if one of these two conditions is met; if not, a validation warning is
    generated to alert user.
    */
    $root._organized.forEach(subGroup=>{
        subGroup.sess.forEach(sesGroup=>{
            let dwiInfo = []
            let fmapInfo = []
            let protocolObjects = sesGroup.objects

            for(const protocol of protocolObjects) {
                Object.keys(protocol).forEach(key=>{
                    if(key == "_type" && protocol[key] == "dwi/dwi") {
                        dwiInfo.push({"series_idx": protocol.series_idx, "idx": protocol.idx, "direction": protocol.PED, "fmap": "N/A", "oppDWI": "N/A"})
                    }

                    if(key == "_type" && protocol[key].startsWith("fmap/")) { //check for field map(s) that might be applied to DWI acquisitions
                        fmapInfo.push({"IntendedFor": $root.series.filter(e=>e.series_idx == protocol.series_idx)[0].IntendedFor})
                    }
                })
            }

            if(dwiInfo.length) {

                let dwiDirs = dwiInfo.map(e=>e.direction)

                if(fmapInfo.length) {
                    fmapInfo.forEach(f=>{
                        dwiInfo.forEach(d=>{
                            if(f.IntendedFor.includes(d.series_idx)) {
                                d.fmap = "yes"
                            }
                            if(dwiDirs.includes(d.direction.split("").reverse().join(""))) {
                                d.oppDWI = "yes"
                            }
                        })
                    })
                }else{
                    dwiInfo.forEach(d=>{
                        if(dwiDirs.includes(d.direction.split("").reverse().join(""))) {
                            d.oppDWI = "yes"
                        }
                    })
                }

                dwiInfo.forEach(d=>{
                    if(d.fmap != "yes" && d.oppDWI != "yes") {
                        let corrProtocolObj = protocolObjects.filter(e=>e.idx == d.idx)[0] //will always be an index of 1, so just grab the first (i.e. only) index
                        corrProtocolObj.analysisResults.warnings.push("This dwi/dwi acquisition doesn't appear to have a corresponding dwi/dwi or field map acquisition with a 180 degree flipped phase encoding direction. You may wish to exclude this from BIDS conversion, unless there is a reason for keeping it.")
                    }
                })
            }
        })
    })
}

export function find_separator(filePath, fileData) {
    if(filePath.indexOf(".tsv") > -1) {
        return /[ \t]+/;
    }else if(filePath.indexOf(".out") > -1 || filePath.indexOf(".csv") > -1)  {
        return /[ ,]+/;
    }else if(filePath.indexOf(".txt") > -1) {
        const data = fileData
        const lines = data.trim().split("\n").map(l=>l.trim());
        if(lines[0].indexOf(',') > -1) {
            return /[ ,]+/;
        }else{
            return /[ \t]+/;
        }
    }else if(filePath.indexOf(".xlsx") > -1) {
        return /[ ,]+/;
    }else{
        console.log("ignoring", filePath);
    }

    throw "unknown file extension";
}

function parseEprimeEvents(fileData, cb) {
    const lines = fileData.trim().split(/\r|\n/).map(l=>l.trim());

    //parse each line
    const trials = [];
    let headers = null;
    let block = {};
    const timing_info = []
    lines.forEach(line=>{
        switch(line) {
        case "*** Header Start ***":
            block = {};
            break;
        case "*** Header End ***":
            headers = block;
            break;
        case "*** LogFrame Start ***":
            block = {};
            break;
        case "*** LogFrame End ***":
            trials.push(block);
            break;
        default:
            const kv = line.split(": ");
            const k = kv[0].toLowerCase();
            const v = kv[1];
            block[k] = v;
        }
        trials.push(block);
    });
    timing_info.push(trials)

    return timing_info[0]
}

export function parseEvents(fileData, sep) {
    const lines = fileData.trim().split(/\r|\n/).map(l=>l.trim().replace(/['"]+/g, ''));
    const trials = [];
    let headers = lines.shift().split(sep);
    const timing_info = []

    lines.forEach(line=>{
        const tokens = line.split(sep);
        if(tokens.length > 1) { //need at least two columns for onset and duration
            if(tokens.filter(t=>t.replace(/[^0-9a-z]/gi, '')).length) { //filter out lines consisting of only non-alphanumeric characters
                const block = {};
                for(let i = 0;i < tokens.length; ++i) {
                    try {
                        const k = headers[i].toLowerCase();
                        const v = tokens[i];
                        block[k] = v;
                    } catch(err) {
                        const k = headers[i]
                        const v = tokens[i]
                        block[k] = v;
                    }
                }
                trials.push(block);
            }
        }
    });
    timing_info.push(trials)

    return timing_info[0]
}

function parseExcelEvents(fileData) {
    // Code from https://stackoverflow.com/questions/30859901/parse-xlsx-with-node-and-create-json
    let workbook = fileData;
    let sheet_name_list = workbook.SheetNames;
    let trials = []
    sheet_name_list.forEach(function(y) {
        let worksheet = workbook.Sheets[y];
        let headers = {};
        let data = [];
        for(z in worksheet) {
            if(z[0] === '!') continue;
            //parse out the column, row, and value
            let col = z.substring(0,1);
            let row = parseInt(z.substring(1));
            let value = worksheet[z].v;

            //store header names
            if(row == 1) {
                headers[col] = value.toLowerCase();
                continue;
            }

            if(!data[row]) data[row]={};
            data[row][headers[col]] = value;
        }
        //drop those first two rows which are empty
        data.shift();
        data.shift();
        trials.push(data)
    });

    return trials[0];
}

export function createEventObjects(ezbids, files) {
    /*
    This function receives files, an array of object containing fullpath and data.
    Data is the actual file content of the file,
    */
    const eventObjects = []; //new event objects to add

    // Identify some terms for decoding purposes
    const subjects = Array.from(new Set(ezbids.subjects.filter(e=>e.exclude == false).map(e=>e.subject)))
    const sessionsArray = Array.from(new Set(ezbids.subjects.map(e=>e.sessions)[0].filter(e=>e.exclude == false).map(e=>e.session)))
    const sessions = sessionsArray.filter(function(e){return e}) // remove empty strings & spaces (i.e. no session(s) present
    const tasks = Array.from(new Set(ezbids.objects.map(e=>e._entities).filter(e=>(e.part == "" || e.part == "mag") && (e.task != "" && e.task != "rest" && e.task !== undefined)).map(e=>e.task)))
    const runs = Array.from(new Set(ezbids.objects.filter(e=>e._entities.task != "" && e._entities.task != "rest" && e._entities.task != undefined).map(e=>e._entities.run)))
    const numEventFiles = files.length

    // Try to determine inheritance level (dataset, subject, session, or individual runs)
    const occurrences = {"Dataset": 1, "Subject": subjects.length, "Session": sessions.length, "Run": runs.length}
    const closest = Object.values(occurrences).reduce(function(prev, curr) {
        return Math.abs(curr - numEventFiles) < Math.abs(prev - numEventFiles) ? curr : prev
    });

    /*
    Chance that multiple occurrences values could be the same, therefore, default to lowest level.
    Assumption is that the lower the level, the more common it is.
    */
    // const inheritance_level = Object.keys(occurrences).filter(key=>occurrences[key] == closest).slice(-1)[0]

    //set random entity values that can be updated later on if events mapping doesn't work properly
    let randSubID = 1
    let randSesID = 1
    let randTaskName = "unknown"
    let randRunID = 1

    // Sort through events file(s) list
    files.forEach(file=>{
        const fileExt = file.path.split(".").pop();

        // Parse the data, depending on the file extension (and header information)
        let events;
        switch(fileExt) {
        // Excel workbook formats (.xlsx, .xlsm, .xls)
        case "xlsx":
            events = parseExcelEvents(file.data)
            break;
        default: // Non-Excel formats
            const data = file.data
            const lines = data.trim().split("\n").map(l=>l.trim());
            if(lines[0].indexOf('Header Start') > -1) {
                // E-prime file format
                events = parseEprimeEvents(file.data)
            }else{
                // "Regular" file format (.csv .tsv .txt .out)
                const sep = find_separator(file.path, file.data) // Read events file(s) data
                events = parseEvents(file.data, sep);
            }
        }

        // Array to help map ezBIDS information to events timing files
        const eventsMappingInfo = {
            subject: {
                MappingKeys: [
                    "sub", "subid", "subname",
                    "subj", "subjid", "subjname",
                    "subject", "subjectid", "subjectname",
                    "participant", "participantid", "participantname"
                ],
                ezBIDSvalues: subjects,
                eventsValue: undefined,
                detectionMethod: undefined,
            },
            session: {
                MappingKeys: [
                    "ses", "sesid", "sesname",
                    "sess", "sessid", "sessname",
                    "session", "sessionid", "sessionname"
                ],
                ezBIDSvalues: sessions,
                eventsValue: undefined,
                detectionMethod: undefined,
            },
            task: {
                MappingKeys: [
                    "exp", "expid", "expname",
                    "task", "taskid", "taskname",
                    "experiment", "experimentid", "experimentname"
                ],
                ezBIDSvalues: tasks,
                eventsValue: undefined,
                detectionMethod: undefined,
            },
            run: {
                MappingKeys: ["run", "runid", "runname"],
                ezBIDSvalues: runs,
                eventsValue: undefined,
                detectionMethod: undefined,
            }
        }

        const sepChars = [".", "-", "_", "/"] //used for parsing file path for identifying information, if we need to use file path
        const colNames = Object.keys(events[0]); //selecting the first column of the events timing file, which contains the column names
        for(const entity in eventsMappingInfo) {
            const info = eventsMappingInfo[entity];

            /* 1st stage: examine column names and data of event file(s) to
            see if identifying information (sub, ses, task, and/or run) is contained there.
            */
           let identifyingCol = undefined

           for(const colName of colNames) {
               const safeCol = colName.toLowerCase().replace(/[^0-9a-z]/gi, ''); //make lowercase and remove non-alphanumeric characters
               if(info.MappingKeys.includes(safeCol)) {
                   identifyingCol = safeCol
                   break;
               }
           }
            if(identifyingCol) {
                const identifyingColValues = events.map(e=>e[identifyingCol]);
                info.eventsValue = findMostCommonValue(identifyingColValues); //columns may contain multiple values, so find the most common value
                info.detectionMethod = "identifying information found from value in identifying column name";
            }

            //2nd stage: examine file path for identifying information
            if(info.eventsValue === undefined) {
                const lowerCaseFilePath = file.path.toLowerCase()
                Object.values(info.MappingKeys).forEach(mappingKey=>{
                    const splitFilePath = lowerCaseFilePath.split(mappingKey)
                    if(splitFilePath.length > 1) { //if a mappingKey is in the file path, the length of the splitFilePath array will be > 1
                        let lastSplit = splitFilePath.slice(-1)[0] //splitFilePath.slice(-1) is an array of length 1, so grab the first (i.e. entire) array
                        const lastSplitFirstChar = lastSplit[0]

                        Object.values(sepChars).forEach(sepChar=>{ //remove leading separator character(s), if they exist
                            if(sepChar == lastSplitFirstChar) {
                                lastSplit = lastSplit.substring(1).replace(sepChar, "")
                            }
                        });
                        lastSplit = lastSplit.replace("/", "-")

                        let value = lastSplit.split(/[._-]+/)[0]
                        let regex = new RegExp(value, "gi")
                        info.eventsValue = file.path.match(regex)[0] //since we used a case-insensitive search, let eventsValue be the case-sensitive value from the file path
                        info.detectionMethod = "identifying information found in file path";
                    }
                });
            }

            /* 3rd stage: ignore zero-padding in subject, session, and run eventsValue if the zero-padded
            value doesn't exist in corresponding ezBIDSvalues. For example, if subject ID in ezBIDS
            is "1", but the corresponding events subject ID is "01", simply assume the two are the same.
            */
            if(entity != "task" && info.eventsValue != undefined) {
                if(!info.ezBIDSvalues.includes(info.eventsValue) && info.ezBIDSvalues.includes(info.eventsValue.replace(/^0+/, ''))) {
                    info.eventsValue = info.eventsValue.replace(/^0+/, '')
                    info.detectionMethod = "ignoring zero-padding led to proper match"
                }
                
                info.ezBIDSvalues.forEach(ezBIDSvalue=>{
                    if(!info.eventsValue.includes(ezBIDSvalue) && info.eventsValue.includes(ezBIDSvalue.replace(/^0+/, ''))) {
                        info.eventsValue = info.eventsValue.replace(/^0+/, '')
                        info.detectionMethod = "ignoring zero-padding led to proper match"
                    }
                  });
            }

            /* 4th stage: if task eventValue can't be determined, look for task name(s) used in ezBIDS in event files
            values (not just column names).
            */
            if(entity == "task" && eventsMappingInfo.task.eventsValue === undefined) {
                const taskNames = eventsMappingInfo.task.ezBIDSvalues.map(v=>v.toLowerCase());
                events.forEach(event=>{
                    for(const key in event) {
                        if(taskNames.includes(event[key])) {
                            info.eventsValue = event[key];
                            info.detectionMethod = "task identifying information was found in events file (not column name)"
                        }
                    }
                });
            }
        }

        /*
        Time to create func/events object(s). If mapping isn't perfect, we'll make a standalone mapping
        for the func/events object(s) that users can then adjust accordingly. This is so that ezBIDS doesn't
        crash if the mapping isn't perfect, and because we don't want to assume a mapping if we can't
        excplitly map it.
        */

        let section_id = 1 //default value unless otherwise determined
        let ModifiedSeriesNumber = "01" //default value unless otherwise determined
        let sidecar = {}

        //create new events object
        const object = {
            exclude: false,
            type: "func/events",
            // series_idx: series_idx, //don't need, I think
            subject_idx: undefined,
            session_idx: undefined,
            ModifiedSeriesNumber: ModifiedSeriesNumber,

            entities: {
                subject: undefined,
                session: undefined,
                task: undefined,
                run: undefined
            },
            items: [
                {
                    name: fileExt,
                    events, //here goes the content of the event object parsed earlier
                    path: file.path //let's use the original file.path as "path" - although it's not..
                },
                {
                    name: "json",
                    path: file.path,
                    sidecar,
                    sidecar_json: JSON.stringify(sidecar),
                }
            ],
            //these aren't used, but I believe we have to initialize it
            analysisResults: {
                section_id: section_id,
                errors: [],
                warnings: []

            },
            paths: [],
            validationErrors: [],
            validationWarnings: []
        };

        //modify object values
        for(const entity of ["subject", "session", "task", "run"]) {
            let ezBIDSvalues = eventsMappingInfo[entity].ezBIDSvalues
            let eventsValue = eventsMappingInfo[entity].eventsValue
            if(eventsValue) {
                object.entities[entity] = eventsValue
            }

            let subjectsInfo = ezbids.subjects

            //update subject_idx
            if(entity == "subject" && ezBIDSvalues.includes(eventsValue)) {
                object.subject_idx = subjectsInfo.findIndex(function (subjectsInfo) {
                    return subjectsInfo.subject === eventsMappingInfo.subject.eventsValue
                });
            }

            //update session_idx
            if(entity == "session" && object.subject_idx && eventsMappingInfo.session.ezBIDSvalues.length > 0 && ezBIDSvalues.includes(eventsValue)) {
                let sessionsInfo = subjectsInfo[object.subject_idx].sessions

                object.session_idx = sessionsInfo.findIndex(function (sessionsInfo) {
                    return sessionsInfo.session === eventsMappingInfo.session.eventsValue
                });
            }
        }

        //set subject_idx and session_idx to 0 if they're still undefined at this point, and adjust task & run entity labels
        if(object.subject_idx === undefined) {
            object.subject_idx = 0
            if(!eventsMappingInfo.subject.eventsValue) {
                object.entities.subject = "XX" + randSubID.toString() //set the subjectID to a new value, which user would then correct.
                randSubID++
            }else{
                object.entities.subject = eventsMappingInfo.subject.eventsValue

            }
        }

        if(object.session_idx === undefined) {
            object.session_idx = 0
            if(eventsMappingInfo.session.eventsValue) {
                object.entities.session = eventsMappingInfo.session.eventsValue
            }else{ // if(eventsMappingInfo.session.ezBIDSvalues.length > 0 && eventsMappingInfo.session.ezBIDSvalues.filter(e=>e != "").length > 0) {
                if(!eventsMappingInfo.session.eventsValue && sessions.length > 0) {
                    object.entities.session = "XX" + randSesID.toString() //set the sessionID to a new value, which user would then correct.
                    randSesID++
                }
            }
        }

        if(object.entities.task === undefined) {
            object.entities.task = randTaskName //set the task name to a new value, which user would then correct.
        }

        if(object.entities.run === undefined) {
            object.entities.run = randRunID //set the runID to a new value, which user would then correct.
            randRunID++
        }

        //update section_id, series_idx, and ModifiedSeriesNumber
        if(sessions.length > 0) {
            try {
                section_id = ezbids.objects.find(e=>e._entities.subject == eventsMappingInfo.subject.eventsValue &&
                    e._entities.session == eventsMappingInfo.session.eventsValue &&
                    e._entities.task == eventsMappingInfo.task.eventsValue &&
                    e._entities.run == eventsMappingInfo.run.eventsValue
                    ).analysisResults.section_id
            }
            catch {
                section_id = 1
            }

            try {
                ModifiedSeriesNumber = ezbids.objects.find(e=>e._entities.subject == eventsMappingInfo.subject.eventsValue &&
                e._entities.session == eventsMappingInfo.session.eventsValue &&
                e._entities.task == eventsMappingInfo.task.eventsValue &&
                e._entities.run == eventsMappingInfo.run.eventsValue &&
                e._type == "func/bold" &&
                (e._entities.part == "" || e._entities.part == "mag")
                ).ModifiedSeriesNumber
            }
            catch {
                ModifiedSeriesNumber = "01"
            }

        }else{
            try {
                section_id = ezbids.objects.find(e=>e._entities.subject == eventsMappingInfo.subject.eventsValue &&
                    e._entities.task == eventsMappingInfo.task.eventsValue &&
                    e._entities.run == eventsMappingInfo.run.eventsValue
                    ).analysisResults.section_id
            }
            catch {
                section_id = 1
            }

            try {
                ModifiedSeriesNumber = ezbids.objects.find(e=>e._entities.subject == eventsMappingInfo.subject.eventsValue &&
                e._entities.task == eventsMappingInfo.task.eventsValue &&
                e._entities.run == eventsMappingInfo.run.eventsValue &&
                e._type == "func/bold" &&
                (e._entities.part == "" || e._entities.part == "mag")
                ).ModifiedSeriesNumber
            }
            catch {
                ModifiedSeriesNumber = "01"
            }

        }
        object.analysisResults.section_id = section_id
        object.ModifiedSeriesNumber = ModifiedSeriesNumber

        eventObjects.push(object);
    });

    return eventObjects;
}


/*
this function receives one example event object. we will do our best to map the event keys (columns) and
map them to bids events.tsv column names. If an ezBIDS configuration (finalized.json) was uploaded, with
imaging data, those mappings are auto generated when user uploads new events timing files.
*/
export function mapEventColumns(ezbids_events, events) {
    if(ezbids_events.columns.onset != "") {
        return ezbids_events.columns
    } else {
        // //we only have to return things that we found out.. (leave other things not set)
        // const columns = Object.values(Object.keys(events[0]))
        return {

            //type definitions are in store/index

            onsetLogic: "eq",
            onset: null,
            onset2: null,
            onsetUnit: "sec",

            durationLogic: "eq",
            duration: null,
            duration2: null,
            durationUnit: "sec",

            sampleLogic: "eq",
            sample: null,
            sample2: null,
            sampleUnit: "samples",

            trialType: null,

            responseTimeLogic: "eq",
            responseTime: null,
            responseTime2: null,
            responseTimeUnit: "sec",

            values: null,

            HED: null,

            stim_file: null
        }
    }
}
