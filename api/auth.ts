import { Params, expressjwt } from 'express-jwt';
import * as fs from 'fs';
import * as jwt from 'jsonwebtoken';
import * as config from './config';

const pubkey = config.authentication ? fs.readFileSync(__dirname + '/auth.pub', 'ascii').trim() : null;
const tryReadKey = (path: string): string | null => {
    if (!fs.existsSync(path)) return null;
    return fs.readFileSync(path, 'ascii').trim();
};

const ezbidsPrivateKey = tryReadKey(`${__dirname}/ezbids.key`);
const ezbidsPublicKey = tryReadKey(`${__dirname}/ezbids.pub`);

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

    if (config.authentication) {
        if (!ezbidsPublicKey) throw new Error('missing ezbids public key');
        return jwt.verify(jwtToVerify, ezbidsPublicKey, { algorithms: ['RS256'] });
    } else {
        return jwt.verify(jwtToVerify, 'mock-key', { algorithms: ['HS256'] });
    }
};

export const signJWT = (claims: { sessionId: string }, signInOpts?: jwt.SignOptions) => {
    if (config.authentication) {
        if (!ezbidsPrivateKey) throw new Error('missing ezbids private key');
        return jwt.sign(claims, ezbidsPrivateKey, {
            algorithm: 'RS256',
            expiresIn: '600s',
            ...(signInOpts || {}),
        });
    } else {
        return jwt.sign(claims, 'mock-key', {
            algorithm: 'HS256',
            expiresIn: '600s',
            ...(signInOpts || {}),
        });
    }
};
