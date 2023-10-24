
import { set, connect as mongooseConnect, disconnect as mongooseDisconnect, CallbackWithoutResult, Schema, model } from "mongoose";
import { mongodb, mongoose_debug } from "./config"

if (mongoose_debug) set("debug", true);

export function connect(cb: CallbackWithoutResult) {
    console.debug("connecting to mongo via: " + mongodb);
    mongooseConnect(mongodb, {
        /* this really screwed up warehouse db..
        readPreference: 'nearest',
        writeConcern: {
            w: 'majority', //isn't this the default?
        },
        readConcernLevel: 'majority',//prevents read to grab stale data from secondary
        */
        //auto_reconnect: true, //isn't this the default?
    }, err => {
        if (err) return cb(err);
        console.log("connected to mongo via: " + mongodb);
        cb(null);
    });
}

export function disconnect(cb) {
    mongooseDisconnect(cb);
}

///////////////////////////////////////////////////////////////////////////////////////////////////
//
// upload sessions
//

var sessionSchema = new Schema({

    create_date: { type: Date, default: Date.now },
    update_date: { type: Date, default: Date.now },

    ownerId: Schema.Types.Number,
    allowedUsers: [Schema.Types.Number],

    request_headers: Schema.Types.Mixed,

    upload_finish_date: Date, //when all files are uploaded

    pre_begin_date: Date, //when preprocessing is started
    pre_finish_date: Date, //when preprocessing is finished

    deface_begin_date: Date,
    deface_finish_date: Date,

    finalize_begin_date: Date,
    finalize_finish_date: Date,

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
sessionSchema.pre('save', function (next) {
    this.update_date = new Date()
    next();
});
export let Session = model("Session", sessionSchema);

var ezbidsSchema = new Schema({
    _session_id: Schema.Types.ObjectId,

    original: Schema.Types.Mixed,
    updated: Schema.Types.Mixed,

    create_date: { type: Date, default: Date.now },
    update_date: { type: Date },
});
export let ezBIDS = model("ezBIDS", ezbidsSchema);


