// @ts-nocheck

export function doStuff($root, param) {
    //do XYZ.. return 123...

    console.log($root);
    conosle.log(params);
}

export function funcQA($root) {
    // Exclude functional bold acquisitions have less than 50 volumes,
    // which are probably a restart or failure functional acquisition occurrence.

    // Loop through all acquisition objects
    for (const obj in $root.objects) {
        if (!obj._exclude && obj._type == 'func/bold' && obj.analysisResults.NumVolumes < 50) {
            obj.exclude = true
            obj.analysisResults.errors = ['Functional acquisition contains less than 50 volumes, a possible indiciation of a failed/restarted run. Please check to see if you want to keep this, otherwise, this acquisitions will be excluded from BIDS conversion']
        }
    }
}

export function fmapQA($root) {
    // Assesses fieldmaps for improper PEDs (for spin-echo field maps),
    // and excludes extra fieldmaps in section

    // Loop through subjects
    for (const subject in $root._organized) {
        
        // Loop through sessions
        const sessions = $root._organized[subject].sess
        for (const session in sessions) {

            // Determine unique sectionIDs
            let allSectionIDs = sessions[session].objects.map(e=>e.analysisResults.section_ID)
            let sectionIDs = Array.from(new Set(allSectionIDs))

            // Loop through sections (no excluded acquisitions included)
            sectionIDs.forEach(s=> {
                let section = sessions[session].objects.filter(e=>e.analysisResults.section_ID == s && !e._exclude)

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
        }
    }     
}


export function setRun($root) {
    // Set run label if not already specified at Series level

    // Loop through subjects
    for (const subject in $root._organized) {
        
        // Loop through sessions
        const sessions = $root._organized[subject].sess
        for (const session in sessions) {
            // Determine series_idx values
            let allSeriesIndices = sessions[session].objects.map(e=>e.series_idx)
            let uniqueSeriesIndices = Array.from(new Set(allSeriesIndices))

            uniqueSeriesIndices.forEach(si=>{
                let seriesObjects = sessions[session].objects.filter(e=>e.series_idx == si && !e._exclude)
                let run = 1
                if (seriesObjects.length > 1) {
                    seriesObjects.forEach(obj=>{
                        obj.entities.run = run.toString()
                        run = run + 1
                    });
                }
            });
        }
    }
}

export function updateErrors($root) {
    // Series that have been un-excluded at Series mapping have warning/error messages
    // that need to be removed, since user is aware and wants the acquisition(s) anyway,
    // or the identification was incorrect to begin with

    for (const subject in $root._organized) {
        
        const sessions = $root._organized[subject].sess
        for (const session in sessions) {

            let allObjects = sessions[session].objects

            allObjects.forEach(obj=>{
                if (!obj.exclude) {
                    obj.analysisResults.errors = []
                }
            });
        }
    }
}

export function setIntendedFor($root) {
    // Apply fmap intendedFor mapping

    // Loop through subjects
    for (const subject in $root._organized) {

        // Loop through sessions
        const sessions = $root._organized[subject].sess
        for (const session in sessions) {

            // Determine unique sectionIDs
            let allSectionIDs = sessions[session].objects.map(e=>e.analysisResults.section_ID)
            let sectionIDs = Array.from(new Set(allSectionIDs))

            // Loop through sections (no excluded acquisitions included)
            sectionIDs.forEach(s=> {
                let section = sessions[session].objects.filter(e=>e.analysisResults.section_ID == s && !e._exclude)

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
        }
    }
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

function parseEvents(fileData, sep, cb) {
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

function mode(arr){
    return arr.sort((a,b) =>
          arr.filter(v => v===a).length
        - arr.filter(v => v===b).length
    ).pop();
}


//this function receives files (an array of object containing fullpath and data. data is the actual file content of the file)
export function createEventObjects(ezbids, files) {

    //console.log("dumping input parameters to build a test case");
    //console.dir(JSON.stringify({ezbids,files}, null, 4));

    /* example for ezbids
    {
        datasetDescription: {
            Name: "Untitled",                                                                                     
            BIDSVersion: "1.6.0",                                                                                 
            DatasetType: "raw",                                                                                   
            License: "",                                                                                       
            Authors: [],                                                                                                      
            Acknowledgements: "", 
            HowToAcknowledge: "", 
            Funding: [],                                                                                                      
            EthicsApprovals: [],                                                                                                      
            ReferencesAndLinks: [],                                                                                                      
            DatasetDOI: "",  
        },
        readme: "edit me",                                                                                          
        participantsColumn: {}, 

        //here lives various things
        subjects: [],                                                                                               
        series: [],                                                                                                 
        objects: [],                                                                                                

        _organized: {}, //above things are organized into subs/ses/run/object hierarchy for quick access
    }
    */

    /* example for files
    [
        {path: "/some/event1.tsv", data: "...content of the tsv..."},
        {path: "/some/event2.tsv", data: "...content of the tsv..."},
        {path: "/some/sub/event3.tsv", data: "...content of the tsv..."},
    ]
    */

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
        console.log("event file detected:", file.path);
        
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

        // Determine mapping of event file(s) to subject,session,task,run
        const subMappingKeys = ["sub", "subid", "subname", "subj", "subjid", "subjname", "subject", "subjectid", "subjectname", "participant", "participantid", "participantname"]
        const sesMappingKeys = ["ses", "sesid", "sesname", "sess", "sessid", "sessname", "session", "sessionid", "sessionname"]
        const taskMappingKeys = ["exp", "expid", "expname", "task", "taskid", "taskname", "experiment", "experimentid", "experimentname"]
        const runMappingKeys = ["run", "runid", "runname"]

        const eventsMappingInfo =   {   
                                        "subject": {"MappingKeys": subMappingKeys, "ezBIDSvalues": subjects, "eventsValue": "", "detectionMethod": ""},
                                        "session": {"MappingKeys": sesMappingKeys, "ezBIDSvalues": sessions, "eventsValue": "", "detectionMethod": ""},
                                        "task": {"MappingKeys": taskMappingKeys, "ezBIDSvalues": tasks, "eventsValue": "", "detectionMethod": ""},
                                        "run": {"MappingKeys": runMappingKeys, "ezBIDSvalues": runs, "eventsValue": "", "detectionMethod": ""}
                                    }


        let modifiedFilePath = file.path

        Object.keys(eventsMappingInfo).forEach(key=>{
            // 1st stage: examine header columns and data of event file(s) to see if helpful information is contained there
            const match = Object.keys(events[0]).map(item=>item.toLowerCase().replace(/[^0-9a-z]/gi, '')).filter(item=>eventsMappingInfo[key].MappingKeys.includes(item))[0]
            const value = mode(events.map(e=>e[match]))
            eventsMappingInfo[key].eventsValue = value
            eventsMappingInfo[key].detectionMethod = 1
            if (eventsMappingInfo.task.eventsValue == undefined) { // Look for task information in events file(s); other information too difficult to discern here
                eventsMappingInfo.task.ezBIDSvalues.forEach(taskItem=>{
                    Object.values(mode(events)).forEach(eventsItem=>{
                        if (eventsItem.toLowerCase().includes(taskItem.toLowerCase())) {
                            eventsMappingInfo.task.eventsValue = taskItem
                            eventsMappingInfo[key].detectionMethod = 1
                        }
                    });
                });
            }

            // 2nd stage: examine file path for helpful information

            // if (eventsMappingInfo[key]["eventsValue"] == undefined) {
            //     Object.values(eventsMappingInfo[key]["ezBIDSvalues"]).forEach(value=>{
            //         if (value.length > 2 && modifiedFilePath.toLowerCase().replace(/[^0-9a-z]/gi, '').includes(value)) {
            //             modifiedFilePath = modifiedFilePath.replace(value, "")
            //             if (eventsMappingInfo[key]["eventsValue"] == undefined) {
            //                 eventsMappingInfo[key]["eventsValue"] = value
            //             }
            //         }
            //     });
            // }
            if (eventsMappingInfo[key].eventsValue == undefined) {
                Object.values(eventsMappingInfo[key].MappingKeys).forEach(mapping=>{
                    if (file.path.toLowerCase().split(mapping).slice(-1)[0].split(/[._-]+/)[0] == "") {
                        eventsMappingInfo[key].eventsValue = file.path.split(new RegExp(regEscape(mapping), "ig")).slice(-1)[0].split(/[._-]+/)[1]
                        eventsMappingInfo[key].detectionMethod = 2
                    } else if (isNaN(parseFloat(file.path.toLowerCase().split(mapping).slice(-1)[0])) == false) {
                        eventsMappingInfo[key].eventsValue = file.path.split(new RegExp(regEscape(mapping), "ig")).slice(-1)[0].split(/[._-]+/)[0]
                        eventsMappingInfo[key].detectionMethod = 2
                    }
                });
            }

            // 3rd stage: if ezBIDSvalues lengths == 1, set those values to the corresponding eventsValue
            if (eventsMappingInfo[key].eventsValue == undefined && eventsMappingInfo[key].ezBIDSvalues.length == 1) {
                eventsMappingInfo[key].eventsValue = eventsMappingInfo[key].ezBIDSvalues[0]
                eventsMappingInfo[key].detectionMethod = 3
            }
        });

        let section_ID;
        // Determine section_ID that events object pertains to
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

        // switch(inheritance_level) {
        // case "Dataset":
        //     // Do nothing
        //     break;
        // case "Subject":
        //     console.log('do nothing')
        //     break;
        // case "Session":
        //     console.log('do nothing')
        //     break;
        // case "Run":
        //     console.log('do nothing')
        //     break;

        // }


        const subjectInfo = ezbids.subjects.filter(e=>e.subject == eventsMappingInfo.subject.eventsValue)
        let sessionInfo;
        sessionInfo = subjectInfo[0].sessions.filter(e=>e.session == eventsMappingInfo.subject.eventsValue)
        if (sessionInfo.length == 0) {
            sessionInfo = subjectInfo[0].sessions.filter(e=>e.session == "")
        }

        // Indexing the first (any only value) but will need to filter this out better for multi-session data
        const subject = subjectInfo[0].PatientInfo[0]
        const session = sessionInfo[0]


        //register new event object using the info we gathered above
        const object = Object.assign({
            type: "func/events",
            series_idx: null, // Make func/event series_idx be 0.5 above corresponding func/bold series_idx

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
        }, subject, session); //we need to set subject / session specific fields that we figured out earlier

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


//this function receives one example event object. we will do our best to map the event keys (columns) and 
//map them to bids events.tsv column names
export function mapEventColumns(events) {
    /*
    input events object may look like this
    [
        {header1: "value1", header2: "value2", header3: "value3"},
        {header1: "value1", header2: "value2", header3: "value3"},
        {header1: "value1", header2: "value2", header3: "value3"},
    ]
    */
   
    //TODO - return a mapping object that sets various bids events.json column name with the name of the columns from the events inputs
    //you can also set Units (if we know)
    /*
    return {
        onset: "header1", 
        onsetUnit: "mm", 
        
        duration: "header2",
        durationUnit: "mm",

        sample: "header3",

        trialType: null,

        responseTime: null,
        responseTimeUnit: "mm",

        value: null,

        HEAD: null,
    }
    */

    //we only have to return things that we found out.. (leave other things not set)
    return {
       onset: "header1",
       onsetUnit: "sec",

       duration: "header2",
       durationUnit: "sec",

       sample: "header3",
       sampleUnit: "samples",

       trial_type: null,

       response_time: null,
       response_timeUnit: "sec",

       values: null,

       HED: null
    }
}
