import { Params, expressjwt } from 'express-jwt';
import * as fs from 'fs';
import * as jwt from 'jsonwebtoken';

const pubkey = fs.readFileSync(__dirname + '/auth.pub', 'ascii').trim();
const ezbidsPrivateKey = fs.readFileSync(`${__dirname}/ezbids.key`, 'ascii').trim();
const ezbidsPublicKey = fs.readFileSync(`${__dirname}/ezbids.pub`, 'ascii').trim();
export const validateWithJWTConfig = (options?: Params) => {
    return expressjwt({
        secret: pubkey,
        algorithms: ['RS256'],
        ...options,
    });
};

export const verifyJWT = (jwtToVerify?: string): string | jwt.JwtPayload | undefined => {
    if (!jwtToVerify) return undefined;
    return jwt.verify(jwtToVerify, ezbidsPublicKey, { algorithms: ['RS256'] });
};

export const signJWT = (claims: { sessionId: string }, signInOpts?: jwt.SignOptions) => {
    return jwt.sign(claims, ezbidsPrivateKey, {
        algorithm: 'RS256',
        expiresIn: '10s',
        ...(signInOpts || {}),
    });
};
