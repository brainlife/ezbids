import { NextFunction, Response } from 'express';
import { Request } from 'express-jwt';
import { ISession, Session } from './models';
import { Types, Document } from 'mongoose';
import * as config from './config';

export enum HTTP_STATUS {
    OK = 200,
    BAD_REQUEST = 400,
    UNAUTHORIZED = 401,
    NOT_FOUND = 404,
    INTERNAL_SERVER_ERROR = 500,
}

export type EzBIDSAuthRequestObject = Request & {
    ezBIDS: {
        session: Document<unknown, any, ISession> &
            Omit<
                ISession & {
                    _id: Types.ObjectId;
                },
                never
            >;
    };
};

export const validateUserCanAccessSession = (onlyOwnerCanAccess: boolean) => {
    return (req: EzBIDSAuthRequestObject, res: Response, next: NextFunction) => {
        const sessionId = req.params.session_id;
        const userId = req.auth.sub as unknown as number;

        if (!sessionId) {
            return res.status(HTTP_STATUS.BAD_REQUEST).json({ err: 'No sessionId found' });
        }

        if (config.authentication && !userId) {
            return res.status(HTTP_STATUS.BAD_REQUEST).json({ err: 'No userId found' });
        }

        return Session.findById(sessionId)
            .then((session) => {
                if (!session)
                    return res
                        .status(HTTP_STATUS.NOT_FOUND)
                        .json({ err: 'Could not find session with ID: ' + sessionId });

                if (config.authentication) {
                    const isOwner = userId === (session.ownerId || '');
                    const isInAllowedUserList = session.allowedUsers.some((allowedUser) => allowedUser === userId);

                    if (onlyOwnerCanAccess && !isOwner) {
                        return res.status(HTTP_STATUS.UNAUTHORIZED).json({ err: 'unauthorized' });
                    } else if (!onlyOwnerCanAccess && !isOwner && !isInAllowedUserList) {
                        return res.status(HTTP_STATUS.UNAUTHORIZED).json({ err: 'unauthorized' });
                    }
                }

                req.ezBIDS = {
                    session,
                };
                return next();
            })
            .catch((err) => {
                console.error(err);
                return res.status(HTTP_STATUS.INTERNAL_SERVER_ERROR).send({ err: 'internal server error' });
            });
    };
};
