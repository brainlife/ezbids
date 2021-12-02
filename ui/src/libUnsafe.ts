// @ts-nocheck


export function setSectionIDs($root) {
    /*
    Set a section_ID value for each acquisition, beginning with a value of 1. A section is
    ezBIDS jargin for each time participant comes out and then re-enters scanner. Each time
    a non-adjacent localizer is detected, the section_ID value is increased by 1. The
    section_ID value helps for determining fmap IntendedFor mapping, where field maps
    cannot be applied to acquisitions from different sections.
    */

    //for (const subject in $root._organized) {
    $root._organized.forEach(subGroup=>{
        const subject = subGroup.sub;
        //const sessions = $root._organized[subject].sess
        //for (const session in sessions) {
        subGroup.sess.forEach(sesGroup=>{
            let protocol = sesGroup.objects
            let sectionID = 1
            let obj_idx = 0
            protocol.forEach(obj=> {
                let message = $root.series[protocol[obj_idx].series_idx].message

                let previousMessage = ""
                if (obj_idx == 0) previousMessage = "";
                else previousMessage = $root.series[protocol[obj_idx - 1].series_idx].message
                if (obj_idx != 0 && message.includes("localizer") && (previousMessage == "" || !previousMessage.includes("localizer"))) {
                    sectionID++;
                    obj.analysisResults.section_ID = sectionID
                } else {
                    obj.analysisResults.section_ID = sectionID
                }
                obj_idx++
            })
        });
    });
}

export function funcQA($root) {
    /*
    Exclude functional bold acquisitions have less than the specified volume threshold from
    Series level. If unspecified, default is 50 volumes because a func/bold with < 50 probably
    indicates a restart or failure.
    */
    $root.series.forEach(s=> {
        if (s.type == "func/bold") {
            let series_idx = s.series_idx
            let VolumeThreshold = s.VolumeThreshold

            $root.objects.forEach(o=> {
                if (o.series_idx == series_idx) {
                    o.exclude = false
                    if (o.analysisResults.NumVolumes < VolumeThreshold) {
                        o.exclude = true
                        o.analysisResults.errors = [`Functional bold acquisition contains less than ${VolumeThreshold} volumes, a possible indication of a failed/restarted run. Please check to see if you want to keep this acquisition, otherwise this acquisition will be excluded from BIDS conversion.`]
                    }
                }
            })
        }
    })

    //If func/bold acquisition is excluded, make sure that corresponding func/sbref is also excluded as well
    $root.objects.forEach(o=> {
        if (o._type == "func/bold" && o.exclude == true) {
            let funcBoldEntities = o._entities
            let badFuncSBRef = $root.objects.filter(e=>e._type == "func/sbref" && JSON.stringify(e._entities) === JSON.stringify(funcBoldEntities)).map(e=>e.idx)
            badFuncSBRef.forEach(bad=> {
                $root.objects[bad].exclude = true
                $root.objects[bad].analysisResults.errors = ["Functional sbref has a corresponding functional bold that has been set to exclude from BIDS conversion. Therefore, this sbref will also be set to exclude from BIDS conversion."]
            })
        }
    })

    //Exclude func/sbref if its PhaseEncodingDirection is different from the corresponding func/bold PhaseEncodingDirection
    $root.objects.forEach(o=> {
        if (o._type == "func/bold") {
            let boldEntities = o._entities
            let boldPED = o.items[0].sidecar.PhaseEncodingDirection
            let badSBRef = $root.objects.filter(e=>e._type == "func/sbref" && JSON.stringify(e._entities) === JSON.stringify(boldEntities) &&
                                                e.items[0].sidecar.PhaseEncodingDirection != boldPED).map(e=>e.idx)
            badSBRef.forEach(bad=> {
                $root.objects[bad].exclude = true
                $root.objects[bad].analysisResults.errors = ["Functional sbref has a different PhaseEncodingDirection than its corresponding functional bold. This is a data error, therefore this sbref will be set to exclude from BIDS conversion."]
            })
        }
    })
}



export function fmapQA($root) {
    // Assesses fieldmaps for improper PEDs (for spin-echo field maps),
    // and excludes extra fieldmaps in section

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
                if (!fmapMagPhaseCheck.length) {
                    fmapMagPhaseObjs = []
                }

                let fmapMagPhasediffObjs = section.filter(function (e) {
                    return e._type.startsWith('fmap/magnitude1') ||
                    e._type.startsWith('fmap/magnitude2') ||
                    e._type.includes('phasediff')
                });

                let fmapMagPhasediffCheck = fmapMagPhasediffObjs.filter(e=>e._type.includes('fmap/phasediff'))
                if (!fmapMagPhasediffCheck.length) {
                    fmapMagPhasediffObjs = []
                }

                let fmapMagFieldmapObjs = section.filter(function (e) {
                    return e._type.startsWith('fmap/magnitude') ||
                    e._type.includes('fieldmap')
                })

                let fmapMagFieldmapCheck = fmapMagFieldmapObjs.filter(e=>e._type.includes('fmap/fieldmap'))
                if (!fmapMagFieldmapCheck.length) {
                    fmapMagFieldmapObjs = []
                }

                // Perform fmap QA
                if (funcObjs.length > 0) {

                    // Remove all spin-echo fmaps except for last two
                    if (fmapSpinEchoFuncObjs.length > 2) {
                        let fmapFuncBadObjs = fmapSpinEchoFuncObjs.slice(0,-2)
                        fmapFuncBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Multiple spin echo field map pairs detected in section; only selecting last pair for BIDS conversion. The other pair acquisition(s) in this section will not be included in the BIDS output']
                        });
                    }

                    // Remove spin-echo fmap if only 1 found
                    if (fmapSpinEchoFuncObjs.length == 1) {
                        fmapSpinEchoFuncObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Only one spin echo field map found; need pair. This acquisition will not be included in the BIDS output']
                        });
                    }

                    // Re-determine spin-echo fmaps meant for func/bold (in event that some were set for exclusion)
                    fmapSpinEchoFuncObjs = fmapSpinEchoFuncObjs.filter(e=>!e.exclude)

                    // Check for proper PEDs for spin-echo pairs
                    if (fmapSpinEchoFuncObjs.length == 2) {
                        let fmapFuncPEDs = fmapSpinEchoFuncObjs.map(e=>e.items[0].sidecar.PhaseEncodingDirection)
                        if (fmapFuncPEDs[0].toString().split('').reverse().join('').slice(-1) == fmapFuncPEDs[1].toString().split('').reverse().join('').slice(-1)) {
                            if ((fmapFuncPEDs[0].length != 2 || fmapFuncPEDs[1].length != 1) && (fmapFuncPEDs[0].length != 1 || fmapFuncPEDs[1].length != 2)) {
                                fmapSpinEchoFuncObjs.forEach(obj=> {
                                    obj.exclude = true
                                    obj.analysisResults.errors = ['Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output']
                                });
                            }
                        } else {
                            fmapSpinEchoFuncObjs.forEach(obj=> {
                                obj.exclude = true
                                obj.analysisResults.errors = ['Spin echo field map pair do not have opposite phase encoding directions (PEDs) and will not be included in the BIDS output']
                            });
                        }
                    }

                    // Remove magnitudes & phasediff if less than 3
                    if (fmapMagPhasediffObjs.length < 3) {
                        fmapMagPhasediffObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Need triplet for magnitude/phasediff field maps. This acquisition will not be included in the BIDS output']
                        });
                    }

                    // Remove all magnitudes and phasediff except for last 3
                    if (fmapMagPhasediffObjs.length > 3) {
                        let fmapMagPhasediffBadObjs = fmapMagPhasediffObjs.slice(0,-3)
                        fmapMagPhasediffBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['More than three magnitude/phasediff field map acquisitions found in section. Only selecting most recent three. Others will not be included in the BIDS output']
                        });
                    }

                    // Remove magnitudes and phases if less than 4
                    if (fmapMagPhaseObjs.length < 4) {
                        fmapMagPhaseObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Need four images (2 magnitude, 2 phase). This acquisition will not be included in the BIDS output']
                        });
                    }

                    // Remove all magnitudes and phases except for last 4
                    if (fmapMagPhaseObjs.length > 4) {
                        let fmapMagPhaseBadObjs = fmapMagPhaseObjs.slice(0,-4)
                        fmapMagPhaseBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Multiple images sets of (2 magnitude, 2 phase) field map acquisitions found in section. Only selecting most recent set. Other(s) will not be included in the BIDS output']
                        });
                    }

                    // Remove all magnitudes & fieldmaps except for last 2
                    if (fmapMagFieldmapObjs.length > 2) {
                        let fmapMagFieldmapBadObjs = fmapMagFieldmapObjs.slice(0,-2)
                        fmapMagFieldmapBadObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Multiple image sets of magnitude & fieldmap field map acquistions found in section. Only selecting most recent pair. Other(s) will not be included in BIDS output']
                        });
                    }

                    // Remove all magnitudes & fieldmaps if less than 2
                    if (fmapMagFieldmapObjs.length < 2) {
                        fmapMagFieldmapObjs.forEach(obj=> {
                            obj.exclude = true
                            obj.analysisResults.errors = ['Need pair (magnitude & fieldmap). This acquisition will not be included in BIDS output']
                        });
                    }

                } else {
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
                if (dwiObjs.length == 0 && fmapSpinEchoDwiObjs.length > 0) {
                    fmapSpinEchoDwiObjs.forEach(obj=> {
                        obj.exclude = true
                        obj.analysisResults.errors = ['No valid dwi/dwi acquisitions found in section, spin echo field map will not be included in the BIDS output']
                    });
                }

                // Remove fmap meant for dwi/dwi if more than 1 fmap
                if (fmapSpinEchoDwiObjs.length > 1) {
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

    //for (const subject in $root._organized) {
    $root._organized.forEach(subGroup=>{

        // Loop through sessions
        //const sessions = subGroup.sess
        //for (const session in sessions) {
        subGroup.sess.forEach(sesGroup=>{
            // Determine series_idx values
            let allSeriesIndices = sesGroup.objects.map(e=>e.series_idx)
            let uniqueSeriesIndices = Array.from(new Set(allSeriesIndices))

            uniqueSeriesIndices.forEach(si=>{
                let seriesObjects = sesGroup.objects.filter(e=>e.series_idx == si && !e._exclude)
                let run = 1
                if (seriesObjects.length > 1) {
                    seriesObjects.forEach(obj=>{
                        obj.entities.run = run.toString()
                        run++
                    });
                }
            });
        });
    });
}

export function updateErrors($root) {
    // Series that have been un-excluded at Series mapping have warning/error messages
    // that need to be removed, since user is aware and wants the acquisition(s) anyway,
    // or the identification was incorrect to begin with

    //for (const subject in $root._organized) {
    $root._organized.forEach(subGroup=>{
        //const sessions = $root._organized[subject].sess
        //for (const session in sessions) {
        subGroup.sess.forEach(sesGroup=>{
            sesGroup.objects.filter(o=>!o.exclude).forEach(obj=>{
                obj.analysisResults.errors = []
            });
        });
    });
}

export function setIntendedFor($root) {
    // Apply fmap intendedFor mapping

    // Loop through subjects
    //for (const subject in $root._organized) {
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

export function deepEqual(object1, object2) {
    /*
    Function comes from https://dmitripavlutin.com/how-to-compare-objects-in-javascript/#4-deep-equality

    Determines whether two arrays are identical or not.
    */
    const keys1 = Object.keys(object1);
    const keys2 = Object.keys(object2);
    if(keys1.length !== keys2.length) {
      return false;
    }
    for(const key of keys1) {
        const val1 = object1[key];
        const val2 = object2[key];
        const areObjects = isObject(val1) && isObject(val2);
        if(areObjects && !deepEqual(val1, val2) || !areObjects && val1 !== val2) {
            return false;
        }
    }
    return true;
}

export function isObject(object) {
    /*
    Function comes from https://dmitripavlutin.com/how-to-compare-objects-in-javascript/#4-deep-equality

    This function determines whether or not something is an object.
    */
    return object != null && typeof object === 'object';
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


//TODO - update this to return {errors: [], warnings: []} 
export function validateSeries(s, ezbids) {
    /*
    Series items with unique series_id values may still contain the same DateType, suffix, and
    entities. This is a problem if uncorrected, because there will then be conflict(s) during
    Objects mapping. A validation error will therefore be generated if the conditions above are
    met.
    */

    s.validationWarnings.push("exmple error...");

    /*

    let seriesItemsList = [] //contains series info (type, entities) from all series
    let duplicateSeriesInfoList = [] //contains series info if it appears more than once in seriesItemsList

    $root.series.forEach(s=>{
        let info = {"type": s.type, "entities": s.entities}
        seriesItemsList.push(info)
    });

    let seriesItemsList_indices = Array.from(Array(seriesItemsList.length).keys())

    // Go through each series info pairing option to check for matches
    for(const [ser_idx, element] of seriesItemsList.entries()) {
        let remaining_indices = seriesItemsList_indices.filter(i=> i !== ser_idx)

        for(const remain_idx in remaining_indices) {
            if(ser_idx != remain_idx) {
                if(deepEqual(seriesItemsList[ser_idx], seriesItemsList[remain_idx]) == true && !duplicateSeriesInfoList.includes(JSON.stringify(seriesItemsList[ser_idx]))) {
                    duplicateSeriesInfoList.push(JSON.stringify(seriesItemsList[ser_idx]))
                }
            }
        }
    }
    // Convert JSON string back to JS object(s)
    for(const [dup_idx, value] of duplicateSeriesInfoList.entries()) {
        duplicateSeriesInfoList[dup_idx] = JSON.parse(duplicateSeriesInfoList[dup_idx])
    }

    return duplicateSeriesInfoList
    */
}


export function find_separator(filePath, fileData) {
	if (filePath.indexOf('.tsv') > -1) {
		return /[ \t]+/;
	} else if (filePath.indexOf('.out') > -1 || filePath.indexOf('.csv') > -1)  {
		return /[ ,]+/;
	} else if (filePath.indexOf('.txt') > -1) {
		const data = fileData
		const lines = data.trim().split("\n").map(l=>l.trim());
		if (lines[0].indexOf(',') > -1) {
			return /[ ,]+/;
		} else {
			return /[ \t]+/;
		}
	} else if (filePath.indexOf('.xlsx') > -1) {
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

//this function receives files (an array of object containing fullpath and data. data is the actual file content of the file)
export function createEventObjects(ezbids, files) {
    const eventObjects = []; //new event objects to add

    // Identify some terms for decoding purposes
    const subjects = Array.from(new Set(ezbids.subjects.filter(e=>e.exclude == false).map(e=>e.subject)))
    const sessions = Array.from(new Set(ezbids.subjects.map(e=>e.sessions)[0].filter(e=>e.exclude == false).map(e=>e.session)))
    const tasks = Array.from(new Set(ezbids.objects.map(e=>e._entities).filter(e=>(e.part == "" || e.part == "mag") && (e.task != "" && e.task != "rest" && e.task !== undefined)).map(e=>e.task)))
    const runs = Array.from(new Set(ezbids.objects.filter(e=>e._entities.task != "" && e._entities.task != "rest" && e._entities.task != undefined).map(e=>e._entities.run)))
    const numEventFiles = files.length
    const uniqueSectionIDs = Array.from(new Set(ezbids.objects.map(e=>e.analysisResults.section_ID)))

    // Try to determine inheritance level (dataset, subject, session, or individual runs)
    const occurrences = {"Dataset": 1, "Subject": subjects.length, "Session": sessions.length, "Run": runs.length}
    const closest = Object.values(occurrences).reduce(function(prev, curr) {
        return Math.abs(curr - numEventFiles) < Math.abs(prev - numEventFiles) ? curr : prev
    });

    /*
    Chance that multiple occurrences values could be the same, therefore, default to lowest level.
    Assumption is that the lower the level, the more common it is.
    */
    const inheritance_level = Object.keys(occurrences).filter(key=>occurrences[key] == closest).slice(-1)[0]

    const regEscape = v=>v.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&')

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
            // let data = XLSX.readFile(file.path)
            events = parseExcelEvents(file.data)
            break;
        default: // Non-Excel formats
            const data = file.data
            const lines = data.trim().split("\n").map(l=>l.trim());
            if (lines[0].indexOf('Header Start') > -1) {
                // E-prime file format
                events = parseEprimeEvents(file.data)
            } else {
                // "Regular" file format (.csv .tsv .txt .out)
                const sep = find_separator(file.path, file.data) // Read events file(s) data
                events = parseEvents(file.data, sep);
            }
        }

        const eventsMappingInfo =   {
            subject: {
                MappingKeys: [
                    "sub", "subid", "subname",
                    "subj", "subjid", "subjname",
                    "subject", "subjectid", "subjectname",
                    "participant", "participantid", "participantname"
                ],
                ezBIDSvalues: subjects,
                eventsValue: null,
                detectionMethod: null,
            },
            session: {
                MappingKeys: [
                    "ses", "sesid", "sesname",
                    "sess", "sessid", "sessname",
                    "session", "sessionid", "sessionname"
                ],
                ezBIDSvalues: sessions,
                eventsValue: null,
                detectionMethod: null,
            },
            task: {
                MappingKeys: [
                    "exp", "expid", "expname",
                    "task", "taskid", "taskname",
                    "experiment", "experimentid", "experimentname"
                ],
                ezBIDSvalues: tasks,
                eventsValue: null,
                detectionMethod: null,
            },
            run: {
                MappingKeys: ["run", "runid", "runname"],
                ezBIDSvalues: runs,
                eventsValue: null,
                detectionMethod: null,
            }
        }

        const keys = Object.keys(events[0]); //picking the first object as a sample
        for(const entity in eventsMappingInfo) {
            const info = eventsMappingInfo[entity];

            // 1st stage: examine header columns and data of event file(s) to
            // see if helpful information is contained there
            const matchingKey = keys.find(key=>{
                const safeKey = key.toLowerCase().replace(/[^0-9a-z]/gi, '');
                info.MappingKeys.includes(safeKey);
            });
            if(matchingKey) {
                const matchingValues = events.map(e=>e[matchingKey]);
                info.eventsValue = findMostCommonValue(matchingValues);
                info.detectionMethod = "column name match";
            }

            // 2nd stage: examine file path for helpful information
            if (info.eventsValue == undefined) {
                Object.values(info.MappingKeys).forEach(mapping=>{
                    if (file.path.toLowerCase().split(mapping).slice(-1)[0].split(/[._-]+/)[0] == "") {
                        info.eventsValue = file.path.split(new RegExp(regEscape(mapping), "ig")).slice(-1)[0].split(/[._-]+/)[1]
                        info.detectionMethod = 2
                    } else if (isNaN(parseFloat(file.path.toLowerCase().split(mapping).slice(-1)[0])) == false) {
                        info.eventsValue = file.path.split(new RegExp(regEscape(mapping), "ig")).slice(-1)[0].split(/[._-]+/)[0]
                        info.detectionMethod = 2
                    }
                });
            }

            // 3rd stage: if ezBIDSvalues lengths == 1, set those values to the corresponding eventsValue
            if (info.eventsValue == undefined && info.ezBIDSvalues.length == 1) {
                info.eventsValue = info.ezBIDSvalues[0]
                info.detectionMethod = 3
            }

            //Sanity checks
            Object.keys(eventsMappingInfo).forEach(key=>{
                /* 1). if a mismatch exists between any key's ezBIDSvalue and eventsValue, and the length of
                ezBIDSvalues == 1, then the ezBIDSvalue takes precedence because that's what the user has explicitly specified
                on ezBIDS.
                */
                if (!info.ezBIDSvalues.includes(info.eventsValue) && info.ezBIDSvalues.length == 1) {
                    info.eventsValue = info.ezBIDSvalues[0]
                }

                //2). ignore zero-padding in subject, session, and run eventsValue if the zero-padded value doesn't exist in corresponding ezBIDSvalues
                if (key != "task" && info.eventsValue) {
                    if (!info.ezBIDSvalues.includes(info.eventsValue) && info.ezBIDSvalues.includes(info.eventsValue.replace(/^0+/, ''))) {
                        info.eventsValue = info.eventsValue.replace(/^0+/, '')
                    }
                }
            })
        }

        //if we couldn't find task eventValue, look for task names used in ezbids in event files valued (not just column name)
        if (!eventsMappingInfo.task.eventsValue) {
            const taskNames = eventsMappingInfo.task.ezBIDSvalues.map(v=>v.toLowerCase());
            events.forEach(event=>{
                for(const key in event) {
                    if(taskNames.includes(event[key])) {
                        eventsMappingInfo.task.eventsValue = event[key];
                        info.detectionMethod = "found a column that contains ezbids task name"
                    }
                }
            });
        }

        // Determine section_ID that events object pertains to
        let section_ID;
        if (uniqueSectionIDs.length == 1) {
            section_ID = uniqueSectionIDs[0]
        } else { // multiple section_IDs; should be able to determine which func/bold the event goes to and use that section_ID
            const correspondingBoldSecID = ezbids.objects.filter(e=>e._entities.subject == eventsMappingInfo.subject.eventsValue &&
                e._entities.session == eventsMappingInfo.session.eventsValue &&
                e._entities.task == eventsMappingInfo.task.eventsValue &&
                e._entities.run == eventsMappingInfo.run.eventsValue
                ).map(e=>e.analysisResults.section_ID)

            if (correspondingBoldSecID.length > 0) {
                section_ID = correspondingBoldSecID[0]
            } else {
                section_ID = 1
            }
        }

        // Determine correspoding series_idx value that event file(s) go to
        const series_idx = Array.from(new Set(ezbids.objects.filter(e=>e._entities.subject == eventsMappingInfo.subject.eventsValue &&
            e._entities.session == eventsMappingInfo.session.eventsValue &&
            e._entities.task == eventsMappingInfo.task.eventsValue &&
            e._entities.run == eventsMappingInfo.run.eventsValue &&
            (e._entities.part == "" || e._entities.part == "mag")
            ).map(e=>e.series_idx)))

        const subjectInfo = ezbids.subjects.filter(e=>e.subject == eventsMappingInfo.subject.eventsValue)
        let sessionInfo;

        sessionInfo = subjectInfo[0].sessions.filter(e=>e.session == eventsMappingInfo.subject.eventsValue)
        if (sessionInfo.length == 0) {
            sessionInfo = subjectInfo[0].sessions.filter(e=>e.session == "")
        }

        // Indexing the first (any only value) but will need to filter this out better for multi-session data
        const subject = subjectInfo[0];
        const session = sessionInfo[0];
        const patientInfo = subject.PatientInfo[0];

        //register new event object using the info we gathered above
        const object = Object.assign({
            type: "func/events",
            //series_idx: null,
            subject_idx: ezbids.subjects.indexOf(subject),
            session_idx: subject.sessions.indexOf(session),

            entities: {
                "subject": eventsMappingInfo.subject.eventsValue,
                "session": eventsMappingInfo.session.eventsValue,
                "task": eventsMappingInfo.task.eventsValue,
                "run": eventsMappingInfo.run.eventsValue
            },
            "items": [],
            //these aren't used, but I believe we have to initialize it
            "analysisResults": {
                "section_ID": section_ID //TODO we do need to set this so that this event object goes to the right section
            },
            "paths": [],
            "validationErrors": [],
        }, patientInfo, session); //we need to set subject / session specific fields that we figured out earlier

        //event object also need some item info!
        object.items.push({
            "name": fileExt,
            events, //here goes the content of the event object parsed earlier
            "path": file.path //let's use the original file.path as "path" - although it's not..
        });

        const sidecar = {};

        object.items.push({
            "name": "json",
            sidecar,
            sidecar_json: JSON.stringify(sidecar),
        });

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
