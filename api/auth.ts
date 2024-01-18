import { Params, expressjwt } from 'express-jwt';
import * as fs from 'fs';
import * as jwt from 'jsonwebtoken';
import * as config from './config';

const pubkey = config.authentication ? fs.readFileSync(__dirname + '/auth.pub', 'ascii').trim() : null;
const ezbidsPrivateKey = fs.readFileSync(`${__dirname}/ezbids.key`, 'ascii').trim();
const ezbidsPublicKey = fs.readFileSync(`${__dirname}/ezbids.pub`, 'ascii').trim();

export const validateWithJWTConfig = (options?: Params) => {
    if (config.authentication) {
        return expressjwt({
            secret: pubkey,
            algorithms: ['RS256'],
            ...options,
        });
    } else {
        return (req: any, res: any, next: any) => {
            req.auth = {
                sub: 0,
            };

            next();
        };
    }
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
