import * as express from 'express';
import { Request } from 'express-jwt';
import { JwtPayload } from 'jsonwebtoken';
import { signJWT, validateWithJWTConfig, verifyJWT } from './auth';
import { EzBIDSAuthRequestObject, HTTP_STATUS, validateUserCanAccessSession } from './controllers.utils';
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
router.get('/health', (req, res) => {
    let status = 'ok';
    let message = '';

    //check to see if we can access the workdir
    try {
        fs.writeFileSync(config.workdir + '/health.txt', 'test');
    } catch (err) {
        status = 'failed';
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
    req.body.status = 'created';
    req.body.request_headers = req.headers;

    const session = new models.Session({
        ...req.body,
        ownerId: req.auth.sub,
        allowedUsers: [],
    });
    session
        .save()
        .then((_session) => {
            //mongoose contains err on the 1st argument of resolve!? odd.
            res.json(_session);
        })
        .catch((err) => {
            console.error(err);
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
router.patch(
    '/session/:session_id',
    validateWithJWTConfig(),
    validateUserCanAccessSession(true),
    (req: EzBIDSAuthRequestObject, res, next) => {
        const session = req.ezBIDS.session;
        session.allowedUsers = req.body.allowedUsers;
        return session
            .save()
            .then(() => {
                res.send('ok');
            })
            .catch((err) => {
                return next(err);
            });
    }
);

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
router.get(
    '/session/:session_id',
    validateWithJWTConfig(),
    validateUserCanAccessSession(false),
    (req: EzBIDSAuthRequestObject, res) => {
        return res.json(req.ezBIDS.session);
    }
);

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
router.post(
    '/session/:session_id/deface',
    validateWithJWTConfig(),
    validateUserCanAccessSession(false),
    (req: EzBIDSAuthRequestObject, res, next) => {
        const session = req.ezBIDS.session;
        fs.writeFile(`${config.workdir}/${session._id}/deface.json`, JSON.stringify(req.body), () => {
            session.status = 'deface';
            session.status_msg = 'Waiting to be defaced';
            session
                .save()
                .then(() => {
                    return res.send('ok');
                })
                .catch((err) => next(err));
        });
    }
);

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
router.post(
    '/session/:session_id/canceldeface',
    validateWithJWTConfig(),
    validateUserCanAccessSession(false),
    (req: EzBIDSAuthRequestObject, res, next) => {
        const session = req.ezBIDS.session;

        fs.writeFile(`${config.workdir}/${session._id}/.cancel`, '', (err) => {
            if (err) console.error(err);

            session.status_msg = 'requested to cancel defacing';

            //handler should set the status when the job is killed so this shouldn't
            //be necessary.. but right now kill() doesn't work.. so
            session.deface_begin_date = undefined;
            session.status = 'analyzed';
            session
                .save()
                .then(() => {
                    return res.send('ok');
                })
                .catch((err) => next(err));
        });
    }
);

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
router.post(
    '/session/:session_id/resetdeface',
    validateWithJWTConfig(),
    validateUserCanAccessSession(false),
    (req: EzBIDSAuthRequestObject, res, next) => {
        const session = req.ezBIDS.session;

        const workdir = `${config.workdir}/${session._id}`;
        if (fs.existsSync(workdir + '/deface.finished')) {
            fs.unlinkSync(workdir + '/deface.finished');
        }
        if (fs.existsSync(workdir + '/deface.failed')) {
            fs.unlinkSync(workdir + '/deface.failed');
        }
        session.status = 'analyzed';
        session.status_msg = 'reset defacing';
        session.deface_begin_date = undefined;
        session.deface_finish_date = undefined;
        session
            .save()
            .then(() => {
                return res.send('ok');
            })
            .catch((err) => next(err));
    }
);

router.post(
    '/session/:session_id/finalize',
    validateWithJWTConfig(),
    validateUserCanAccessSession(false),
    (req: EzBIDSAuthRequestObject, res, next) => {
        const session = req.ezBIDS.session;

        fs.writeFile(`${config.workdir}/${session._id}/finalized.json`, JSON.stringify(req.body), (err) => {
            if (err) console.error(err);
            models.ezBIDS
                .findOneAndUpdate(
                    { _session_id: session._id },
                    {
                        $set: {
                            //TODO - store this somewhere for book keeping
                            //updated: req.body, //finalized.json could exceed 16MB
                            update_date: new Date(),
                        },
                    }
                )
                .then(() => {
                    session.status = 'finalized';
                    session.status_msg = 'Waiting to be finalized';
                    session
                        .save()
                        .then(() => {
                            res.send('ok');
                        })
                        .catch((err) => next(err));
                })
                .catch((err) => next(err));
        });
    }
);

//download finalized(updated) content
router.get(
    '/session/:session_id/updated',
    validateWithJWTConfig(),
    validateUserCanAccessSession(false),
    (req: EzBIDSAuthRequestObject, res, next) => {
        const session = req.ezBIDS.session;

        models.ezBIDS
            .findOne({ _session_id: session._id })
            .then((ezBIDS) => {
                if (!ezBIDS) {
                    return res
                        .status(HTTP_STATUS.NOT_FOUND)
                        .json({ message: 'no such session or ezBIDS not finalized' });
                }

                if (!ezBIDS.updated) {
                    return res.status(HTTP_STATUS.NOT_FOUND).json({ message: 'not yet finalized' });
                }

                return res.status(HTTP_STATUS.OK).json(ezBIDS.updated);
            })
            .catch((err) => next(err));
    }
);

/**
 * This route exists in order to authenticate users trying to download server files via /download/:session_id/*
 * The user is authenticated via this route, receives a shortlived JWT, and then submits it in the URL here: /download/:session_id/*
 */
router.get(
    '/download/:session_id/token',
    validateWithJWTConfig(),
    validateUserCanAccessSession(false),
    (req: EzBIDSAuthRequestObject, res) => {
        const session = req.ezBIDS.session;
        const JWT = signJWT({ sessionId: session._id.toString() });
        return res.send(JWT);
    }
);

//let user download files within session (like the .png image generated by analyzer)
router.get('/download/:session_id/*', (req, res, next) => {
    const jwt = req?.query?.token as string;
    if (!jwt) {
        res.sendStatus(HTTP_STATUS.BAD_REQUEST);
        return;
    }

    let validJWTPayload;
    try {
        validJWTPayload = verifyJWT(jwt) as JwtPayload;
        if (validJWTPayload === undefined) throw new Error('invalid - did not receive a jwt to verify');
    } catch (e) {
        res.sendStatus(HTTP_STATUS.UNAUTHORIZED);
        return;
    }

    models.Session.findById(validJWTPayload?.sessionId)
        .then((session) => {
            const basepath = config.workdir + '/' + session._id;

            //validate path so it will be inside the basepath
            const fullpath = path.resolve(basepath + '/' + req.params[0]);
            if (!fullpath.startsWith(basepath)) return next('invalid path');

            //TODO - if requested path is a file, thenstream
            const stats = fs.lstatSync(fullpath);
            if (stats.isFile()) {
                res.setHeader('Content-disposition', 'attachment; filename=' + path.basename(fullpath));
                res.setHeader('Access-Control-Expose-Headers', 'Content-Disposition');
                return fs.createReadStream(fullpath).pipe(res);
            } else if (stats.isDirectory()) {
                res.setHeader('Content-disposition', 'attachment; filename=' + path.basename(fullpath) + '.zip');
                res.setHeader('Access-Control-Expose-Headers', 'Content-Disposition');
                const archive = archiver('zip', {
                    zlib: { level: 0 },
                });
                archive.directory(fullpath, 'bids');
                archive.finalize();
                return archive.pipe(res);
            } else return next('weird file');
        })
        .catch((err) => {
            if (err?.code === 'ENOENT') {
                return res.status(HTTP_STATUS.NOT_FOUND).json(err);
            } else {
                return next(err);
            }
        });
});

router.post(
    '/upload-multi/:session_id',
    validateWithJWTConfig(),
    validateUserCanAccessSession(false),
    upload.any(),
    (req: any, res, next) => {
        const session = req.ezBIDS.session;

        //when a single file is uploaded paths becomes just a string. convert it to an array of 1
        let paths = req.body.paths;
        if (!Array.isArray(paths)) paths = [paths];
        //same for mtimes
        let mtimes = req.body.mtimes;
        if (!Array.isArray(mtimes)) mtimes = [mtimes];

        let idx = -1;
        async.eachSeries(
            req.files,
            (file: any, nextFile) => {
                idx++;
                const srcPath = file.path;
                const dirtyPath = `${config.workdir}/${session._id}/${paths[idx]}`;
                const destPath = path.resolve(dirtyPath);
                const mtime = mtimes[idx] / 1000; //browser uses msec.. filesystem uses sec since epoch

                if (!destPath.startsWith(config.workdir)) {
                    return nextFile(new Error(`invalid path: ${destPath}`));
                }
                const destdir = path.dirname(destPath);

                //move the file over to workdir
                mkdirp.sync(destdir);
                fs.renameSync(srcPath, destPath);
                if (mtime) fs.utimesSync(destPath, mtime, mtime);
                return nextFile();
            },
            (err) => {
                if (err) return next(err);
                return res.send('ok');
            }
        );
    }
);

//done uploading.
router.patch(
    '/session/uploaded/:session_id',
    validateWithJWTConfig(),
    validateUserCanAccessSession(false),
    (req: EzBIDSAuthRequestObject, res, next) => {
        const session = req.ezBIDS.session;
        session.status = 'uploaded';
        session.status_msg = 'Waiting in the queue..';
        session.upload_finish_date = new Date();
        session
            .save()
            .then(() => {
                return res.send('ok');
            })
            .catch((err) => {
                return next(err);
            });
    }
);

module.exports = router;
