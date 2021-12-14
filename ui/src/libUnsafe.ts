// @ts-nocheck

//deepEqual and isPrimitive functions come from https://stackoverflow.com/a/45683145
function deepEqual(obj1, obj2) {
    /*
    Determines if two arrays are equal or not. Better then JSON.stringify
    because this accounts for different ordering, only cares about whether
    keys and values match.
    */

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

function isPrimitive(obj) {
    return (obj !== Object(obj));
}

export function setSectionIDs($root) {
    /*
    Set section_ID value for each acquisition, beginning with value of 1. A section is
    ezBIDS jargin for each time participant comes out and then re-enters scanner. Each time
    a non-adjacent localizer is detected, the section_ID value is increased by 1. The
    section_ID value helps for determining fmap IntendedFor mapping, where field maps
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
                    obj.analysisResults.section_ID = sectionID
                }else{
                    obj.analysisResults.section_ID = sectionID
                }
                obj_idx++
            })
        });
    });
}

export function funcQA($root) {
    /*
    1). Exclude functional bold acquisitions have less than the specified volume threshold from
    Series level. If unspecified, default is 50 volumes, because a func/bold with < 50 probably
    indicates a restart, incomplete, or calibration run.

    2). If func/bold acquisition is excluded, make sure that corresponding
    func/sbref, and func/bold (part-phase) are all excluded as well,
    if they exist.

    3). Exclude func/sbref if its PhaseEncodingDirection (PED) is different
    from the corresponding func/bold PED.
    */

    // #1
    $root.series.forEach(s=> {
        if(s.type == "func/bold") {
            let series_idx = s.series_idx
            let VolumeThreshold = s.VolumeThreshold

            $root.objects.forEach(o=> {
                if(o.series_idx == series_idx) {
                    o.exclude = false
                    o.analysisResults.errors = []

                    //apply VolumeThreshold exclusion criteria
                    if(o.analysisResults.NumVolumes < VolumeThreshold) {
                        o.exclude = true
                        o.analysisResults.errors = [`Functional bold acquisition contains less than ${VolumeThreshold} volumes, a possible indication of a restarted, incomplete, or calibration run. Please check to see if you want to keep this acquisition, otherwise this acquisition will be excluded from BIDS conversion.`]
                    }
                }
            })
        }
    })

    $root.objects.forEach(o=> {
        // #2

        //update analysisResults.errors in case user went back to Series and adjusted things
        if(o._type == "func/bold" && o.exclude == false && (!o._entities.mag || o._entities.mag == "mag")) {
            let funcBoldEntities = o._entities
            let goodFuncSBRef = $root.objects.filter(e=>e._type == "func/sbref" && deepEqual(e._entities, funcBoldEntities))
            let goodFuncBoldPhase = $root.objects.filter(e=>e._type == "func/bold" && e._entities.mag == "phase" && deepEqual(Object.keys(e._entities).filter(e=>e != "part"), funcBoldEntities))

            for(const good of [goodFuncSBRef, goodFuncBoldPhase]) {
                good.forEach(g=>{
                    g.analysisResults.errors = []
                })
            }
        }

        //now check for corresponding func/bold == exclude, and go from there
        if(o._type == "func/bold" && o.exclude == true && (!o._entities.mag || o._entities.mag == "mag")) {
            let funcBoldEntities = o._entities
            let badFuncSBRef = $root.objects.filter(e=>e._type == "func/sbref" && deepEqual(e._entities, funcBoldEntities))
            let badFuncBoldPhase = $root.objects.filter(e=>e._type == "func/bold" && e._entities.mag == "phase" && deepEqual(Object.keys(e._entities).filter(e=>e != "part"), funcBoldEntities))

            for(const bad of [badFuncSBRef, badFuncBoldPhase]) {
                bad.forEach(b=>{
                    b.analysisResults.errors = [`The corresponding func/bold (#${o.series_idx}) to this acquisition has been set to exclude from BIDS conversion. Recommendation is to also exclude this acquisition from BIDS conversion, unless you have good reason for keeping it.`]
                })
            }
        }

        // #3
        if(o._type == "func/bold" && (!o._entities.mag || o._entities.mag == "mag")) {
            let boldEntities = o._entities
            let boldPED = o.items[0].sidecar.PhaseEncodingDirection
            let badSBRef = $root.objects.filter(e=>e._type == "func/sbref" && deepEqual(e._entities, boldEntities) &&
                                                e.items[0].sidecar.PhaseEncodingDirection != boldPED).map(e=>e.idx)
            badSBRef.forEach(bad=> {
                $root.objects[bad].exclude = true
                $root.objects[bad].analysisResults.errors = [`Functional sbref has a different PhaseEncodingDirection than its corresponding functional bold (#${o.series_idx}). This is a data error, therefore this sbref will be set to exclude from BIDS conversion.`]
            })
        }
    })

    // #4
    $root._organized.forEach(subGroup=>{
        subGroup.sess.forEach(sesGroup=>{
            let dwiDir0 = {}
            let dwiDir180 = {}

            let protocol = sesGroup.objects
            protocol.Foreach(p=>{
                if(p._type == "dwi/dwi") {
                    console.log(p._SeriesDescription)
                }
            })
        })
    })
}

// function newSetIntendedFor($root) {
//     /*
//     This function applies the IntendedFor fmap mapping, based on user
//     input at SeriesPage.
//     */
//     $root.series.forEach(s=> {
//         if(s.type.includes("fmap")) {
//             let intendedFor = s.IntendedFor

// }



export function fmapQA($root) {
    /* Assesses fieldmaps for improper PEDs (for spin-echo field maps),
    and excludes extra fieldmaps in section.
    */

    $root._organized.forEach(subGroup=>{
        subGroup.sess.forEach(sesGroup=>{

            // Determine unique sectionIDs
            let allSectionIDs = sesGroup.objects.map(e=>e.analysisResults.section_ID)
            let sectionIDs = Array.from(new Set(allSectionIDs))

            // Loop through sections (no excluded acquisitions included)
            sectionIDs.forEach(s=> {
                let section = sesGroup.objects.filter(e=>e.analysisResults.section_ID == s && !e._exclude)

                let funcObjs = section.filter(e=>e._type == 'func/bold' || e._type == 'func/sbref')
                let dwiObjs = section.filter(e=>e._type == 'dwi/dwi')
                let fmapSpinEchoFuncObjs = section.filter(e=>e._type.startsWith('fmap/epi') && e._forType == 'func/bold')
                let fmapSpinEchoDwiObjs = section.filter(e=>e._type.startsWith('fmap/epi') && e._forType == 'dwi/dwi')
                let fmapMagPhaseObjs = section.filter(function (e) {
                    return e._type.startsWith('fmap/magnitude1') ||
                    e._type.startsWith('fmap/magnitude2') ||
                    e._type.includes('phase1') ||
                    e._type.includes('phase2')
                });

                let fmapMagPhaseCheck = fmapMagPhaseObjs.filter(e=>e._type.includes('fmap/phase1'))
                if(!fmapMagPhaseCheck.length) {
                    fmapMagPhaseObjs = []
                }

                let fmapMagPhasediffObjs = section.filter(function (e) {
                    return e._type.startsWith('fmap/magnitude1') ||
                    e._type.startsWith('fmap/magnitude2') ||
                    e._type.includes('phasediff')
                });

                let fmapMagPhasediffCheck = fmapMagPhasediffObjs.filter(e=>e._type.includes('fmap/phasediff'))
                if(!fmapMagPhasediffCheck.length) {
                    fmapMagPhasediffObjs = []
                }

                let fmapMagFieldmapObjs = section.filter(function (e) {
                    return e._type.startsWith('fmap/magnitude') ||
                    e._type.includes('fieldmap')
                })

                let fmapMagFieldmapCheck = fmapMagFieldmapObjs.filter(e=>e._type.includes('fmap/fieldmap'))
                if(!fmapMagFieldmapCheck.length) {
                    fmapMagFieldmapObjs = []
                }

                // Perform fmap QA
                if(funcObjs.length > 0) {

                    // Remove all spin-echo fmaps except for last two
                    if(fmapSpinEchoFuncObjs.length > 2) {
                        let fmapFuncBadObjs = fmapSpinEchoFuncObjs.slice(0,-2)
                        fmapFuncBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Multiple spin echo field map pairs detected in section; only selecting last pair for BIDS conversion. The other pair acquisition(s) in this section will not be included in the BIDS output']
                        });
                    }

                    // Remove spin-echo fmap if only 1 found
                    if(fmapSpinEchoFuncObjs.length == 1) {
                        fmapSpinEchoFuncObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Only one spin echo field map found; need pair. This acquisition will not be included in the BIDS output']
                        });
                    }

                    // Re-determine spin-echo fmaps meant for func/bold (in event that some were set for exclusion)
                    fmapSpinEchoFuncObjs = fmapSpinEchoFuncObjs.filter(e=>!e.exclude)

                    // Check for proper PEDs for spin-echo pairs
                    if(fmapSpinEchoFuncObjs.length == 2) {
                        let fmapFuncPEDs = fmapSpinEchoFuncObjs.map(e=>e.items[0].sidecar.PhaseEncodingDirection)
                        if(fmapFuncPEDs[0].toString().split('').reverse().join('').slice(-1) == fmapFuncPEDs[1].toString().split('').reverse().join('').slice(-1)) {
                            if((fmapFuncPEDs[0].length != 2 || fmapFuncPEDs[1].length != 1) && (fmapFuncPEDs[0].length != 1 || fmapFuncPEDs[1].length != 2)) {
                                fmapSpinEchoFuncObjs.forEach(obj=> {
                                    obj.exclude = true
                                    obj.analysisResults.errors = ['Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output']
                                });
                            }
                        }else{
                            fmapSpinEchoFuncObjs.forEach(obj=> {
                                obj.exclude = true
                                obj.analysisResults.errors = ['Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output']
                            });
                        }
                    }

                    // Remove magnitudes & phasediff if less than 3
                    if(fmapMagPhasediffObjs.length < 3) {
                        fmapMagPhasediffObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Need triplet for magnitude/phasediff field maps. This acquisition will not be included in the BIDS output']
                        });
                    }

                    // Remove all magnitudes and phasediff except for last 3
                    if(fmapMagPhasediffObjs.length > 3) {
                        let fmapMagPhasediffBadObjs = fmapMagPhasediffObjs.slice(0,-3)
                        fmapMagPhasediffBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['More than three magnitude/phasediff field map acquisitions found in section. Only selecting most recent three. Others will not be included in the BIDS output']
                        });
                    }

                    // Remove magnitudes and phases if less than 4
                    if(fmapMagPhaseObjs.length < 4) {
                        fmapMagPhaseObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Need four images (2 magnitude, 2 phase). This acquisition will not be included in the BIDS output']
                        });
                    }

                    // Remove all magnitudes and phases except for last 4
                    if(fmapMagPhaseObjs.length > 4) {
                        let fmapMagPhaseBadObjs = fmapMagPhaseObjs.slice(0,-4)
                        fmapMagPhaseBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Multiple images sets of (2 magnitude, 2 phase) field map acquisitions found in section. Only selecting most recent set. Other(s) will not be included in the BIDS output']
                        });
                    }

                    // Remove all magnitudes & fieldmaps except for last 2
                    if(fmapMagFieldmapObjs.length > 2) {
                        let fmapMagFieldmapBadObjs = fmapMagFieldmapObjs.slice(0,-2)
                        fmapMagFieldmapBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Multiple image sets of magnitude & fieldmap field map acquistions found in section. Only selecting most recent pair. Other(s) will not be included in BIDS output']
                        });
                    }

                    // Remove all magnitudes & fieldmaps if less than 2
                    if(fmapMagFieldmapObjs.length < 2) {
                        fmapMagFieldmapObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Need pair (magnitude & fieldmap). This acquisition will not be included in BIDS output']
                        });
                    }

                }else{
                    fmapSpinEchoFuncObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.analysisResults.errors = ['No valid func/bold acquisitions found in section, spin echo field map pair will not be included in the BIDS output']
                    });

                    fmapMagPhasediffObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.analysisResults.errors = ['No valid func/bold acquisitions found in section, magnitude & phasediff field maps will not be included in the BIDS output']
                    });

                    fmapMagPhaseObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.analysisResults.errors = ['No valid func/bold acquisitions found in section, magnitude & phase field maps will not be included in the BIDS output']
                    });

                    fmapMagFieldmapObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.analysisResults.errors = ['No valid func/bold acquisitions found in section, magnitude & fieldmap will not be included in the BIDS output']
                    })
                }

                // Remove fmap meant for dwi/dwi acquisition(s) if no valid dwi/dwi found in section
                if(dwiObjs.length == 0 && fmapSpinEchoDwiObjs.length > 0) {
                    fmapSpinEchoDwiObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.analysisResults.errors = ['No valid dwi/dwi acquisitions found in section, spin echo field map will not be included in the BIDS output']
                    });
                }

                // Remove fmap meant for dwi/dwi if more than 1 fmap
                if(fmapSpinEchoDwiObjs.length > 1) {
                    fmapSpinEchoDwiObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.analysisResults.errors = ['Multiple spin echo field maps (meant for dwi/dwi) detected in section; only selecting last one for BIDS conversion. The other fmap acquisition(s) in this section will not be included in the BIDS output']
                    });
                }
            });
        });
    });
}
export function setRun($root) {
    // Set run entity label if not already specified at Series level

    // Loop through subjects

    //for(const subject in $root._organized) {
    $root._organized.forEach(subGroup=>{

        // Loop through sessions
        //const sessions = subGroup.sess
        //for(const session in sessions) {
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
    // Apply fmap intendedFor mapping

    // Loop through subjects
    //for(const subject in $root._organized) {
    $root._organized.forEach(subGroup=>{

        subGroup.sess.forEach(sesGroup=>{
            // Determine unique sectionIDs
            let allSectionIDs = sesGroup.objects.map(e=>e.analysisResults.section_ID)
            let sectionIDs = Array.from(new Set(allSectionIDs))

            // Loop through sections (no excluded acquisitions included)
            sectionIDs.forEach(s=> {
                let section = sesGroup.objects.filter(e=>e.analysisResults.section_ID == s && !e._exclude)

                let funcObjs = section.filter(e=>e._type == 'func/bold' || e._type == 'func/sbref' && !e._exclude)
                let dwiObjs = section.filter(e=>e._type == 'dwi/dwi' && !e._exclude)
                let fmapFuncObjs = section.filter(e=>e._type.startsWith('fmap') && e._forType == 'func/bold' && !e._exclude)
                let fmapDwiObjs = section.filter(e=>e._type.startsWith('fmap') && e._forType == 'dwi/dwi' && !e._exclude)

                // Assign IntendedFor information
                fmapFuncObjs.forEach(obj=> {
                    obj.IntendedFor = funcObjs.map(e=>e.idx)
                });

                fmapDwiObjs.forEach(obj=> {
                    obj.IntendedFor = dwiObjs.map(e=>e.idx)
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

export function validateEntities(entities/*: Series*/) {
    const errors = [];
    //validate entity (only alpha numeric values)
    for(const k in entities) {
        const v = entities[k];
        if(v && !/^[a-zA-Z0-9]*$/.test(v)) {
            errors.push("Entity:"+k+" contains non-alphanumeric character");
        }
    }
    return errors;
}

export function find_separator(filePath, fileData) {
    if(filePath.indexOf('.tsv') > -1) {
        return /[ \t]+/;
    }else if(filePath.indexOf('.out') > -1 || filePath.indexOf('.csv') > -1)  {
        return /[ ,]+/;
    }else if(filePath.indexOf('.txt') > -1) {
        const data = fileData
        const lines = data.trim().split("\n").map(l=>l.trim());
        if(lines[0].indexOf(',') > -1) {
            return /[ ,]+/;
        }else{
            return /[ \t]+/;
        }
    }else if(filePath.indexOf('.xlsx') > -1) {
        return /[ ,]+/;
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
    const sessions = Array.from(new Set(ezbids.subjects.map(e=>e.sessions)[0].filter(e=>e.exclude == false).map(e=>e.session)))
    const tasks = Array.from(new Set(ezbids.objects.map(e=>e._entities).filter(e=>(e.part == "" || e.part == "mag") && (e.task != "" && e.task != "rest" && e.task !== undefined)).map(e=>e.task)))
    const runs = Array.from(new Set(ezbids.objects.filter(e=>e._entities.task != "" && e._entities.task != "rest" && e._entities.task != undefined).map(e=>e._entities.run)))
    const numEventFiles = files.length
    // const uniqueSectionIDs = Array.from(new Set(ezbids.objects.map(e=>e.analysisResults.section_ID)))

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

    // Sort through events file(s) list
    files.forEach(file=>{
        const fileExt = file.path.split(".").pop();

        // Parse the data, depending on the file extension (and header information)
        let events;
        switch(fileExt) {
        // Excel workbook formats (.xlsx, .xlsm, .xls)
        case "xlsx":
        case "xlsm":
        case "xls":
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
            if(info.eventsValue == undefined) {
                const lowerCaseFilePath = file.path.toLowerCase()
                Object.values(info.MappingKeys).forEach(mappingKey=>{
                    const splitFilePath = lowerCaseFilePath.split(mappingKey)
                    if(splitFilePath.length > 1) { //if a mappingKey is in the file path, the length of the splitFilePath array will be > 1
                        let lastSplit = splitFilePath.slice(-1)[0] //splitFilePath.slice(-1) is an array of length 1, so grab the first (i.e. entire) array
                        const lastSplitFirstChar = lastSplit[0]
                        Object.values(sepChars).forEach(sepChar=>{ //remove leading separator character(s), if they exist
                            if(sepChar == lastSplitFirstChar) {
                                lastSplit = lastSplit.substring(1)
                            }
                        });
                        info.eventsValue = lastSplit.split(/[._-]+/)[0] //first index will contain the value we want (e.g. sub1 ==> 1)
                        info.detectionMethod = "identifying information found in file path";
                    }
                });
            }

            //3rd stage: if ezBIDSvalues lengths == 1, set that value to the corresponding eventsValue
            if(info.eventsValue == undefined && info.ezBIDSvalues.length == 1) {
                info.eventsValue = info.ezBIDSvalues[0] //in this scenario info.ezBIDSvalues has a length of 1, so simply get the first indexed value
                info.detectionMethod = `"identifying information found because there is only one ${entity} value, so assumption is it's that"`
            }

            //sanity checks, based on the current mapping performed
            Object.keys(eventsMappingInfo).forEach(key=>{
                /* 1). if a mismatch exists between any key's ezBIDSvalue and eventsValue, and the length of
                ezBIDSvalues == 1, then the ezBIDSvalue takes precedence because that's what the user has
                explicitly specified in ezBIDS.
                */
                if(!info.ezBIDSvalues.includes(info.eventsValue) && info.ezBIDSvalues.length == 1) {
                    info.eventsValue = info.ezBIDSvalues[0]
                }

                /* 2). ignore zero-padding in subject, session, and run eventsValue if the zero-padded
                value doesn't exist in corresponding ezBIDSvalues. For example, if subject ID in ezBIDS
                is "1", but the corresponding events subject ID is "01", simply assume the two are the same.
                */
                if(key != "task" && info.eventsValue) {
                    if(!info.ezBIDSvalues.includes(info.eventsValue) && info.ezBIDSvalues.includes(info.eventsValue.replace(/^0+/, ''))) {
                        info.eventsValue = info.eventsValue.replace(/^0+/, '')
                    }
                }
            })
        }

        /* if task eventValue can't be determined, look for task names used in ezBIDS in event files
        values (not just column names).
        */
        if(!eventsMappingInfo.task.eventsValue) {
            const taskNames = eventsMappingInfo.task.ezBIDSvalues.map(v=>v.toLowerCase());
            events.forEach(event=>{
                for(const key in event) {
                    if(taskNames.includes(event[key])) {
                        eventsMappingInfo.task.eventsValue = event[key];
                        info.detectionMethod = "task identifying information was found in events file (not column name)"
                    }
                }
            });
        }

        /* Determine the section_ID, series_idx, and ModifiedSeriesNumber values of the events object(s).
        This is necessary to properly organize the events object(s) on the Objects page.
        */
        let section_ID = 1 //default value unless otherwise determined
        let series_idx = 0 //default value unless otherwise determined
        let ModifiedSeriesNumber = "01" //default value unless otherwise determined

        for(const entity of ["subject", "session", "task", "run"]) {
            if(eventsMappingInfo[entity].ezBIDSvalues != "" && !eventsMappingInfo[entity].eventsValue) { //user has specified subject, session, task, and/or run entities, but mapping to events file(s) doesn't work
                section_ID = undefined
                break;
            }
        }

        if(section_ID) {
            try {
                section_ID = ezbids.objects.find(e=>e._entities.subject == eventsMappingInfo.subject.eventsValue &&
                    e._entities.session == eventsMappingInfo.session.eventsValue &&
                    e._entities.task == eventsMappingInfo.task.eventsValue &&
                    e._entities.run == eventsMappingInfo.run.eventsValue
                    ).analysisResults.section_ID
            }
            catch {
                section_ID = 1
            }

            // try {
            //     series_idx = ezbids.objects.find(e=>e._entities.subject == eventsMappingInfo.subject.eventsValue &&
            //         e._entities.session == eventsMappingInfo.session.eventsValue &&
            //         e._entities.task == eventsMappingInfo.task.eventsValue &&
            //         e._entities.run == eventsMappingInfo.run.eventsValue &&
            //         e._type == "func/bold" &&
            //         (e._entities.part == "" || e._entities.part == "mag")
            //         ).series_idx
            // }
            // catch {
            //     series_idx = 0
            // }

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
            section_ID = 1
        }

        const subjectInfo = ezbids.subjects.filter(e=>e.subject == eventsMappingInfo.subject.eventsValue)
        let sessionInfo;

        sessionInfo = subjectInfo[0].sessions.filter(e=>e.session == eventsMappingInfo.subject.eventsValue)
        if(sessionInfo.length == 0) {
            sessionInfo = subjectInfo[0].sessions.filter(e=>e.session == "")
        }

        // Indexing the first (and only value) but will need to filter this out better for multi-session data
        const subject = subjectInfo[0];
        const session = sessionInfo[0];
        const patientInfo = subject.PatientInfo[0];

        //register new event object using the info we gathered above
        const object = Object.assign({
            exclude: false,
            type: "func/events",
            // series_idx: series_idx, //may need to comment this line out depending on behavior
            subject_idx: ezbids.subjects.indexOf(subject),
            session_idx: subject.sessions.indexOf(session),
            ModifiedSeriesNumber: ModifiedSeriesNumber,

            entities: {
                subject: eventsMappingInfo.subject.eventsValue,
                session: eventsMappingInfo.session.eventsValue,
                task: eventsMappingInfo.task.eventsValue,
                run: eventsMappingInfo.run.eventsValue
            },
            items: [],
            //these aren't used, but I believe we have to initialize it
            analysisResults: {
                section_ID: section_ID,
                errors: []

            },
            paths: [],
            validationErrors: [],
        }, patientInfo, session); //we need to set subject / session specific fields that we figured out earlier

        //event object also need some item info!
        object.items.push({
            name: fileExt,
            events, //here goes the content of the event object parsed earlier
            path: file.path //let's use the original file.path as "path" - although it's not..
        });

        const sidecar = {};

        object.items.push({
            name: "json",
            path: file.path,
            sidecar,
            sidecar_json: JSON.stringify(sidecar),
        });

        // console.log("created event object", object);
        eventObjects.push(object);
    });

    return eventObjects;
}


/*
this function receives one example event object. we will do our best to map the event keys (columns) and
map them to bids events.tsv column names.
*/
export function mapEventColumns(events) {
    //we only have to return things that we found out.. (leave other things not set)
    const columns = Object.values(Object.keys(events[0]))

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

        HED: null
    }
}
