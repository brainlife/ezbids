"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
const { spawn } = require('child_process');
const fs = require("fs");
const config = require("../api/config");
const models = require("../api/models");
console.log("---------------------------------------");
console.log(" starting ezbids-handler");
console.log("---------------------------------------");
models.connect(err => {
    if (err)
        throw err;
    run();
});
function run() {
    models.Session.find({
        //TODO- why don't we just look for "uploaded" session?
        //upload_finish_date: {$exists: true}, 
        //pre_begin_date: {$exists: false},
        status: { $in: ["finalized", "uploaded", "deface"] },
    }).then((sessions) => __awaiter(this, void 0, void 0, function* () {
        for (let session of sessions) {
            try {
                switch (session.status) {
                    case "uploaded":
                        yield handle_uploaded(session);
                        break;
                    case "finalized":
                        yield handle_finalized(session);
                        break;
                    case "deface":
                        yield handle_deface(session);
                        break;
                }
            }
            catch (err) {
                console.log("caught exception...");
                console.error(err);
            }
        }
        console.log("waiting a bit before looking for more jobs");
        setTimeout(run, 1000 * 3);
    }));
}
function handle_uploaded(session) {
    return __awaiter(this, void 0, void 0, function* () {
        let workdir = config.workdir + "/" + session._id;
        session.pre_begin_date = new Date();
        session.status = "preprocessing";
        yield handle(session, "./preprocess.sh", "preprocess", cb => {
            //monitoring callback
            console.log("checking dcm2niix progress--------------------------");
            //load dcm2niix.list/done 
            let list = null;
            if (fs.existsSync(workdir + "/dcm2niix.list")) {
                list = fs.readFileSync(workdir + "/dcm2niix.list", "utf8").split("\n");
                session.dicomCount = list.length;
            }
            let done = null;
            if (fs.existsSync(workdir + "/dcm2niix.done")) {
                done = fs.readFileSync(workdir + "/dcm2niix.done", "utf8").split("\n");
                session.dicomDone = done.length;
            }
            cb();
        }, cb => {
            //finish callback
            session.status = "analyzed";
            session.status_msg = "successfully run preprocess.sh";
            session.pre_finish_date = new Date();
            fs.readFile(workdir + "/ezBIDS.json", "utf8", (err, data) => {
                if (err)
                    cb(err);
                let ezbids = new models.ezBIDS({
                    _session_id: session._id,
                    original: JSON.parse(data),
                });
                ezbids.save().then(() => {
                    session.save().then(() => {
                        cb();
                    }).catch(cb);
                }).catch(cb);
            });
        });
    });
}
function handle_finalized(session) {
    return __awaiter(this, void 0, void 0, function* () {
        session.status = "bidsing";
        yield handle(session, "./bids.sh", "bids", cb => {
            //monitor cb
        }, cb => {
            //finish cb
            session.status = "finished";
            cb();
        });
    });
}
function handle_deface(session) {
    return __awaiter(this, void 0, void 0, function* () {
        session.status = "defacing";
        yield handle(session, "./deface.sh", "deface", cb => {
            //monitor cb
            cb();
        }, cb => {
            //finish cb
            session.status = "defaced";
            cb();
        });
    });
}
function handle(session, script, name, cb_monitor, cb_finish) {
    let workdir = config.workdir + "/" + session._id;
    console.log("handling session " + session._id, name);
    return new Promise((resolve, reject) => {
        session.save().then(() => {
            try {
                let monitor;
                let workdir = config.workdir + "/" + session._id;
                const p = spawn(script, [workdir], { cwd: __dirname });
                const logout = fs.openSync(workdir + "/" + name + ".log", "w");
                const errout = fs.openSync(workdir + "/" + name + ".err", "w");
                let lasterr = "";
                p.stdout.on('data', data => {
                    fs.writeSync(logout, data);
                    let out = data.toString("utf8").trim();
                    console.log(out);
                    session.status_msg = out.substring(out.length - 1000);
                });
                p.stderr.on('data', data => {
                    console.log(data.toString("utf8"));
                    lasterr = data.toString("utf8");
                    fs.writeSync(errout, data);
                });
                p.on('close', code => {
                    clearInterval(monitor);
                    fs.closeSync(logout);
                    fs.closeSync(errout);
                    //check status
                    console.debug(name + " finished: " + code);
                    if (code != 0) {
                        session.status = "failed";
                        session.status_msg = `failed to run ${name} -- code:${code}\n${lasterr}`;
                        session.save().then(resolve).catch(reject);
                    }
                    else {
                        session.status_msg = "successfully run " + name;
                        cb_finish(() => {
                            session.save().then(resolve).catch(reject);
                        });
                    }
                });
                //update session periodically
                monitor = setInterval(() => {
                    cb_monitor(() => {
                        session.save(); //saves for stdout and any update made by monitor_cb
                    });
                }, 1000 * 5);
            }
            catch (err) {
                //from spawn?
                reject(err);
            }
        });
    });
}
//# sourceMappingURL=handler.js.map