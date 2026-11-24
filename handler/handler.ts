/* eslint-disable no-console */
import { spawn } from 'child_process';
import fs = require('fs');
import path = require('path');
import config = require('../api/config');
import models = require('../api/models');
import { sessionStore, ezbidsStore } from '../api/store';
import { nodeArgsForScript, resolveHandlerScript } from './utils';

console.log('---------------------------------------');
console.log(' starting ezbids-handler');
console.log('---------------------------------------');

function handle(
    session,
    script: string,
    name: string,
    cbMonitor: (done: () => void) => void,
    cbFinish: (done: (err?: Error | null) => void) => void
) {
    console.log('handling session ' + session._id, name);
    return new Promise((resolve, reject) => {
        sessionStore.save(session).then(() => {
            try {
                let monitor;
                let cancelHandled = false;
                const workdir = path.join(config.workdir, String(session._id));
                const handlerDir = process.env.EZBIDS_HANDLER_DIR ?? './handler';
                const spawnArgs = nodeArgsForScript([script, workdir, handlerDir]);

                const p = spawn(process.execPath, spawnArgs, { cwd: handlerDir, detached: true });
                // const p = spawn(script, [workdir, handlerDir], { cwd: handlerDir, detached: true });
                const logPath = path.join(workdir, `${name}.log`);
                const errPath = path.join(workdir, `${name}.err`);
                const logout = fs.openSync(logPath, 'w');
                const errout = fs.openSync(errPath, 'w');
                let lasterr = '';
                p.stdout.on('data', (data) => {
                    let out = data.toString('utf8').trim();
                    console.log(out);
                    session.status_msg = out.substring(out.length - 1000);
                    fs.writeSync(logout, data);
                });
                p.stderr.on('data', (data) => {
                    let out = data.toString('utf8').trim();
                    console.log(out);
                    lasterr = out;
                    fs.writeSync(errout, data);
                });
                p.on('close', (code) => {
                    clearInterval(monitor);
                    console.log('process closed');
                    fs.closeSync(logout);
                    fs.closeSync(errout);

                    //check status
                    console.debug(name + ' finished: ' + code);
                    if (code != 0) {
                        session.status = 'failed';
                        session.status_msg = `failed to run ${name} -- code:${code}\n${lasterr}`;
                        sessionStore.save(session).then(resolve).catch(reject);
                    } else {
                        session.status_msg = 'successfully run ' + name;
                        cbFinish((err) => {
                            if (err) {
                                session.status = 'failed';
                                session.status_msg = err;
                                console.error(err);
                            }
                            sessionStore.save(session).then(resolve).catch(reject);
                        });
                    }
                });

                //update session periodically
                monitor = setInterval(() => {
                    const safeKill = (pid: number) => {
                        try {
                            process.kill(pid);
                        } catch (err) {
                            // Ignore "no such process" when child exited between checks.
                            if (!(err && err.code === 'ESRCH')) {
                                throw err;
                            }
                        }
                    };

                    //handle cancel request
                    const cancelPath = path.join(workdir, '.cancel');
                    if (!cancelHandled && fs.existsSync(cancelPath)) {
                        cancelHandled = true;
                        console.log('received .cancel request.. killing process group');
                        //p.stdin.pause();
                        safeKill(-p.pid); //, 'SIGKILL');
                        setTimeout(() => {
                            //parallel will wait for child process to end unless we seng SIGTERM again
                            safeKill(-p.pid); //, 'SIGKILL');
                        }, 1000);
                        fs.rename(logPath, path.join(workdir, `${name}.log.canceled`), (err) => {
                            if (err) console.error(err);
                        });
                        fs.rename(errPath, path.join(workdir, `${name}.err.canceled`), (err) => {
                            if (err) console.error(err);
                        });
                        fs.rename(cancelPath, path.join(workdir, '.cancel.ed'), (err) => {
                            if (err) console.error(err);
                        });
                    }

                    cbMonitor(() => {
                        sessionStore.save(session);
                    });
                }, 1000 * 5);
            } catch (err) {
                //from spawn?
                reject(err);
            }
        });
    });
}

async function handleUploaded(session) {
    const workdir = path.join(config.workdir, session._id);
    const handlerDir = process.env.EZBIDS_HANDLER_DIR ?? './handler';
    const preprocessScript = resolveHandlerScript('preprocess', handlerDir);

    session.pre_begin_date = new Date();
    session.pre_end_date = undefined;

    session.status = 'preprocessing';
    await handle(
        session,
        preprocessScript,
        'preprocess',
        (cb) => {
            //monitoring callback
            console.log('checking dcm2niix progress--------------------------');
            //load dcm2niix.list/done
            let list = null;
            const dcm2niixListPath = path.join(workdir, 'dcm2niix.list');
            if (fs.existsSync(dcm2niixListPath)) {
                list = fs.readFileSync(dcm2niixListPath, 'utf8').split('\n');
                session.dicomCount = list.length;
            }
            let done = null;
            const dcm2niixDonePath = path.join(workdir, 'dcm2niix.done');
            if (fs.existsSync(dcm2niixDonePath)) {
                done = fs.readFileSync(dcm2niixDonePath, 'utf8').split('\n');
                session.dicomDone = done.length;
            }
            cb();
        },
        (cb) => {
            //finish callback
            fs.readFile(path.join(workdir, 'ezBIDS_core.json'), 'utf8', async (err, data) => {
                if (err) return cb(err);
                try {
                    //try parsing the json!
                    const json = JSON.parse(data);
                    await ezbidsStore.create({
                        _session_id: session._id,
                        original: json,
                    });

                    session.status = 'analyzed';
                    session.status_msg = 'successfully run preprocess';
                    session.pre_finish_date = new Date();
                } catch (err) {
                    return cb(err);
                }
                await sessionStore.save(session);
                cb();
            });
        }
    );
}

async function handleFinalized(session) {
    console.log('handling finalized request!-----------------------');
    const handlerDir = process.env.EZBIDS_HANDLER_DIR ?? './handler';
    const bidsScript = resolveHandlerScript('bids', handlerDir);

    session.finalize_begin_date = new Date();
    session.finalize_end_date = undefined;
    session.status = 'bidsing';

    await handle(
        session,
        bidsScript,
        'bids',
        () => {
            //monitor cb
        },
        (cb) => {
            //finish cb
            session.finalize_finish_date = new Date();
            session.status = 'finished';
            cb();
        }
    );
}

async function handleDeface(session) {
    console.log('handling deface request!-----------------------');
    const handlerDir = process.env.EZBIDS_HANDLER_DIR ?? './handler';
    const defacePath = resolveHandlerScript('deface', handlerDir);

    session.deface_begin_date = new Date();
    session.deface_end_date = undefined;
    session.status = 'defacing';

    await handle(
        session,
        defacePath,
        'deface',
        (cb) => {
            //monitor cb - nothing special to do yet
            cb();
        },
        (cb) => {
            //finish cb
            session.deface_finish_date = new Date();
            session.status = 'defaced';
            cb();
        }
    );
}

setInterval(() => {
    try {
        process.kill(process.ppid, 0);
    } catch (e) {
        console.log('parent process gone, shutting down handler');
        process.exit(0);
    }
}, 1000).unref();

function run() {
    sessionStore
        .find({
            status: { $in: ['finalized', 'uploaded', 'deface'] },
        })
        .then(async (sessions) => {
            for (const session of sessions) {
                console.log({ session });
                try {
                    switch (session.status) {
                        case 'uploaded':
                            await handleUploaded(session);
                            break;
                        case 'finalized':
                            await handleFinalized(session);
                            break;
                        case 'deface':
                            await handleDeface(session);
                            break;
                        default:
                            console.log('unknown status', session._id, session.status);
                            break;
                    }
                } catch (err) {
                    console.log('caught exception...');
                    console.error(err);
                }
            }
            console.log('waiting a bit before looking for more jobs');
            setTimeout(run, 1000 * 3);
        });
}

function start() {
    if (config.isElectron) {
        console.log('starting ezbids-handler in electron mode');
        run();
    } else {
        console.log('Connecting to MongoDB.');
        models.connect((err) => {
            if (err) throw err;
            run();
        });
    }
}
start();
