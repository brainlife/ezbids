import mongoose from "mongoose";

if (process.env.MONGOOSE_DEBUG === 'true') mongoose.set("debug", true);

export function connect(cb) {
    console.debug("connecting to mongo");
    mongoose.connect(process.env.MONGO_URL, {}, err=>{
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

const sessionSchema = new mongoose.Schema({

    create_date: { type: Date, default: Date.now },
    update_date: { type: Date, default: Date.now },

    request_headers: mongoose.Schema.Types.Mixed,

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
sessionSchema.pre('save', function(next) {
    this.update_date = new Date(Date.now());
    next();
});
export const Session = mongoose.model("Session", sessionSchema);

const ezbidsSchema = new mongoose.Schema({
    _session_id: mongoose.Schema.Types.ObjectId, 

    original: mongoose.Schema.Types.Mixed,
    updated: mongoose.Schema.Types.Mixed,

    create_date: { type: Date, default: Date.now },
    update_date: { type: Date },
});
export const ezBIDS = mongoose.model("ezBIDS", ezbidsSchema);


