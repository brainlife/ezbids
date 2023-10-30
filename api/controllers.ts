
import * as express from 'express';
import { Request } from 'express-jwt';
import { signJWT, validateWithJWTConfig, verifyJWT } from './auth';
import { HttpError } from './controllers.errors';
import { HTTP_STATUS, userCanAccessSession } from './controllers.utils';
import multer = require('multer');
import path = require('path');
import fs = require('fs');
import mkdirp = require('mkdirp');
import archiver = require('archiver');
import async = require('async');

import config = require('./config');
import models = require('./models');

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
router.post('/session', validateWithJWTConfig(), (req: Request, res: express.Response, next) => {
    if (!req.auth.sub) res.sendStatus(HTTP_STATUS.BAD_REQUEST);

    req.body.status = "created";
    req.body.request_headers = req.headers;
    let session = new models.Session({
        ...req.body,
        ownerId: req.auth.sub,
        allowedUsers: []
    });
    session.save().then((_session) => { //mongoose contains err on the 1st argument of resolve!? odd.
        res.json(_session);
    }).catch((err) => {
        console.error(err)
        return next(err);
    });
});

/**
 * @swagger
 * paths:
 *  /session/{session_id}
 *      patch:
 *          summary: Update users that can access a session
 *          description: This endpoint updates the users for a session
 *          tags:
 *            - Session
 *          parameters:
 *            - in: path
 *              name: session_id
 *              schema:
 *                  type: string
 *              required: true
 *              description: The session ID to update
 *          responses:
 *              200:
 *                  description: Returns the updated session
 *                  content:
 *                      application/json:
 *                          schema:
 *                              $ref: '#/components/schemas/Session'
 *              400:
 *                  description: Bad request
 *              404:
 *                  description: Session not found
 *              500:
 *                  description: Server error
 */
router.patch('/session/:session_id', validateWithJWTConfig(), (req: Request, res: express.Response, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, true).then((session) => {
        session.allowedUsers = req.body.allowedUsers;
        return session.save()
    }).then(() => {
        res.send('ok')
    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    })
})

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
router.get('/session/:session_id', validateWithJWTConfig(), (req: Request, res, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, false).then((session) => {
        res.json(session);
    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    })
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
router.post('/session/:session_id/deface', validateWithJWTConfig(), (req: Request, res, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, false).then((session) => {
        fs.writeFile(`${config.workdir}/${session._id}/deface.json`, JSON.stringify(req.body), (err) => {
            session.status = "deface";
            session.status_msg = "Waiting to be defaced";
            session.save().then(() => {
                res.send("ok");
            }).catch((err) => console.error(err))
        })
    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    })
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
router.post('/session/:session_id/canceldeface', validateWithJWTConfig(), (req: Request, res, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, false).then((session) => {
        fs.writeFile(`${config.workdir}/${session._id}/.cancel`, '', (err) => {
            if (err) console.error(err);

            session.status_msg = "requested to cancel defacing";

            //handler should set the status when the job is killed so this shouldn't
            //be necessary.. but right now kill() doesn't work.. so
            session.deface_begin_date = undefined;
            session.status = "analyzed";
            session.save().then(() => {
                res.send("ok");
            }).catch((err) => console.error(err))
        });
    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    })
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
router.post('/session/:session_id/resetdeface', validateWithJWTConfig(), (req: Request, res, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, false).then((session) => {
        const workdir = `${config.workdir}/${session._id}`;
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
        return session.save();
    }).then(() => {
        res.send("ok");
    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    })
});

router.post('/session/:session_id/finalize', validateWithJWTConfig(), (req: Request, res, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, false).then((session) => {
        fs.writeFile(`${config.workdir}/${session._id}/finalized.json`, JSON.stringify(req.body), (err) => {
            if (err) console.error(err)
            models.ezBIDS.findOneAndUpdate({ _session_id: session._id }, {
                $set: {
                    //TODO - store this somewhere for book keeping
                    //updated: req.body, //finalized.json could exceed 16MB 
                    update_date: new Date(),
                }
            }).then(() => {
                session.status = "finalized";
                session.status_msg = "Waiting to be finalized";
                session.save().then(() => {
                    res.send("ok");
                }).catch((err) => { console.error(err) })
            });
        });
    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    })
});

//download finalized(updated) content
router.get('/session/:session_id/updated', validateWithJWTConfig(), (req: Request, res, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, false).then((session) => {
        return models.ezBIDS.findOne({ _session_id: session._id })
    }).then((ezBIDS) => {
        if (!ezBIDS) {
            res.status(HTTP_STATUS.NOT_FOUND).json({ message: 'no such session or ezBIDS not finalized' })
            return;
        }
        if (!ezBIDS.updated) {
            res.status(HTTP_STATUS.NOT_FOUND).json({ message: 'not yet finalized' })
            return;
        }

        res.status(HTTP_STATUS.OK).json(ezBIDS.updated)
    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    });
});

/**
 * This route exists in order to authenticate users trying to download server files via /download/:session_id/*
 * The user is authenticated via this route, receives a shortlived JWT, and then submits it in the URL here: /download/:session_id/*
 */
router.get('/download/:session_id/token', validateWithJWTConfig(), (req: Request, res, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, false).then((session) => {
        const JWT = signJWT({ sessionId: session._id.toString() });
        res.send(JWT);
    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    });
})

//let user download files within session (like the .png image generated by analyzer)
router.get('/download/:session_id/*', (req, res, next) => {
    const jwt = req?.query?.token as string;
    if (!jwt) {
        res.sendStatus(HTTP_STATUS.BAD_REQUEST)
        return;
    }

    let validJWTPayload;
    try {
        validJWTPayload = verifyJWT(jwt);
    } catch (e) {
        res.sendStatus(HTTP_STATUS.UNAUTHORIZED);
        return;
    }

    models.Session.findById((validJWTPayload as any)?.sessionId).then((session) => {
        const basepath = config.workdir + "/" + session._id;

        //validate path so it will be inside the basepath
        const fullpath = path.resolve(basepath + "/" + req.params[0]);
        if (!fullpath.startsWith(basepath)) return next("invalid path");

        //TODO - if requested path is a file, thenstream 
        const stats = fs.lstatSync(fullpath);
        if (stats.isFile()) {
            res.setHeader('Content-disposition', 'attachment; filename=' + path.basename(fullpath));
            res.setHeader('Access-Control-Expose-Headers', 'Content-Disposition');
            fs.createReadStream(fullpath).pipe(res);
        } else if (stats.isDirectory()) {
            res.setHeader('Content-disposition', 'attachment; filename=' + path.basename(fullpath) + ".zip");
            res.setHeader('Access-Control-Expose-Headers', 'Content-Disposition');
            const archive = archiver('zip', {
                zlib: { level: 0 }
            });
            archive.directory(fullpath, 'bids');
            archive.finalize();
            archive.pipe(res);

        } else next("weird file");
    }).catch((err) => {
        if (err?.code === 'ENOENT') {
            res.status(HTTP_STATUS.NOT_FOUND).json(err);
            return;
        }
        next(err);
    });
});

router.post('/upload-multi/:session_id', validateWithJWTConfig(), upload.any(), (req: any, res, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, false).then(async (session) => {

        //when a single file is uploaded paths becomes just a string. convert it to an array of 1
        let paths = req.body["paths"];
        if (!Array.isArray(paths)) paths = [paths];
        //same for mtimes
        let mtimes = req.body["mtimes"];
        if (!Array.isArray(mtimes)) mtimes = [mtimes];

        let idx = -1;
        async.eachSeries(req.files, (file: any, next_file) => {
            idx++;
            const src_path = file.path;
            const dirty_path = `${config.workdir}/${session._id}/${paths[idx]}`
            const dest_path = path.resolve(dirty_path);
            const mtime = mtimes[idx] / 1000; //browser uses msec.. filesystem uses sec since epoch

            if (!dest_path.startsWith(config.workdir)) return next_file(new Error(`invalid path: ${dest_path}`));
            const destdir = path.dirname(dest_path);

            //move the file over to workdir
            const made = mkdirp.sync(destdir);
            fs.renameSync(src_path, dest_path);
            if (mtime) fs.utimesSync(dest_path, mtime, mtime);
            next_file();
        }, (err) => {
            if (err) return next(err);
            res.send("ok");
        });

    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    });
});

//done uploading.
router.patch('/session/uploaded/:session_id', validateWithJWTConfig(), (req: Request, res, next) => {
    userCanAccessSession(req.params.session_id, req.auth.sub as unknown as number, false).then((session) => {
        session.status = "uploaded";
        session.status_msg = "Waiting in the queue..";
        session.upload_finish_date = new Date();
        return session.save();
    }).then(() => {
        res.send('ok');
    }).catch((err: HttpError) => {
        console.error(err)
        if (err.statusCode) {
            res.sendStatus(err.statusCode);
        } else {
            return next(err)
        }
    });
});

module.exports = router;