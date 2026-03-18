/* eslint-disable no-console */
import { spawn } from 'child_process';
import fs = require('fs');
import path = require('path');
import config = require('../api/config');
import models = require('../api/models');
import { sessionStore, ezbidsStore } from '../api/store';

console.log('---------------------------------------');
console.log(' starting ezbids-handler');
console.log('---------------------------------------');

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
                            await handle_uploaded(session);
                            break;
                        case 'finalized':
                            await handle_finalized(session);
                            break;
                        case 'deface':
                            await handle_deface(session);
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

async function handle_uploaded(session) {
    const workdir = path.join(config.workdir, session._id);
    const projectDir = process.env.PROJECT_DIR ?? './';
    const handlerDir = path.join(projectDir, 'handler');

    session.pre_begin_date = new Date();
    session.pre_end_date = undefined;

    session.status = 'preprocessing';
    await handle(
        session,
        path.join(handlerDir, 'preprocess.js'),
        'preprocess',
        (cb) => {
            //monitoring callback
            console.log('checking dcm2niix progress--------------------------');
            //load dcm2niix.list/done
            let list = null;
            if (fs.existsSync(workdir + '/dcm2niix.list')) {
                list = fs.readFileSync(workdir + '/dcm2niix.list', 'utf8').split('\n');
                session.dicomCount = list.length;
            }
            let done = null;
            if (fs.existsSync(workdir + '/dcm2niix.done')) {
                done = fs.readFileSync(workdir + '/dcm2niix.done', 'utf8').split('\n');
                session.dicomDone = done.length;
            }
            cb();
        },
        (cb) => {
            //finish callback
            fs.readFile(workdir + '/ezBIDS_core.json', 'utf8', async (err, data) => {
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

async function handle_finalized(session) {
    console.log('handling finalized request!-----------------------');
    const projectDir = process.env.PROJECT_DIR ?? './';
    const handlerDir = path.join(projectDir, 'handler');

    session.finalize_begin_date = new Date();
    session.finalize_end_date = undefined;
    session.status = 'bidsing';

    await handle(
        session,
        path.join(handlerDir, 'bids.js'),
        'bids',
        (cb) => {
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

async function handle_deface(session) {
    console.log('handling deface request!-----------------------');
    const projectDir = process.env.PROJECT_DIR ?? './';
    const handlerDir = path.join(projectDir, 'handler');

    session.deface_begin_date = new Date();
    session.deface_end_date = undefined;
    session.status = 'defacing';

    await handle(
        session,
        path.join(handlerDir, 'deface.js'),
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

function handle(session, script: string, name: string, cb_monitor, cb_finish: (err: Error | null) => void) {
    console.log('handling session ' + session._id, name);
    return new Promise((resolve, reject) => {
        sessionStore.save(session).then(() => {
            try {
                let monitor;
                let workdir = config.workdir + '/' + session._id;
                const handlerDir = path.join(process.env.PROJECT_DIR ?? './', 'handler');
                const p = spawn(process.execPath, [script, workdir, handlerDir], { cwd: handlerDir, detached: true });
                // const p = spawn(script, [workdir, handlerDir], { cwd: handlerDir, detached: true });
                const logout = fs.openSync(workdir + '/' + name + '.log', 'w');
                const errout = fs.openSync(workdir + '/' + name + '.err', 'w');
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
                        cb_finish((err) => {
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
                    //handle cancel request
                    if (fs.existsSync(workdir + '/.cancel')) {
                        console.log('received .cancel request.. killing process group');
                        //p.stdin.pause();
                        process.kill(-p.pid); //, 'SIGKILL');
                        setTimeout(() => {
                            //parallel will wait for child process to end unless we seng SIGTERM again
                            process.kill(-p.pid); //, 'SIGKILL');
                        }, 1000);
                        fs.rename(workdir + '/' + name + '.log', workdir + '/' + name + '.log.canceled', (err) => {
                            if (err) console.error(err);
                        });
                        fs.rename(workdir + '/' + name + '.err', workdir + '/' + name + '.err.canceled', (err) => {
                            if (err) console.error(err);
                        });
                        fs.rename(workdir + '/.cancel', workdir + '/.cancel.ed', (err) => {
                            if (err) console.error(err);
                        });
                    }

                    cb_monitor(() => {
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
