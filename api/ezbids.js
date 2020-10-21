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
//init express
const app = express();
//app.options('*', cors()) // include before other routes
/*
var whitelist = ['http://localhost:3000', 'http://localhost:8080', 'http://localhost:8081', 'https://dev1.soichi.us']
var corsOptionsDelegate = function (req, callback) {
  var corsOptions;
  if (whitelist.indexOf(req.header('Origin')) !== -1) {
    corsOptions = { origin: true } // reflect (enable) the requested origin in the CORS response
  } else {
    corsOptions = { origin: false } // disable CORS for this request
  }
  console.dir(req.header('Origin'));
  console.dir(corsOptions);
  callback(null, corsOptions) // callback expects two parameters: error and options
}
app.use(cors(corsOptionsDelegate));
*/
//app.use(express.json({ limit: 10*1000000 })); //file list from session might be quite large..
app.use(cors());
app.use(compression());
app.use(nocache());
/*
app.use(fileupload({
    useTempFiles : true,
    tempFileDir : '/tmp/'
}));
*/
//app.disable('etag'); //to speed things up, but I really haven't noticed much difference
app.disable('x-powered-by'); //for better security?
//parse application/json
app.use(bodyParser.urlencoded({
    //parameterLimit: 100000,
    limit: '50mb',
    extended: true
}));
app.use(bodyParser.json({
    limit: '50mb',
    type: "application/json",
}));
//app.use(expressWinston.logger(config.logger.winston));
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