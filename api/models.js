"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const mongoose = require("mongoose");
const config = require("./config");
if (config.mongoose_debug)
    mongoose.set("debug", true);
function connect(cb) {
    console.debug("connecting to mongo");
    mongoose.connect(config.mongodb, {
        useNewUrlParser: true,
        useUnifiedTopology: true,
    }, err => {
        if (err)
            return cb(err);
        console.log("connected to mongo");
        cb();
    });
}
exports.connect = connect;
function disconnect(cb) {
    mongoose.disconnect(cb);
}
exports.disconnect = disconnect;
///////////////////////////////////////////////////////////////////////////////////////////////////
//
// upload sessions
//
var sessionSchema = mongoose.Schema({
    create_date: { type: Date, default: Date.now },
    request_headers: mongoose.Schema.Types.Mixed,
    upload_finish_date: Date,
    pre_begin_date: Date,
    pre_finish_date: Date,
    status: String,
    //created
    //uploaded (waiting to be preprocessed)
    //preprocessing
    //analyzed
    //finalized
    //finished
    //failed
    //dcm2niix status
    dicomCount: Number,
    dicomDone: Number,
    status_msg: String,
});
exports.Session = mongoose.model("Session", sessionSchema);
var ezbidsSchema = mongoose.Schema({
    _session_id: mongoose.Schema.Types.ObjectId,
    original: mongoose.Schema.Types.Mixed,
    updated: mongoose.Schema.Types.Mixed,
    create_date: { type: Date, default: Date.now },
    update_date: { type: Date },
});
exports.ezBIDS = mongoose.model("ezBIDS", ezbidsSchema);
//# sourceMappingURL=models.js.map