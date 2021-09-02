"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ezBIDS = exports.Session = exports.disconnect = exports.connect = void 0;
const mongoose = require("mongoose");
const config = require("./config");
if (config.mongoose_debug)
    mongoose.set("debug", true);
function connect(cb) {
    console.debug("connecting to mongo");
    mongoose.connect(config.mongodb, {
        readPreference: 'nearest',
        useNewUrlParser: true,
        useUnifiedTopology: true,
        auto_reconnect: true, //isn't this the default?
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
    update_date: { type: Date, default: Date.now },
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
    //bidsing
    //finished
    //failed
    //dcm2niix status
    dicomCount: Number,
    dicomDone: Number,
    status_msg: String,
    /*
    files: [{
        idx: Number,
        name: String,
        size: Number,
        path: String,
        _upload: Object, //set when the file is uploaded.. just to store some extra information from multer
    }],
    */
    //workdir: String, //directory containing uploaded file structure
    //removed: { type: Boolean, default: false },
});
sessionSchema.pre('save', function (next) {
    this.update_date = Date.now();
    next();
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