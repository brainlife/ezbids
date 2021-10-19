// @ts-nocheck

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

//this function receives files (an array of object containing fullpath and data. data is the actual file content of the file)
//to filter out files by file extensions, please edit Events.vue
export function createEventObjects(ezbids, files) {
    /* example for ezbids
    {
        datasetDescription: {
            Name: "Untitled",                                                                                     
            BIDSVersion: "1.4.0",                                                                                 
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

    files.forEach(file=>{
        
        //TODO - for each files, parse the content according to the file type, 
        const fileExt = file.path.split(".").pop();
        console.log("event file detected", file.path, fileExt);

        //TODO convert parsed object into an array of json dictionary
        const events = [];
        switch(fileExt) {
        case "tsv":
            events.push({header1: 1, header2: 2, header3: 3});    
            break;
        default:
            //TODO..
            events.push({header1: "h1-value1", header2: "h2-value2", header3: "h3-value3"});    
            events.push({header1: "h1-value2", header2: "h2-value2", header3: "h3-value3"});
            events.push({header1: "h2-value3", header2: "h2-value2", header3: "h3-value3"});
        }
        
        //TODO - for each file, find the most likely subject/session/task using the number of files (to guess if they are session/run specific)
        //as well as path / data 
        /*
        const subject = {
            "PatientName": "OpenSciJan22",
            "PatientID": "10462@thwjames/OpenScience",
            "PatientBirthDate": "19910101",
        }
        */
        
        //just pick a subject/session rarndomly for this sample
        const subject = ezbids.subjects[0].PatientInfo[0];
        //console.log("subject chosen");
        //console.dir(subject);

        const session =  ezbids.subjects[0].sessions[0];
        //console.log("session chosen");
        //console.dir(session);

        //register new event object using the info we gathered above
        const object = Object.assign({
            //"series_idx": 5, //DO I need to create a series to store this object?\
            type: "func/events",
            series_idx: null,

            entities: {
              "task": "smt", //task is the only required entity
            },
            "items": [
            ],

            //these aren't used, but I believe we have to initialize it
            "analysisResults": {
                section_ID: 1, //TODO we do need to set this so that this event object goes to the right section
            },
            "paths": [],
            "validationErrors": [],
        }, subject, session); //we need to set subject / session specific fields that we figured out earlier

        //event object also need some item info!
        object.items.push({
            "name": "tsv",
            events, //here goes the content of the event object parsed earlier
            "path": file.path, //let's use the original file path as "path" - although it's not..
        });

        const sidecar = {};

        object.items.push({
            "name": "json",
            sidecar,
            sidecar_json: JSON.stringify(sidecar),
        });

        eventObjects.push(object);
    });

    //console.log("created objects");
    //console.dir(eventObjects);
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
       onsetUnit: "cm",

   }
}


