#!/usr/bin/env node
const fs = require('fs');
const path = require('path')
var XLSX = require('xlsx');
const study = '' // Need to get this value from ezBIDS UI
const $rootDir = '' // Need to get value from ezBIDS UI

const findTimingFiles = function (rootDir, timingFiles) {
	// inspired by https://coderrocketfuel.com/article/recursively-list-all-the-files-in-a-directory-using-node-js
	files = fs.readdirSync(rootDir)

	timingFiles = timingFiles || []

	  files.forEach(function(file) {
	    if (fs.statSync(rootDir + "/" + file).isDirectory()) {
	      timingFiles = findTimingFiles(rootDir + "/" + file, timingFiles)
	    } else {
	    	file = path.join(rootDir, "/", file)
	    	// Only accept certain file extensions
	    	if (file.indexOf('.out') > -1 ||
	    		file.indexOf('.txt') > -1 ||
	    		file.indexOf('.csv') > -1 ||
	    		file.indexOf('.tsv') > -1 ||
	    		file.indexOf('.xlsx') > -1 ||
	    		file.indexOf('.xlsm') > -1 ||
	    		file.indexOf('.xlsb') > -1 ||
	    		file.indexOf('.xlm') > -1) {

	    		timingFiles.push(file)
	    	}
	    }
	});
  return timingFiles
}


function find_separator(FileName) {
	if(FileName.indexOf('.tsv') > -1) {
		var separator = /[ \t]+/;
	} else if (FileName.indexOf('.out') > -1 || FileName.indexOf('.csv') > -1)  {
		var separator = /[ ,]+/;
	} else if (FileName.indexOf('.txt') > -1) {
		const data = fs.readFileSync(FileName, "utf8")
		const lines = data.trim().split("\n").map(l=>l.trim());
		if (lines[0].indexOf(',') > -1) {
			var separator = /[ ,]+/;
		} else {
			var separator = /[ \t]+/;
		}
	} else if (FileName.indexOf('.xlsx') > -1) {
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
    const headers = lines.shift().split(sep);
    const timing_info = []

    lines.forEach(line=>{
        const tokens = line.split(sep);
        const block = {};
        for(let i = 0;i < tokens.length; ++i) {
            const k = headers[i].toLowerCase();
            const v = tokens[i];
            block[k] = v;
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

var timingFiles = findTimingFiles($rootDir)

// Read in the current ezBIDS UI information to help perform the mapping.
// For now, assuming that the timing files and the ezBIDS information are stored in same location.
const $root = require('./' + study + '/root.json');

var timingInfo = []
// Load data from each uploaded behavioral timing file
for (let timingFile of timingFiles) {

	var timingObj = {}
	timingObj['filePath'] = timingFile
	
	// Read timing file(s) data
	const sep = find_separator(timingFile)

	// Parse the data, depending on the file extension
	// Excel workbook formats (.xlsx, .xlsm, .xls)
	if (timingFile.indexOf('.xlsx') > -1 || timingFile.indexOf('.xlsm') > -1 || timingFile.indexOf('.xlsb') > -1 || timingFile.indexOf('.xls') > -1) {
		var data = XLSX.readFile(timingFile)
		var timingData = parseExcelWorkbookTimingFiles(data);

	} else {
		// Not Excel workbook format
		var data = fs.readFileSync(timingFile, "utf8")
		const lines = data.trim().split("\n").map(l=>l.trim());

		if (lines[0].indexOf('Header Start') > -1) {
			// E-prime file format
			var timingData = parseEprimeTimingFiles(data)
		} else {
			// "Regular" file format (e.g. .csv .tsv .txt .out)
			var timingData = parseTimingFiles(data, sep);
		}
	}
	timingObj['data'] = timingData
	timingInfo.push(timingObj)
}


/* Extract key mapping information (subject, [session], taskName(s), run numbers associated with each task) 
from the UI (root.json)
*/
rootInfo = []
for (const sub of $root.subjects) {
	const subject = sub.subject.replace(/[^0-9a-zA-Z]/g, '')
	for (const ses of sub.sessions) {
		var session = ses.session

		const taskNames = Array.from(new Set($root.objects.map(e=>e._entities).filter(e=>e.subject == subject &&
																	e.session == session &&
																	e.task != null &&
																	e.task != "" &&
																	e.task != "rest").map(e=>e.task)))

		var numTimeTasks = taskNames.length
		
		for (let task of taskNames) {
			const taskRuns = Array.from(new Set($root.objects.map(e=>e._entities).filter(e=>e.subject == subject &&
															e.session == session &&
															e.task == task).map(e=>e.run)))

			for (let taskRun of taskRuns) {
				mappingObj = {}
				mappingObj['subject'] = subject
				mappingObj['session'] = session
				mappingObj['numTimeTasks'] = numTimeTasks
				mappingObj['task'] = task
				mappingObj['taskRun'] = taskRun
				rootInfo.push(mappingObj)
			}
		}
	}
}

/* Try to determine key mapping information (subject, [session], taskName(s), run numbers for each task) 
from the timing files.
*/
for (const [index, element] of timingInfo.entries()) {
	var data = element.data[0]

	if (data.hasOwnProperty('subject')) {
		timingInfo[index]['subject'] = data['subject']
	} else if (data.hasOwnProperty('participant')) {
		timingInfo[index]['subject'] = data['participant']
	} else if (data.hasOwnProperty('participantid')) {
		timingInfo[index]['subject'] = data['participantid']
	} else {
		timingInfo[index]['subject'] = null
	}


	if (data.hasOwnProperty('session')) {
		timingInfo[index]['session'] = data['session']
	} else if (data.hasOwnProperty('sessionid')) {
		timingInfo[index]['session'] = data['sessionid']
	} else if (data.hasOwnProperty('sesid')) {
		timingInfo[index]['session'] = data['sesid']
	} else if (data.hasOwnProperty('ses')) {
		timingInfo[index]['session'] = data['ses']
	} else {
		timingInfo[index]['session'] = null
	}


	if (data.hasOwnProperty('task')) {
		timingInfo[index]['task'] = data['task']
	} else {
		timingInfo[index]['task'] = null
	}


	if (data.hasOwnProperty('run')) {
		timingInfo[index]['taskRun'] = data['run']
	} else {
		timingInfo[index]['taskRun'] = null
	}


	var modifiedFileName = timingInfo[index].filePath
	/* If any mapping fields are null, check the UI info (root.json) for reference.
	Use modifiedFileName to remove mapping info substrings if found, 
	that way they don't overlap with other mapping info checks.
	*/
	if (timingInfo[index]['subject'] == null) {
		if (rootInfo[index].subject != '' && modifiedFileName.indexOf(rootInfo[index].subject) > -1) {
			timingInfo[index]['subject'] = rootInfo[index].subject
			var modifiedFileName = modifiedFileName.replace(rootInfo[index].subject, '')
		} else {
			timingInfo[index]['subject'] = ''
		}
	}

	if (timingInfo[index]['session'] == null) {
		if (rootInfo[index].session != '' && modifiedFileName.indexOf(rootInfo[index].session) > -1) {
			timingInfo[index]['session'] = rootInfo[index].session
			var modifiedFileName = modifiedFileName.replace(rootInfo[index].session, '')
		} else {
			timingInfo[index]['session'] = ''
		}
	}

	if (timingInfo[index]['task'] == null) {
		if (rootInfo[index].task != '' && modifiedFileName.toLowerCase().indexOf(rootInfo[index].task) > -1) {
			timingInfo[index]['task'] = rootInfo[index].task
			var modifiedFileName = modifiedFileName.replace(rootInfo[index].task, '')
		} else {
			/* If there's only one non-rest task for the subject [and session],
			then use that as the task name
			*/
			if (rootInfo[index].numTimeTasks == 1) {
				timingInfo[index]['task'] = rootInfo[index].task
			} else {
				timingInfo[index]['task'] = ''
			}
		}
	}

	if (timingInfo[index]['taskRun'] == null) {
		if (rootInfo[index].taskRun != '' && modifiedFileName.indexOf(rootInfo[index].taskRun) > -1) {
			timingInfo[index]['taskRun'] = rootInfo[index].taskRun
			var modifiedFileName = modifiedFileName.replace(rootInfo[index.task, ''])
		} else {
			timingInfo[index]['taskRun'] = ''
		}
	}
}
