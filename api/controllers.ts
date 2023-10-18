
import express = require('express');
import multer = require('multer');
import path = require('path');
import fs = require('fs');
import mkdirp = require('mkdirp');
import archiver = require('archiver');
import async = require('async');
import { validateWithJWTConfig } from './auth'

import config = require('./config');
import models = require('./models');
import rangeStream = require('range-stream');

console.debug(config.multer);
const upload = multer(config.multer);

const router = express.Router();
/**
 * @swagger
 * paths:
 *  /health:
 *    get:
 *      summary: Health check
 *      description: This endpoint allows for the health check of the server. It checks to see if the workdir is accessible.
 *      tags:
 *        - Health
 *      responses:
 *        '200':
 *          description: Returns the health status
 *          content:
 *            application/json:
 *              schema:
 *                type: object
 *                properties:
 *                  status:
 *                    type: string
 *                  timestamp:
 *                    type: string
 *                    format: date-time
 *        '503':
 *          description: Service is unhealthy
 *          content:
 *            application/json:
 *              schema:
 *                type: object
 *                properties:
 *                  status:
 *                    type: string
 *                  error:
 *                    type: string
 */
router.get('/health', (req, res, next) => {
    let status = "ok";
    let message = "";

    //check to see if we can access the workdir
    try {
        fs.writeFileSync(config.workdir + '/health.txt', "test")
    } catch (err) {
        status = "failed";
        message = err;
    }
    res.json({ status, message, date: new Date() });
});

/**
 * @swagger
 * paths:
 *   /session/{session_id}:
 *     post:
 *       summary: Post a session by its ID
 *       description: This endpoint retrieves a session by its `session_id`.
 *       tags:
 *         - Session
 *       parameters:
 *         - in: path
 *           name: session_id
 *           schema:
 *             type: string
 *           required: true
 *           description: The session ID to retrieve
 *       responses:
 *         200:
 *           description: Returns the requested session
 *           content:
 *             application/json:
 *               schema:
 *                 $ref: '#/components/schemas/Session'
 *         400:
 *           description: Bad request
 *         404:
 *           description: Session not found
 *         500:
 *           description: Server error
 *
 * components:
 *   schemas:
 *    Session: $ref: '#/components/schemas/Session'
 */
router.post('/session', validateWithJWTConfig(), (req, res, next) => {
    console.log((req as any).auth);
    req.body.status = "created";
    req.body.request_headers = req.headers;
    let session = new models.Session(req.body);
    session.save().then(_session => { //mongoose contains err on the 1st argument of resolve!? odd.
        res.json(_session);
    }).catch(err => {
        next(err);
    });
});

/**
 * @swagger
 * paths:
 *   /session/{session_id}:
 *     get:
 *       summary: Retrieve a session by its ID
 *       description: This endpoint retrieves a session by its `session_id`.
 *       tags:
 *         - Session
 *       parameters:
 *         - in: path
 *           name: session_id
 *           schema:
 *             type: string
 *           required: true
 *           description: The session ID to retrieve
 *       responses:
 *         200:
 *           description: Returns the requested session
 *           content:
 *             application/json:
 *               schema:
 *                 $ref: '#/components/schemas/Session'
 *         400:
 *           description: Bad request
 *         404:
 *           description: Session not found
 *         500:
 *           description: Server error
 *
 * components:
 *   schemas:
 *     Session:
 *       type: object
 *       properties:
 *         create_date:
 *           type: string
 *           format: date-time
 *           description: Creation date of the session
 *           example: '2023-01-01T00:00:00Z'
 *         update_date:
 *           type: string
 *           format: date-time
 *           description: Last update date of the session
 *           example: '2023-01-02T00:00:00Z'
 *         status:
 *           type: string
 *           description: Status of the session
 *           example: created
 *         status_msg:
 *           type: string
 *           description: Status message for the session
 *         request_headers:
 *           type: object
 *           description: Headers of the request when creating the session
 *         upload_finish_date:
 *           type: string
 *           format: date-time
 *           description: Finish date of file upload
 */
router.get('/session/:session_id', (req, res, next) => {
    if (!req.params.session_id) return next("session is empty")
    models.Session.findById(req.params.session_id).then(session => {
        res.json(session);
    }).catch(err => {
        next(err);
    });
});

/**
 * @swagger
 * paths:
 *   /session/{session_id}/deface:
 *     post:
 *       summary: Deface a session by its ID
 *       description: This endpoint allows defacing an existing session by its `session_id`.
 *       tags:
 *         - Session
 *       parameters:
 *         - in: path
 *           name: session_id
 *           schema:
 *             type: string
 *           required: true
 *           description: The session ID to deface
 *       requestBody:
 *         description: Deface options and parameters
 *         required: true
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *       responses:
 *         200:
 *           description: Successfully defaced the session
 *         400:
 *           description: Bad request
 *         404:
 *           description: Session not found
 *         500:
 *           description: Server error
 */
router.post('/session/:session_id/deface', (req, res, next) => {
    models.Session.findById(req.params.session_id).then(session => {
        if (!session) return next("no such session");

        fs.writeFile(config.workdir + "/" + session._id + "/deface.json", JSON.stringify(req.body), err => {
            session.status = "deface";
            session.status_msg = "Waiting to be defaced";
            session.save().then(() => {
                res.send("ok");
            });
        });
    });
});

/**
 * @swagger
 * paths:
 *   /session/{session_id}/canceldeface:
 *     post:
 *       summary: Cancel the deface operation for a session by its ID
 *       description: This endpoint allows cancelling the defacing of an existing session by its `session_id`.
 *       tags:
 *         - Session
 *       parameters:
 *         - in: path
 *           name: session_id
 *           schema:
 *             type: string
 *           required: true
 *           description: The session ID whose defacing is to be cancelled
 *       responses:
 *         200:
 *           description: Successfully cancelled defacing for the session
 *         400:
 *           description: Bad request
 *         404:
 *           description: Session not found
 *         500:
 *           description: Server error
 */
router.post('/session/:session_id/canceldeface', (req, res, next) => {
    models.Session.findById(req.params.session_id).then(session => {
        if (!session) return next("no such session");

        //request deface.cancel by writing out "deface.cancel" file
        console.debug("writing .cancel");
        fs.writeFile(config.workdir + "/" + session._id + "/.cancel", "", err => {
            if (err) console.error(err);

            session.status_msg = "requested to cancel defacing";

            //handler should set the status when the job is killed so this shouldn't
            //be necessary.. but right not kill() doesn't work.. so
            session.deface_begin_date = undefined;
            session.status = "analyzed";
            session.save().then(() => {
                res.send("ok");
            });
        });
    });
});

/**
 * @swagger
 * paths:
 *   /session/{session_id}/resetdeface:
 *     post:
 *       summary: Reset the deface status for a session by its ID
 *       description: This endpoint allows resetting the deface status for a session by its `session_id`.
 *       tags:
 *         - Session
 *       parameters:
 *         - in: path
 *           name: session_id
 *           schema:
 *             type: string
 *           required: true
 *           description: The session ID whose deface status is to be reset
 *       responses:
 *         200:
 *           description: Successfully reset defacing for the session
 *         400:
 *           description: Bad request
 *         404:
 *           description: Session not found
 *         500:
 *           description: Server error
 */
router.post('/session/:session_id/resetdeface', (req, res, next) => {
    models.Session.findById(req.params.session_id).then(session => {
        if (!session) return next("no such session");
        try {
            const workdir = config.workdir + "/" + session._id;
            console.log("removing deface output");
            if (fs.existsSync(workdir + "/deface.finished")) {
                fs.unlinkSync(workdir + "/deface.finished");
            }
            if (fs.existsSync(workdir + "/deface.failed")) {
                fs.unlinkSync(workdir + "/deface.failed");
            }
            session.status = "analyzed";
            session.status_msg = "reset defacing";
            session.deface_begin_date = undefined;
            session.deface_finish_date = undefined;
            session.save().then(() => {
                res.send("ok");
            });
        } catch (err) {
            console.error(err);
            res.send(err);
        }
    });
});


router.post('/session/:session_id/finalize', (req, res, next) => {
    models.Session.findById(req.params.session_id).then(session => {
        if (!session) return next("no such session");
        fs.writeFile(config.workdir + "/" + session._id + "/finalized.json", JSON.stringify(req.body), err => {
            models.ezBIDS.findOneAndUpdate({ _session_id: req.params.session_id }, {
                $set: {

                    //TODO - store this somewhere for book keeping
                    //updated: req.body, //finalized.json could exceed 16MB 

                    update_date: new Date(),
                }
            }).then(err => {
                session.status = "finalized";
                session.status_msg = "Waiting to be finalized";
                session.save().then(() => {
                    res.send("ok");
                });
            });
        });
    });
});

//download finalized(updated) content
router.get('/session/:session_id/updated', (req, res, next) => {
    models.ezBIDS.findOne({ _session_id: req.params.session_id }).then(ezbids => {
        if (!ezbids) return next("no such session or ezbids not finalized");
        if (!ezbids.updated) return next("not yet finalized");
        res.json(ezbids.updated);
    });
});

//let user download files within session (like the .png image generated by analyzer)
router.get('/download/:session_id/*', (req, res, next) => {
    models.Session.findById(req.params.session_id).then(session => {
        const basepath = config.workdir + "/" + session._id;

        //validate path so it will be inside the basepath
        const fullpath = path.resolve(basepath + "/" + req.params[0]);
        if (!fullpath.startsWith(basepath)) return next("invalid path");

        //TODO - if requested path is a file, thenstream
        const stats = fs.lstatSync(fullpath);
        if (stats.isFile()) {
            res.setHeader('Content-disposition', 'attachment; filename=' + path.basename(fullpath));
            fs.createReadStream(fullpath).pipe(res);
        } else if (stats.isDirectory()) {
            res.setHeader('Content-disposition', 'attachment; filename=' + path.basename(fullpath) + ".zip");
            const archive = archiver('zip', {
                zlib: { level: 0 }
            });
            archive.directory(fullpath, 'bids');
            archive.finalize();
            archive.pipe(res);

        } else next("weird file");
    }).catch(err => {
        next(err);
    });
});

router.post('/upload-multi/:session_id', upload.any(), (req: any, res, next) => {

    //when a single file is uploaded paths becomes just a string. convert it to an array of 1
    let paths = req.body["paths"];
    if (!Array.isArray(paths)) paths = [paths];
    //same for mtimes
    let mtimes = req.body["mtimes"];
    if (!Array.isArray(mtimes)) mtimes = [mtimes];

    models.Session.findById(req.params.session_id).then(async session => {
        let idx = -1;
        async.eachSeries(req.files, (file: any, next_file) => {
            idx++;
            const src_path = file.path;
            /* //file
11|ezbids- | {
11|ezbids- |   fieldname: 'files',
11|ezbids- |   originalname: 'i1848324.MRDC.82',
11|ezbids- |   encoding: '7bit',
11|ezbids- |   mimetype: 'application/octet-stream',
11|ezbids- |   destination: '/mnt/ezbids/upload',
11|ezbids- |   filename: '2d682c5694b0fb8da2beeea3e670350a',
11|ezbids- |   path: '/mnt/ezbids/upload/2d682c5694b0fb8da2beeea3e670350a',
11|ezbids- |   size: 147882
11|ezbids- | }
            */
            const dirty_path = config.workdir + "/" + req.params.session_id + "/" + paths[idx];
            const dest_path = path.resolve(dirty_path);
            const mtime = mtimes[idx] / 1000; //browser uses msec.. filesystem uses sec since epoch

            if (!dest_path.startsWith(config.workdir)) return next_file(new Error(`invalid path: ${dest_path}`));
            const destdir = path.dirname(dest_path);

            //move the file over to workdir
            const made = mkdirp.sync(destdir);
            fs.renameSync(src_path, dest_path);
            if (mtime) fs.utimesSync(dest_path, mtime, mtime);
            next_file();
        }, err => {
            if (err) return next(err);
            res.send("ok");
        });

    }).catch(err => {
        console.error(err);
        next(err);
    });
});

//done uploading.
router.patch('/session/uploaded/:session_id', (req, res, next) => {
    models.Session.findByIdAndUpdate(req.params.session_id, {
        status: "uploaded",
        status_msg: "Waiting in the queue..",
        upload_finish_date: new Date()
    }).then(session => {
        if (!session) return next("no such session");
        res.send("ok");
    }).catch(err => {
        console.error(err);
        next(err);
    });
});

module.exports = router;