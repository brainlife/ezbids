"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const mongoose = require("mongoose");
const config = require("./config");
console.dir(mongoose);
if (config.mongoose_debug)
    mongoose.set("debug", true);
function connect(cb) {
    console.debug("connecting to mongo");
    mongoose.connect(config.mongodb, {
        useNewUrlParser: true,
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
    upload_finish_date: Date,
    pre_begin_date: Date,
    pre_finish_date: Date,
    status: String,
    //created
    //uploaded (waiting to be preprocessed)
    //preprocessing
    //validating (waiting to be validated by the user)
    //failed
    status_msg: String,
});
exports.Session = mongoose.model("Session", sessionSchema);
//# sourceMappingURL=models.js.map