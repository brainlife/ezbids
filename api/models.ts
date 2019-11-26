
import mongoose = require("mongoose");
import config  = require("./config");

console.dir(mongoose);
if(config.mongoose_debug) mongoose.set("debug", true);

export function connect(cb) {
    console.debug("connecting to mongo");
    mongoose.connect(config.mongodb, {
        useNewUrlParser: true,
        
        //TODO - isn't auto_reconnect set by default?
        //auto_reconnect: true, 
        //reconnectTries: Number.MAX_VALUE
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
    upload_finish_date: Date, //when all files are uploaded

    pre_begin_date: Date, //when preprocessing is started
    pre_finish_date: Date, //when preprocessing is finished

    status: String, //just message to show to the user
    //created
    //uploaded (waiting to be preprocessed)
    //preprocessing
    //validating (waiting to be validated by the user)

    //failed


    status_msg: String,

    files: [{
        idx: Number,
        name: String,
        size: Number, 
        path: String,      
        _upload: Object, //set when the file is uploaded.. just to store some extra information from multer
    }],

    //workdir: String, //directory containing uploaded file structure

    //removed: { type: Boolean, default: false },
});
export let Session = mongoose.model("Session", sessionSchema);

