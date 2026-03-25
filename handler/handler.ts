/* eslint-disable no-console, no-use-before-define, consistent-return */
import { spawn } from 'child_process';
import fs = require('fs');
import path = require('path');
import config = require('../api/config');
import models = require('../api/models');
import { sessionStore, ezbidsStore } from '../api/store';

console.log('---------------------------------------');
console.log(' starting ezbids-handler');
console.log('---------------------------------------');

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

async function handle_deface(session) {
    console.log('handling deface request!-----------------------');
    const workdir = config.workdir + '/' + session._id;
    const defaceJson = JSON.parse(fs.readFileSync(path.join(workdir, 'deface.json'), 'utf8'));
    const method = defaceJson.method;

    session.deface_begin_date = new Date();
    session.deface_end_date = undefined;
    session.status = 'defacing';
    await sessionStore.save(session);

    if (method === 'allineate') {
        // Handle allineate skull-stripping natively in Node.js (works in Electron)
        await handle_allineate_skullstrip(session, workdir, defaceJson.list);
    } else {
        // Fall back to deface.sh for quickshear/pydeface (server environment)
        const projectDir = process.env.PROJECT_DIR ?? './';
        const handlerDir = path.join(projectDir, 'handler');
        await handle(
            session,
            path.join(handlerDir, 'deface.js'),
            'deface',
            (cb) => {
                cb();
            },
            (cb) => {
                session.deface_finish_date = new Date();
                session.status = 'defaced';
                cb();
            }
        );
    }
}

/** Skull-strip anatomical images using allineate. Runs natively in Node.js. */
async function handle_allineate_skullstrip(session: any, workdir: string, list: Array<{ idx: number; path: string }>) {
    // Resolve allineate binary
    const binDir = process.env.EZBIDS_BIN_DIR;
    let allineateBin = 'allineate';
    const projectDir = process.env.PROJECT_DIR ?? './';
    const devPath = path.resolve(projectDir, '..', 'allineate', 'allineate');
    if (binDir && fs.existsSync(path.join(binDir, 'allineate'))) {
        allineateBin = path.join(binDir, 'allineate');
    } else if (fs.existsSync(devPath)) {
        allineateBin = devPath;
    }

    // Resolve MNI template and mask (next to binary)
    const allineateDir = path.dirname(allineateBin);
    const template = path.join(allineateDir, 'MNI152_T1_2mm_ext.nii.gz');
    const mask = path.join(allineateDir, 'MNI152_T1_2mm_ext_mask12.nii.gz');

    if (!fs.existsSync(template) || !fs.existsSync(mask)) {
        session.status = 'failed';
        session.status_msg = `MNI template or mask not found at ${allineateDir}`;
        await sessionStore.save(session);
        return;
    }

    // Reset tracking files
    fs.writeFileSync(path.join(workdir, 'deface.finished'), '');
    fs.writeFileSync(path.join(workdir, 'deface.failed'), '');

    for (const item of list) {
        const anatPath = path.join(workdir, item.path);
        const defacedPath = anatPath + '.defaced.nii.gz';

        console.log(`[skull-strip] Processing [${item.idx}]: ${anatPath}`);
        session.status_msg = `Skull-stripping image ${item.idx + 1} of ${list.length}...`;
        await sessionStore.save(session);

        try {
            // allineate <template> <input> -cost ls -skullstrip <mask> <output>
            const args = [template, anatPath, '-cost', 'ls', '-skullstrip', mask, defacedPath];
            const result = await new Promise<number>((resolve, reject) => {
                const proc = spawn(allineateBin, args, {
                    env: { ...process.env, OMP_NUM_THREADS: '4' },
                });
                proc.stdout.on('data', (d) => console.log(d.toString().trim()));
                proc.stderr.on('data', (d) => console.log(d.toString().trim()));
                proc.on('close', (code) => resolve(code ?? 1));
                proc.on('error', reject);
            });

            if (result !== 0 || !fs.existsSync(defacedPath)) {
                console.log(`[skull-strip] Failed for idx ${item.idx}`);
                fs.appendFileSync(path.join(workdir, 'deface.failed'), item.idx + '\n');
            } else {
                // Generate thumbnail
                try {
                    const thumbScript = path.join(projectDir, 'handler', 'ezBIDS_core', 'createThumbnail.py');
                    await new Promise<void>((resolve) => {
                        const proc = spawn('python3', [thumbScript, defacedPath, defacedPath + '.png']);
                        proc.on('close', () => resolve());
                        proc.on('error', () => resolve()); // thumbnail failure is non-fatal
                    });
                } catch {
                    // thumbnail failure is non-fatal
                }
                fs.appendFileSync(path.join(workdir, 'deface.finished'), item.idx + '\n');
            }
        } catch (err) {
            console.error(`[skull-strip] Error for idx ${item.idx}:`, err);
            fs.appendFileSync(path.join(workdir, 'deface.failed'), item.idx + '\n');
        }
    }

    session.deface_finish_date = new Date();
    session.status = 'defaced';
    session.status_msg = 'Skull stripping complete';
    await sessionStore.save(session);
    console.log('[skull-strip] All done');
}

function handle(session, script: string, name: string, cb_monitor, cb_finish: (err: Error | null) => void) {
    console.log('handling session ' + session._id, name);
    return new Promise((resolve, reject) => {
        sessionStore.save(session).then(() => {
            try {
                let monitor; // eslint-disable-line prefer-const
                const workdir = config.workdir + '/' + session._id;
                const handlerDir = path.join(process.env.PROJECT_DIR ?? './', 'handler');
                const p = spawn(process.execPath, [script, workdir, handlerDir], { cwd: handlerDir, detached: true });
                // const p = spawn(script, [workdir, handlerDir], { cwd: handlerDir, detached: true });
                const logout = fs.openSync(workdir + '/' + name + '.log', 'w');
                const errout = fs.openSync(workdir + '/' + name + '.err', 'w');
                let lasterr = '';
                p.stdout.on('data', (data) => {
                    const out = data.toString('utf8').trim();
                    console.log(out);
                    session.status_msg = out.substring(out.length - 1000);
                    fs.writeSync(logout, data);
                });
                p.stderr.on('data', (data) => {
                    const out = data.toString('utf8').trim();
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
                    if (code !== 0) {
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
