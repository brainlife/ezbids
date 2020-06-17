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
console.log("starting preprocess");
models.connect(err => {
    if (err)
        throw err;
    run();
});
function run() {
    console.log("finding sessions to preprocess");
    models.Session.find({
        upload_finish_date: { $exists: true },
        pre_begin_date: { $exists: false },
    }).then((sessions) => __awaiter(this, void 0, void 0, function* () {
        for (let session of sessions) {
            yield handle_session(session);
        }
        console.log("done.. taking a break");
        setTimeout(run, 1000 * 5);
    }));
}
function handle_session(session) {
    console.log("handling session " + session._id);
    return new Promise((resolve, reject) => {
        session.pre_begin_date = new Date();
        session.status = "preprocessing"; //not working?
        session.save().then(() => {
            let workdir = config.workdir + "/" + session._id;
            const p = spawn('./preprocess.sh', [workdir], { cwd: __dirname });
            const logout = fs.openSync(workdir + "/preprocess.log", "w");
            const errout = fs.openSync(workdir + "/preprocess.err", "w");
            p.stdout.on('data', data => {
                console.log(data.toString("utf8"));
                fs.writeSync(logout, data);
            });
            p.stderr.on('data', data => {
                console.log(data.toString("utf8"));
                fs.writeSync(errout, data);
            });
            p.on('close', code => {
                //check status
                console.debug("preprocess.sh finished: " + code);
                if (code != 0) {
                    session.status = "failed";
                    session.status_msg = "failed to run preprocess.sh";
                }
                else {
                    session.status = "analyzed";
                    session.status_msg = "successfully run preprocess.sh";
                    session.pre_finish_date = new Date();
                }
                //update session and done.
                session.save().then(() => {
                    resolve();
                }).catch(err => {
                    reject();
                });
            });
        });
    });
}
//# sourceMappingURL=handler.js.map