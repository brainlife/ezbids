'use strict';
exports.mongodb = "mongodb://mongodb:27017/ezbids";
exports.mongoose_debug = true;
//multer incoming upload directory
exports.multer = {
    dest: "/tmp/upload",
}
//directory to copy uploaded files (it needs to be on the same filesystem as multer incoming dir)
exports.workdir = "/tmp/ezbids-workdir",
exports.express = {
    host: "0.0.0.0",
    port: 8082,
}