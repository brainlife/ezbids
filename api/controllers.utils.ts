import { BadRequestHttpError, NotFoundHttpError, UnauthorizedHttpError } from './controllers.errors';
import { Session } from './models';

export enum HTTP_STATUS {
    OK = 200,
    BAD_REQUEST = 400,
    UNAUTHORIZED = 401,
    NOT_FOUND = 404,
    INTERNAL_SERVER_ERROR = 500
}

export const userCanAccessSession = (sessionId: string, userId: number, onlyOwnerCanAccess: boolean) => {
    if (!sessionId || !userId) return Promise.reject(new BadRequestHttpError('bad request'))
    return Session.findById(sessionId).then((session) => {
        if (!session) throw new NotFoundHttpError('could not find session with ID: ' + sessionId);

        const isOwner = userId === (session.ownerId || '');
        const isInAllowedUserList = session.allowedUsers.some((allowedUser) => allowedUser === userId);

        if (onlyOwnerCanAccess && !isOwner) {
            throw new UnauthorizedHttpError('unauthorized user');
        } else if (!onlyOwnerCanAccess && !isOwner && !isInAllowedUserList) {
            throw new UnauthorizedHttpError('unauthorized user')
        }

        return session
    })
}