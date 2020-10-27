
import mongoose = require("mongoose");
import config  = require("./config");

if(config.mongoose_debug) mongoose.set("debug", true);

export function connect(cb) {
    console.debug("connecting to mongo");
    mongoose.connect(config.mongodb, {
        useNewUrlParser: true,
        useUnifiedTopology: true,
    }, err=>{
        if(err) return cb(err);
        console.log("connected to mongo");
        cb();
    });
}

export function disconnect(cb) {
    mongoose.disconnect(cb);
}

///////////////////////////////////////////////////////////////////////////////////////////////////
//
// upload sessions
//

var sessionSchema = mongoose.Schema({

    create_date: { type: Date, default: Date.now },
    update_date: { type: Date, default: Date.now },

    request_headers: mongoose.Schema.Types.Mixed,

    upload_finish_date: Date, //when all files are uploaded

    pre_begin_date: Date, //when preprocessing is started
    pre_finish_date: Date, //when preprocessing is finished

    status: String, //just message to show to the user
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
sessionSchema.pre('save', function(next) {
    this.update_date = Date.now();
    next();
});
export let Session = mongoose.model("Session", sessionSchema);

var ezbidsSchema = mongoose.Schema({
    _session_id: mongoose.Schema.Types.ObjectId, 

    original: mongoose.Schema.Types.Mixed,
    updated: mongoose.Schema.Types.Mixed,

    create_date: { type: Date, default: Date.now },
    update_date: { type: Date },
});
export let ezBIDS = mongoose.model("ezBIDS", ezbidsSchema);


