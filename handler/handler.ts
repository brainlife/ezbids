require('dotenv').config({ path:'../.env' })

const { spawn } = require('child_process');
import fs = require('fs');

import config = require('../api/config');
import models = require('../api/models');

console.log("---------------------------------------")
console.log(" starting ezbids-handler");
console.log("---------------------------------------")

models.connect(err=>{
    if(err) throw err;
    run();
});

function run() {
    models.Session.find({
        //TODO- why don't we just look for "uploaded" session?
        //upload_finish_date: {$exists: true}, 
        //pre_begin_date: {$exists: false},
        status: {$in: ["finalized", "uploaded", "deface"]},
    }).then(async sessions=>{
        for(let session of sessions) {
            try {
                switch(session.status) {
                case "uploaded":
                    await handle_uploaded(session);
                    break;
                case "finalized":
                    await handle_finalized(session);
                    break;
                case "deface":
                    await handle_deface(session);
                    break;
                }
            } catch(err) {
                console.log("caught exception...")
                console.error(err);
            }
        }
        console.log("waiting a bit before looking for more jobs");
        setTimeout(run, 1000*3);
    });
}

async function handle_uploaded(session) {
    let workdir = process.env.WORK_DIR + "/"+session._id;

    session.pre_begin_date = new Date();
    session.pre_end_date = undefined;

    session.status = "preprocessing"; 
    await handle(session, "./preprocess.sh", "preprocess", cb=>{
        //monitoring callback
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
        cb();
    }, cb=>{
        //finish callback
        fs.readFile(workdir+"/ezBIDS_core.json", "utf8", async (err, data)=>{
            if(err) return cb(err);
            try {
                //try parsing the json!
                const json = JSON.parse(data);
                const ezbids = new models.ezBIDS({
                    _session_id: session._id,
                    original: JSON.parse(data),
                });
                await ezbids.save();

                session.status = "analyzed";
                session.status_msg = "successfully run preprocess.sh";
                session.pre_finish_date = new Date();
            } catch (err) {
                return cb(err);
            }
            await session.save();
            cb();
        });
    });
}

async function handle_finalized(session) {
    console.log("handling finalized request!-----------------------");

    session.finalize_begin_date = new Date();
    session.finalize_end_date = undefined;
    session.status = "bidsing";

    await handle(session, "./bids.sh", "bids", cb=>{
        //monitor cb
    }, cb=>{
        //finish cb
        session.finalize_finish_date = new Date();
        session.status = "finished";
        cb();
    });
}

async function handle_deface(session) {
    console.log("handling deface request!-----------------------");

    session.deface_begin_date = new Date();
    session.deface_end_date = undefined;
    session.status = "defacing";

    await handle(session, "./deface.sh", "deface", cb=>{
        //monitor cb - nothing special to do yet
        cb();
    }, cb=>{
        //finish cb
        session.deface_finish_date = new Date();
        session.status = "defaced";
        cb();
    });
}

function handle(session, script, name, cb_monitor, cb_finish) {
    let workdir = process.env.WORK_DIR + "/"+session._id;
    console.log("handling session "+session._id, name);
    return new Promise((resolve, reject)=>{
        session.save().then(()=>{
            try {
                let monitor;
                let workdir = process.env.WORK_DIR + "/"+session._id;
                const p = spawn(script, [workdir], {cwd: __dirname, detached: true});
                const logout = fs.openSync(workdir+"/"+name+".log", "w");
                const errout = fs.openSync(workdir+"/"+name+".err", "w");
                let lasterr = "";
                p.stdout.on('data', data=>{
                    let out = data.toString("utf8").trim();
                    console.log(out);
                    session.status_msg = out.substring(out.length - 1000);
                    fs.writeSync(logout, data);
                });
                p.stderr.on('data', data=>{
                    let out = data.toString("utf8").trim();
                    console.log(out);
                    lasterr = out;
                    fs.writeSync(errout, data);
                })
                p.on('close', code=>{
                    clearInterval(monitor);
                    console.log("process closed");
                    fs.closeSync(logout);
                    fs.closeSync(errout);

                    //check status
                    console.debug(name+" finished: "+code);
                    if(code != 0) {
                        session.status = "failed";
                        session.status_msg = `failed to run ${name} -- code:${code}\n${lasterr}`;
                        session.save().then(resolve).catch(reject);
                    } else {
                        session.status_msg = "successfully run "+name;
                        cb_finish(err=>{
                            if(err) {
                                session.status = "failed";  
                                session.status_msg = err;
                                console.error(err);
                            } 
                            session.save().then(resolve).catch(reject);
                        });
                    }
                })

                //update session periodically
                monitor = setInterval(()=>{

                    //handle cancel request
                    if(fs.existsSync(workdir+"/.cancel")) {
                        console.log("received .cancel request.. killing process group");
                        //p.stdin.pause();
                        process.kill(-p.pid);//, 'SIGKILL');
                        setTimeout(()=>{
                            //parallel will wait for child process to end unless we seng SIGTERM again
                            process.kill(-p.pid);//, 'SIGKILL');
                        }, 1000);
                        fs.rename(workdir+"/"+name+".log", workdir+"/"+name+".log.canceled", err=>{
                            if(err) console.error(err); 
                        });
                        fs.rename(workdir+"/"+name+".err", workdir+"/"+name+".err.canceled", err=>{
                            if(err) console.error(err); 
                        });
                        fs.rename(workdir+"/.cancel", workdir+"/.cancel.ed", err=>{
                            if(err) console.error(err); 
                        });
                    }

                    cb_monitor(()=>{
                        session.save(); //saves for stdout and any update made by monitor_cb
                    });

                }, 1000*5);
            } catch(err) {
                //from spawn?
                reject(err);
            }
        });
    });
}

