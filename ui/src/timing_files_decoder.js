#!/usr/bin/env node
const fs = require('fs');
const path = require('path')
// var XLSX = require('xlsx');
// const study = '' // Need to get this value from ezBIDS UI
const $rootDir = '' // Need to get value from ezBIDS UI


function find_separator(filePath) {
	if (filePath.indexOf('.tsv') > -1) {
		var separator = /[ \t]+/;
	} else if (filePath.indexOf('.out') > -1 || filePath.indexOf('.csv') > -1)  {
		var separator = /[ ,]+/;
	} else if (filePath.indexOf('.txt') > -1) {
		const data = fs.readFileSync(filePath, "utf8")
		const lines = data.trim().split("\n").map(l=>l.trim());
		if (lines[0].indexOf(',') > -1) {
			var separator = /[ ,]+/;
		} else {
			var separator = /[ \t]+/;
		}
	} else if (filePath.indexOf('.xlsx') > -1) {
		var separator = /[ ,]+/;
	}

	return separator;
}

function parseEprimeTimingFiles(data, cb) {
	const lines = data.trim().split(/\r|\n/).map(l=>l.trim());

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

function parseTimingFiles(data, sep, cb) {
    const lines = data.trim().split(/\r|\n/).map(l=>l.trim().replace(/['"]+/g, ''));
    const trials = [];
    var headers = lines.shift().split(sep);
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

function parseExcelWorkbookTimingFiles (data) {
	// Code from https://stackoverflow.com/questions/30859901/parse-xlsx-with-node-and-create-json
	var workbook = data;
	var sheet_name_list = workbook.SheetNames;
	var trials = []
	sheet_name_list.forEach(function(y) {
	    var worksheet = workbook.Sheets[y];
	    var headers = {};
	    var data = [];
	    for(z in worksheet) {
	        if(z[0] === '!') continue;
	        //parse out the column, row, and value
	        var col = z.substring(0,1);
	        var row = parseInt(z.substring(1));
	        var value = worksheet[z].v;

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

// const ezbids = require('/media/data/ezbids/fMRI_behavioral_timing_files/OpenScience/root.json')
const ezbids = require('/media/data/ezbids/fMRI_behavioral_timing_files/WML/root.json')
// const ezbids = require('/media/data/ezbids/fMRI_behavioral_timing_files/R01_HighSchool/root.json')
// const files = require('/media/data/ezbids/fMRI_behavioral_timing_files/OpenScience/files_path.json')
const files = require('/media/data/ezbids/fMRI_behavioral_timing_files/WML/files_path.json')
// const files = require('/media/data/ezbids/fMRI_behavioral_timing_files/R01_HighSchool/files_path.json')


//this function receives files (an array of object containing fullpath and data. data is the actual file content of the file)
//to filter out files by file extensions, please edit Events.vue
function createEventObjects(ezbids, files) {
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

    // Determine number of subjects, sessions, event tasks (i.e. no rest), and event files
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
        // console.log("event file detected:", file.path);

        // Parse the data, depending on the file extension (and header information)
        switch(fileExt) {
        // Excel workbook formats (.xlsx, .xlsm, .xls)
        case "xlsx":
        case "xlsm":
        case "xls":
            var data = XLSX.readFile(file.path)
            var events = parseExcelWorkbookTimingFiles(data)
            break;
        default: // Non-Excel formats
            var data = fs.readFileSync(file.path, "utf8")
            var lines = data.trim().split("\n").map(l=>l.trim());
            if (lines[0].indexOf('Header Start') > -1) {
                // E-prime file format
                var events = parseEprimeTimingFiles(data)
            } else {
                // "Regular" file format (.csv .tsv .txt .out)
                var sep = find_separator(file.path) // Read events file(s) data
                var events = parseTimingFiles(data, sep);
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


        var modifiedFilePath = file.path

        Object.keys(eventsMappingInfo).forEach(key=>{
            // 1st stage: examine header columns and data of event file(s) to see if helpful information is contained there
            const match = Object.keys(events[0]).map(item=>item.toLowerCase().replace(/[^0-9a-z]/gi, '')).filter(item=>eventsMappingInfo[key]["MappingKeys"].includes(item))[0]
            const value = mode(events.map(e=>e[match]))
            eventsMappingInfo[key]["eventsValue"] = value
            eventsMappingInfo[key]["detectionMethod"] = 1
            if (eventsMappingInfo["task"]["eventsValue"] == undefined) { // Look for task information in events file(s); other information too difficult to discern here
                eventsMappingInfo["task"]["ezBIDSvalues"].forEach(taskItem=>{
                    Object.values(mode(events)).forEach(eventsItem=>{
                        if (eventsItem.toLowerCase().includes(taskItem.toLowerCase())) {
                            eventsMappingInfo["task"]["eventsValue"] = taskItem
                            eventsMappingInfo[key]["detectionMethod"] = 1
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
            if (eventsMappingInfo[key]["eventsValue"] == undefined) {
                Object.values(eventsMappingInfo[key]["MappingKeys"]).forEach(mapping=>{
                    if (file.path.toLowerCase().split(mapping).slice(-1)[0].split(/[._-]+/)[0] == "") {
                        eventsMappingInfo[key]["eventsValue"] = file.path.split(new RegExp(regEscape(mapping), "ig")).slice(-1)[0].split(/[._-]+/)[1]
                        eventsMappingInfo[key]["detectionMethod"] = 2
                    } else if (isNaN(parseFloat(file.path.toLowerCase().split(mapping).slice(-1)[0])) == false) {
                        eventsMappingInfo[key]["eventsValue"] = file.path.split(new RegExp(regEscape(mapping), "ig")).slice(-1)[0].split(/[._-]+/)[0]
                        eventsMappingInfo[key]["detectionMethod"] = 2
                    }
                });
            }

            // 3rd stage: if ezBIDSvalues lengths == 1, set those values to the corresponding eventsValue
            if (eventsMappingInfo[key]["eventsValue"] == undefined && eventsMappingInfo[key]["ezBIDSvalues"].length == 1) {
                eventsMappingInfo[key]["eventsValue"] = eventsMappingInfo[key]["ezBIDSvalues"][0]
                eventsMappingInfo[key]["detectionMethod"] = 3
            }
        });

        // console.log(file.path)
        // console.log(eventsMappingInfo)

        // Determine section_ID that events object pertains to
        if (uniqueSectionIDs.length == 1) {
            section_ID = uniqueSectionIDs[0]
        } else { // multiple section_IDs; should be able to determine which func/bold the event goes to and use that section_ID
            section_ID = ""

        }

        // Determine correspoding series_idx value that event file(s) go to
        const series_idx = Array.from(new Set(ezbids.objects.filter(e=>e._entities.subject == eventsMappingInfo["subject"]["eventsValue"] &&
                                                                    e._entities.session == eventsMappingInfo["session"]["eventsValue"] &&
                                                                    e._entities.task == eventsMappingInfo["task"]["eventsValue"] &&
                                                                    e._entities.run == eventsMappingInfo["run"]["eventsValue"] &&
                                                                    (e._entities.part == "" || e._entities.part == "mag")
                                                                    ).map(e=>e.series_idx)))

        if (series_idx.length == 1) {
            var corr_series_idx = parseInt(series_idx[0]) + 0.5
        } else {
            var corr_series_idx = undefined
        }



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

        
        const subject = eventsMappingInfo["subject"]["eventsValue"]
        const session = eventsMappingInfo["session"]["eventsValue"]


        //register new event object using the info we gathered above
        const object = Object.assign({
            type: "func/events",
            series_idx: corr_series_idx, // Make func/event series_idx be 0.5 above corresponding func/bold series_idx

            entities: {
                "subject": eventsMappingInfo["subject"]["eventsValue"],
                "session": eventsMappingInfo["session"]["eventsValue"],
                "task": eventsMappingInfo["task"]["eventsValue"],
                "run": eventsMappingInfo["run"]["eventsValue"]
            },
            "items": [],
            //these aren't used, but I believe we have to initialize it
            "analysisResults": {
                section_ID: section_ID, //TODO we do need to set this so that this event object goes to the right section
            },
            "paths": [],
            "validationErrors": [],
        }, '50', '1'); //we need to set subject / session specific fields that we figured out earlier

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

const output = createEventObjects(ezbids, files)

console.log(output)