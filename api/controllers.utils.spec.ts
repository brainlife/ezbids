let mockAuthentication = false;

jest.mock('./config', () => ({
    get authentication() {
        return mockAuthentication;
    },
}));

jest.mock('./store', () => ({
    sessionStore: {
        findById: jest.fn(),
    },
}));

import { NextFunction, Response } from 'express';
import { HTTP_STATUS, validateUserCanAccessSession, type EzBIDSAuthRequestObject } from './controllers.utils';
import { sessionStore } from './store';
import type { ISessionReturn } from './store/types';

const findByIdMock = sessionStore.findById as jest.MockedFunction<typeof sessionStore.findById>;

function createMockRes(): Response {
    const res = {
        json: jest.fn(),
        send: jest.fn(),
        status: jest.fn(),
    };
    res.status.mockReturnValue(res);
    res.json.mockReturnValue(res);
    res.send.mockReturnValue(res);
    return res as unknown as Response;
}

function sessionFixture(overrides: Partial<ISessionReturn> = {}): ISessionReturn {
    return {
        _id: 'sess-1',
        ownerId: 10,
        allowedUsers: [20, 30],
        ...overrides,
    } as ISessionReturn;
}

describe('controllers.utils', () => {
    beforeEach(() => {
        mockAuthentication = false;
        findByIdMock.mockReset();
    });

    describe('HTTP_STATUS', () => {
        it('exposes expected numeric codes', () => {
            expect(HTTP_STATUS.OK).toBe(200);
            expect(HTTP_STATUS.BAD_REQUEST).toBe(400);
            expect(HTTP_STATUS.UNAUTHORIZED).toBe(401);
            expect(HTTP_STATUS.NOT_FOUND).toBe(404);
            expect(HTTP_STATUS.INTERNAL_SERVER_ERROR).toBe(500);
        });
    });

    describe('validateUserCanAccessSession', () => {
        it('responds 400 when session_id param is missing', async () => {
            const mw = validateUserCanAccessSession(false);
            const req = { params: {}, auth: { sub: 1 } } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(res.status).toHaveBeenCalledWith(HTTP_STATUS.BAD_REQUEST);
            expect(res.json).toHaveBeenCalledWith({ err: 'No sessionId found' });
            expect(next).not.toHaveBeenCalled();
        });

        it('responds 400 when authentication is on and user id is missing', async () => {
            mockAuthentication = true;
            const mw = validateUserCanAccessSession(false);
            const req = { params: { session_id: 's1' }, auth: {} } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(res.status).toHaveBeenCalledWith(HTTP_STATUS.BAD_REQUEST);
            expect(res.json).toHaveBeenCalledWith({ err: 'No userId found' });
            expect(findByIdMock).not.toHaveBeenCalled();
        });

        it('responds 404 when the session does not exist', async () => {
            findByIdMock.mockResolvedValue(null);
            const mw = validateUserCanAccessSession(false);
            const req = { params: { session_id: 'missing' }, auth: { sub: 1 } } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(findByIdMock).toHaveBeenCalledWith('missing');
            expect(res.status).toHaveBeenCalledWith(HTTP_STATUS.NOT_FOUND);
            expect(res.json).toHaveBeenCalledWith({ err: 'Could not find session with ID: missing' });
            expect(next).not.toHaveBeenCalled();
        });

        it('when authentication is off, calls next and attaches session without owner checks', async () => {
            const session = sessionFixture({ ownerId: 99 });
            findByIdMock.mockResolvedValue(session);
            const mw = validateUserCanAccessSession(false);
            const req = { params: { session_id: 'sess-1' }, auth: {} } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(next).toHaveBeenCalledTimes(1);
            expect(req.ezBIDS).toEqual({ session });
            expect(res.status).not.toHaveBeenCalled();
        });

        it('when authentication is on and onlyOwnerCanAccess, allows the owner', async () => {
            mockAuthentication = true;
            findByIdMock.mockResolvedValue(sessionFixture({ ownerId: 5 }));
            const mw = validateUserCanAccessSession(true);
            const req = { params: { session_id: 'sess-1' }, auth: { sub: 5 } } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(next).toHaveBeenCalled();
        });

        it('when authentication is on and onlyOwnerCanAccess, rejects non-owner', async () => {
            mockAuthentication = true;
            findByIdMock.mockResolvedValue(sessionFixture({ ownerId: 5 }));
            const mw = validateUserCanAccessSession(true);
            const req = { params: { session_id: 'sess-1' }, auth: { sub: 99 } } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(res.status).toHaveBeenCalledWith(HTTP_STATUS.UNAUTHORIZED);
            expect(res.json).toHaveBeenCalledWith({ err: 'unauthorized' });
            expect(next).not.toHaveBeenCalled();
        });

        it('when authentication is on and not onlyOwner, allows allowedUsers', async () => {
            mockAuthentication = true;
            findByIdMock.mockResolvedValue(sessionFixture({ ownerId: 1, allowedUsers: [42] }));
            const mw = validateUserCanAccessSession(false);
            const req = { params: { session_id: 'sess-1' }, auth: { sub: 42 } } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(next).toHaveBeenCalled();
        });

        it('when authentication is on and not onlyOwner, allows the owner even if not in allowedUsers', async () => {
            mockAuthentication = true;
            findByIdMock.mockResolvedValue(sessionFixture({ ownerId: 7, allowedUsers: [] }));
            const mw = validateUserCanAccessSession(false);
            const req = { params: { session_id: 'sess-1' }, auth: { sub: 7 } } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(next).toHaveBeenCalled();
        });

        it('when authentication is on and not onlyOwner, rejects user who is neither owner nor allowed', async () => {
            mockAuthentication = true;
            findByIdMock.mockResolvedValue(sessionFixture({ ownerId: 1, allowedUsers: [2] }));
            const mw = validateUserCanAccessSession(false);
            const req = { params: { session_id: 'sess-1' }, auth: { sub: 3 } } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(res.status).toHaveBeenCalledWith(HTTP_STATUS.UNAUTHORIZED);
            expect(next).not.toHaveBeenCalled();
        });

        it('responds 500 when findById rejects', async () => {
            const errSpy = jest.spyOn(console, 'error').mockImplementation(jest.fn());
            findByIdMock.mockRejectedValue(new Error('db down'));
            const mw = validateUserCanAccessSession(false);
            const req = { params: { session_id: 's1' }, auth: { sub: 1 } } as unknown as EzBIDSAuthRequestObject;
            const res = createMockRes();
            const next = jest.fn() as NextFunction;

            await mw(req, res, next);

            expect(errSpy).toHaveBeenCalled();
            expect(res.status).toHaveBeenCalledWith(HTTP_STATUS.INTERNAL_SERVER_ERROR);
            expect(res.send).toHaveBeenCalledWith({ err: 'internal server error' });
            expect(next).not.toHaveBeenCalled();
            errSpy.mockRestore();
        });
    });
});
