#!/usr/bin/node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express = require("express");
const bodyParser = require("body-parser");
const compression = require("compression");
const cors = require("cors");
const nocache = require("nocache");
const models = require("./models");
const config = require("./config");
//import sendSeekable = require('send-seekable');
//init express
const app = express();
app.use(cors());
app.use(compression());
app.use(nocache());
//app.use(sendSeekable);
app.disable('x-powered-by'); //for better security?
app.use(bodyParser.urlencoded({
    limit: '50gb',
    extended: true
}));
app.use(bodyParser.json({
    limit: '50mb',
    type: "application/json",
}));
app.use('/', require('./controllers'));
//error handling
//app.use(expressWinston.errorLogger(config.logger.winston)); 
app.use(function (err, req, res, next) {
    if (typeof err == "string")
        err = { message: err };
    if (!err.name || err.name != "UnauthorizedError") {
        console.error(err);
    }
    if (err.stack)
        err.stack = "hidden"; //don't sent call stack to UI - for security reason
    res.status(err.status || 500);
    res.json(err);
});
process.on('uncaughtException', err => {
    //TODO report this to somewhere!
    console.error((new Date).toUTCString() + ' uncaughtException:', err.message);
    console.error(err.stack);
});
models.connect(err => {
    if (err)
        throw err;
    var port = process.env.PORT || config.express.port || '8081';
    var host = process.env.HOST || config.express.host || 'localhost';
    var server = app.listen(port, host, function () {
        console.log("warehouse api service running on %s:%d in %s mode", host, port, app.settings.env);
    });
});
//increase timeout for dataset download .. (default 120s)
//without this, places like nki/s3 will timeout
//server.timeout = 300*1000; 
//# sourceMappingURL=ezbids.js.map