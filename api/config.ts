'use strict';
export const mongodb = process.env.MONGO_CONNECTION_STRING || "mongodb://mongodb:27017/ezbids";
export const mongoose_debug = true;
//multer incoming upload directory
export const multer = {
    dest: "/tmp/upload",
}
//directory to copy uploaded files (it needs to be on the same filesystem as multer incoming dir)
export const workdir = "/tmp/ezbids-workdir";
export const express = {
    host: "0.0.0.0",
    port: '8082',
}