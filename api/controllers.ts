
import express = require('express');
import multer  = require('multer');
import path = require('path');
import fs = require('fs');
import mkdirp = require('mkdirp');

import config = require('./config');
import models = require('./models');
import { isFunction } from 'util';
import { fstat } from 'fs';

const upload = multer(config.multer);

const router = express.Router();

var storage = multer.diskStorage({
    destination: function (req, file, cb) {
      cb(null, path.join(__dirname,'/uploads'))
    },
    filename: function (req, file, cb) {
      console.log("file",file);
      let fileExtension = file.originalname.split('.')[1]
      cb(null, file.fieldname + '-' + Date.now()+'.'+fileExtension)
    }
})

router.post('/session', (req, res, next)=>{
    //console.log("new session");
    //console.dir(req.body);
    //res.json({id: "123"}); //TODO - should be some random ID
    req.body.status = "created";
    let session = new models.Session(req.body);
    session.save().then(_session=>{ //mongoose contains err on the 1st argument of resolve!? odd.
        console.log("created session");
        res.json(_session);
    }).catch(err=>{
        next(err);
    });
});

router.get('/session/:session_id', (req, res, next) => {
    models.Session.findById(req.params.session_id).select('-files').then(session=>{
        res.json(session);
    }).catch(err=>{
        next(err);
    });
});

router.get('/session/:session_id/log', (req, res, next) => {
    models.Session.findById(req.params.session_id).select('-files').then(session=>{
        res.setHeader("content-type", "text/plain");
        fs.createReadStream(config.workdir+"/"+session._id+"/preprocess.log").pipe(res);
    }).catch(err=>{
        next(err);
    });
});

router.get('/session/:session_id/error', (req, res, next) => {
    models.Session.findById(req.params.session_id).select('-files').then(session=>{
        res.setHeader("content-type", "text/plain");
        fs.createReadStream(config.workdir+"/"+session._id+"/preprocess.err").pipe(res);
    }).catch(err=>{
        next(err);
    });
});

router.get('/session/:session_id/list', (req, res, next) => {
    models.Session.findById(req.params.session_id).select('-files').then(session=>{
        res.setHeader("content-type", "text/plain");
        fs.createReadStream(config.workdir+"/"+session._id+"/list").pipe(res);
    }).catch(err=>{
        next(err);
    });
});

router.get('/session/:session_id/ezbids', (req, res, next) => {
    models.Session.findById(req.params.session_id).select('-files').then(session=>{
        res.setHeader("content-type", "application/json");
        console.debug("loading ezbids.json from", config.workdir, session._id);
        fs.createReadStream(config.workdir+"/"+session._id+"/ezBIDS.json").pipe(res);
    }).catch(err=>{
        next(err);
    });
});

router.patch('/session/:session_id/finalize', (req, res, next)=>{
    models.Session.findById(req.params.session_id).then(session=>{
        if(!session) return next("no such session");
        console.log("streaming");
        req.pipe(fs.createWriteStream(config.workdir+"/"+session._id+"/finalized.json"));
        req.on('end', ()=>{
            session.status = "finalized";
            session.save().then(()=>{
                res.send("ok"); 
            });
        });
    }).catch(err=>{
        console.error(err);
        next(err);
    });
});

router.post('/upload/:session_id/:file_idx', upload.single('file'), (req, res, next)=>{
    //console.debug(req.file);
    /* req.file
    { fieldname: 'file',
      originalname: 'variety-copied-wallpaper-d7b0306b3be73a3227d1ae869f08f7aa.jpg',
      encoding: '7bit',
      mimetype: 'image/jpeg',
      destination: '/tmp',
      filename: 'ae91ece10c00b5007f96c934e09169c9',
      path: '/tmp/ae91ece10c00b5007f96c934e09169c9',
      size: 5951638 }
    */
    models.Session.find({ _id: req.params.session_id, }, {files: {$elemMatch: {idx: parseInt(req.params.file_idx)}} }).then(sessions=>{
        if(sessions.length == 0) return next("no such session");
        let session = sessions[0];
        let src_path = req.file.path;
        let dirty_path = config.workdir+"/"+req.params.session_id+"/"+session.files[0].path;
        let dest_path = path.resolve(dirty_path);

        if(!dest_path.startsWith(config.workdir)) return next("invalid path");
        let destdir = path.dirname(dest_path);
        //console.log(src_path, abs_dest_path, abs_dest_basepath);

        //move the file over to workdir
        mkdirp(destdir).then(err=>{
            fs.rename(src_path, dest_path, err=>{
                if(err) return next(err);
                //update session with some extra info
                models.Session.update({ _id: req.params.session_id, "files.idx": req.params.file_idx}, 
                    {$set: {
                        "files.$._upload": req.file, 
                        "files.$._workpath": dest_path,
                    }}
                ).then(err=>{
                    res.send("ok");
                });
            });
        });

    }).catch(err=>{
        console.error(err);
        next(err);
    });
});

//done uploading.
router.patch('/session/uploaded/:session_id', (req, res, next)=>{
    //let workdir = config.workdir+"/"+req.params.session_id;
    models.Session.findByIdAndUpdate(req.params.session_id, {status: "uploaded", upload_finish_date: new Date()}).then(session=>{
        if(!session) return next("no such session");
        console.log("done");
        res.send("ok");
    }).catch(err=>{
        console.error(err);
        next(err);
    });
});

module.exports = router;

