
const { spawn } = require('child_process');
import fs = require('fs');

import config = require('../api/config');
import models = require('../api/models');

console.log("starting preprocess");
models.connect(err=>{
    if(err) throw err;
    run();
});

function run() {
    console.log("finding sessions to preprocess");
    models.Session.find({
        //TODO- why don't we just look for "uploaded" session?
        //upload_finish_date: {$exists: true}, 
        //pre_begin_date: {$exists: false},
        status: {$in: ["finalized", "uploaded"]},
    }).then(async sessions=>{
        for(let session of sessions) {
            try {
                switch(session.status) {
                case "uploaded":
                    await handle_uploaded_session(session);
                    break;
                case "finalized":
                    await handle_finalized_session(session);
                    break;
                }
            } catch(err) {
                console.error(err);
            }
        }
        setTimeout(run, 1000*3);
    });
}

function handle_uploaded_session(session) {
    console.log("handling uploaded session "+session._id);
    return new Promise((resolve, reject)=>{
        session.pre_begin_date = new Date();
        session.status = "preprocessing"; 
        session.save().then(()=>{
            let monitor;
            let lastout;
            let workdir = config.workdir+"/"+session._id;
            const p = spawn('./preprocess.sh', [workdir], {cwd: __dirname});
            const logout = fs.openSync(workdir+"/preprocess.log", "w");
            const errout = fs.openSync(workdir+"/preprocess.err", "w");
            let lasterr = "";
            p.stdout.on('data', data=>{
                fs.writeSync(logout, data);
                console.log(data.toString("utf8"));
                //session.status_msg = data.toString("utf8").trim().split("\n").pop();
                session.status_msg = data.toString("utf8").trim();//.split("\n").pop();
            });
            p.stderr.on('data', data=>{
                console.log(data.toString("utf8"));
                lasterr = data.toString("utf8");
                fs.writeSync(errout, data);
            })
            p.on('close', code=>{
                clearInterval(monitor);

                fs.closeSync(logout);
                fs.closeSync(errout);

                //check status
                console.debug("preprocess.sh finished: "+code);
                if(code != 0) {
                    session.status = "failed";
                    session.status_msg = "failed\n"+lasterr;
                    //update session and done.
                    session.save().then(()=>{
                        resolve();
                    }).catch(reject);
                } else {
                    session.status = "analyzed";
                    session.status_msg = "successfully run preprocess.sh";
                    session.pre_finish_date = new Date();
                    fs.readFile(workdir+"/ezBIDS.json", "utf8", (err, data)=>{
                        if(err) reject();
                        let ezbids = new models.ezBIDS({
                            _session_id: session._id,
                            original: JSON.parse(data),
                        });
                        ezbids.save().then(()=>{
                            session.save().then(()=>{
                                resolve();
                            }).catch(reject);
                        }).catch(reject);
                    });
                }

            })

            //monitor progress
            monitor = setInterval(()=>{
                console.log("checking dcm2niix progress--------------------------");
                //load dcm2niix.list/done 
                let list = null;
                if(fs.existsSync(workdir+"/dcm2niix.list")) {
                    list = fs.readFileSync(workdir+"/dcm2niix.list", "utf8").split("\n");
                    session.dicomCount = list.length;
                }
                let done = null;
                if(fs.existsSync(workdir+"/dcm2niix.done")) {
                    done = fs.readFileSync(workdir+"/dcm2niix.done", "utf8").split("\n");
                    session.dicomDone = done.length;
                }
                if(list || done) session.save();
            }, 1000*10);
        });
    });
}

function handle_finalized_session(session) {
    console.log("handling uploaded session "+session._id);
    return new Promise((resolve, reject)=>{
        //session.pre_begin_date = new Date();
        session.status = "bidsing"; 
        session.save().then(()=>{

            let workdir = config.workdir+"/"+session._id;
            const p = spawn('./bids.sh', [workdir], {cwd: __dirname});
            const logout = fs.openSync(workdir+"/bids.log", "w");
            const errout = fs.openSync(workdir+"/bids.err", "w");
            p.stdout.on('data', data=>{
                console.log(data.toString("utf8"));
                fs.writeSync(logout, data);
            });
            p.stderr.on('data', data=>{
                console.log(data.toString("utf8"));
                fs.writeSync(errout, data);
            })
            p.on('close', code=>{
                fs.closeSync(logout);
                fs.closeSync(errout);

                //check status
                console.debug("bids.sh finished: "+code);
                if(code != 0) {
                    session.status = "failed";
                    session.status_msg = "failed to run preprocess.sh";
                } else {
                    session.status = "finished";
                    session.status_msg = "successfully run bids.sh";
                    //session.pre_finish_date = new Date();
                }

                //update session and done.
                session.save().then(()=>{
                    resolve();
                }).catch(err=>{
                    reject();
                });
            })
        });
    });
}



