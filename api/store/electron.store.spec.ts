type SessionDoc = {
    _id: string;
    status: string;
    ownerId?: number;
    allowedUsers?: number[];
    status_msg?: string;
    dicomCount?: number;
    dicomDone?: number;
    [k: string]: unknown;
};

type EzDoc = {
    _id: string;
    _session_id: string;
    original: unknown;
    updated?: unknown;
    [k: string]: unknown;
};

const backing: Record<string, Record<string, unknown>> = {};
let uuidCounter = 0;

jest.mock('uuid', () => ({
    v4: jest.fn(() => `uuid-${++uuidCounter}`),
}));

jest.mock('electron-store', () => {
    return jest.fn().mockImplementation((opts: { name: string }) => {
        if (!backing[opts.name]) backing[opts.name] = {};
        return {
            get: jest.fn((key: string, defaultValue?: unknown) => {
                const value = backing[opts.name][key];
                return value === undefined ? defaultValue : value;
            }),
            set: jest.fn((key: string, value: unknown) => {
                backing[opts.name][key] = value;
            }),
        };
    });
});

import { ezbidsStore, sessionStore } from './electron.store';

const SESSION_STORE_NAME = 'ezbids-sessions';
const EZBIDS_STORE_NAME = 'ezbids-data';
const SESSIONS_KEY = 'sessions';
const EZBIDS_KEY = 'ezbids';

describe('api/store/electron.store', () => {
    beforeEach(() => {
        backing[SESSION_STORE_NAME] = {};
        backing[EZBIDS_STORE_NAME] = {};
        uuidCounter = 0;
    });

    describe('sessionStore', () => {
        it('findById returns null when no session exists', async () => {
            await expect(sessionStore.findById('missing')).resolves.toBeNull();
        });

        it('findById returns a cloned session document', async () => {
            backing[SESSION_STORE_NAME][SESSIONS_KEY] = {
                a1: { _id: 'a1', status: 'created', ownerId: 1 } as SessionDoc,
            };
            const found = (await sessionStore.findById('a1')) as unknown as SessionDoc;
            expect(found).toEqual({ _id: 'a1', status: 'created', ownerId: 1 });
            found.status = 'changed';
            const raw = (backing[SESSION_STORE_NAME][SESSIONS_KEY] as Record<string, SessionDoc>).a1;
            expect(raw.status).toBe('created');
        });

        it('find filters by status.$in when provided', async () => {
            backing[SESSION_STORE_NAME][SESSIONS_KEY] = {
                s1: { _id: 's1', status: 'created' } as SessionDoc,
                s2: { _id: 's2', status: 'finalized' } as SessionDoc,
            };
            const list = (await sessionStore.find({ status: { $in: ['finalized'] } })) as unknown as SessionDoc[];
            expect(list).toHaveLength(1);
            expect(list[0]._id).toBe('s2');
        });

        it('find returns all sessions when no status filter', async () => {
            backing[SESSION_STORE_NAME][SESSIONS_KEY] = {
                s1: { _id: 's1', status: 'created' } as SessionDoc,
                s2: { _id: 's2', status: 'finalized' } as SessionDoc,
            };
            const list = (await sessionStore.find({})) as unknown as SessionDoc[];
            expect(list.map((s) => s._id).sort()).toEqual(['s1', 's2']);
        });

        it('findForUser returns owned or explicitly allowed sessions', async () => {
            backing[SESSION_STORE_NAME][SESSIONS_KEY] = {
                owned: { _id: 'owned', status: 'x', ownerId: 9, allowedUsers: [] } as SessionDoc,
                allowed: { _id: 'allowed', status: 'x', ownerId: 1, allowedUsers: [9] } as SessionDoc,
                denied: { _id: 'denied', status: 'x', ownerId: 1, allowedUsers: [2] } as SessionDoc,
            };
            const list = (await sessionStore.findForUser(9)) as unknown as SessionDoc[];
            expect(list.map((s) => s._id).sort()).toEqual(['allowed', 'owned']);
        });

        it('create sets defaults and persists session under generated id', async () => {
            const created = (await sessionStore.create({})) as unknown as SessionDoc;
            expect(created._id).toBe('uuid-1');
            expect(created.status).toBe('created');
            expect(created.allowedUsers).toEqual([]);
            const raw = backing[SESSION_STORE_NAME][SESSIONS_KEY] as Record<string, SessionDoc>;
            expect(raw['uuid-1']).toBeDefined();
        });

        it('create honors explicit data overrides', async () => {
            const created = (await sessionStore.create({
                status: 'uploading',
                ownerId: 77,
                allowedUsers: [7],
                status_msg: 'hello',
            } as never)) as unknown as SessionDoc;
            expect(created.status).toBe('uploading');
            expect(created.ownerId).toBe(77);
            expect(created.allowedUsers).toEqual([7]);
            expect(created.status_msg).toBe('hello');
        });

        it('save merges existing document and updates update_date', async () => {
            const oldDate = new Date('2024-01-01T00:00:00.000Z');
            backing[SESSION_STORE_NAME][SESSIONS_KEY] = {
                s1: { _id: 's1', status: 'created', update_date: oldDate, ownerId: 1 } as SessionDoc,
            };
            const saved = (await sessionStore.save({
                _id: 's1',
                status: 'done',
            } as never)) as unknown as SessionDoc;
            expect(saved.status).toBe('done');
            expect(saved.ownerId).toBe(1);
            expect(saved.update_date).toBeInstanceOf(Date);
            expect((saved.update_date as Date).getTime()).toBeGreaterThan(oldDate.getTime());
        });
    });

    describe('ezbidsStore', () => {
        it('findOneBySessionId returns null when missing', async () => {
            await expect(ezbidsStore.findOneBySessionId('none')).resolves.toBeNull();
        });

        it('findOneBySessionId returns matching record', async () => {
            backing[EZBIDS_STORE_NAME][EZBIDS_KEY] = {
                sid1: { _id: 'e1', _session_id: 'sid1', original: { a: 1 } } as EzDoc,
            };
            const found = (await ezbidsStore.findOneBySessionId('sid1')) as unknown as EzDoc;
            expect(found._id).toBe('e1');
        });

        it('findOneAndUpdate returns null when target not found', async () => {
            backing[EZBIDS_STORE_NAME][EZBIDS_KEY] = {};
            await expect(
                ezbidsStore.findOneAndUpdate('sidX', { $set: { updated: { z: 1 } } } as never)
            ).resolves.toBeNull();
        });

        it('findOneAndUpdate merges $set into existing doc and persists', async () => {
            backing[EZBIDS_STORE_NAME][EZBIDS_KEY] = {
                sid1: { _id: 'e1', _session_id: 'sid1', original: { a: 1 }, keep: 'x' } as EzDoc,
            };
            await ezbidsStore.findOneAndUpdate('sid1', { $set: { updated: { b: 2 } } } as never);
            const raw = (backing[EZBIDS_STORE_NAME][EZBIDS_KEY] as Record<string, EzDoc>).sid1;
            expect(raw.keep).toBe('x');
            expect(raw.updated).toEqual({ b: 2 });
        });

        it('create writes document keyed by generated _id and returns undefined', async () => {
            const ret = await ezbidsStore.create({ _session_id: 'sid2', original: { p: 1 } } as never);
            expect(ret).toBeUndefined();
            const all = backing[EZBIDS_STORE_NAME][EZBIDS_KEY] as Record<string, EzDoc>;
            expect(all['uuid-1']).toMatchObject({
                _id: 'uuid-1',
                _session_id: 'sid2',
                original: { p: 1 },
                updated: undefined,
            });
        });
    });
});
