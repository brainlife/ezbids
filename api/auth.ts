import { Params, expressjwt } from "express-jwt";
import * as fs from 'fs';

const pubkey = fs.readFileSync(__dirname + "/auth.pub", "ascii").trim();

export const validateWithJWTConfig = (options?: Params) => {
    return expressjwt({
        secret: pubkey,
        algorithms: ['RS256'],
        ...options
    })
};

// for validating jwt tokens