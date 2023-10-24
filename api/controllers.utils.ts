import { BadRequestHttpError, NotFoundHttpError, UnauthorizedHttpError } from './controllers.errors';
import { Session } from './models';

export enum STATUS {
    OK = 'ok'
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