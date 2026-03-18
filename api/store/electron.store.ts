/* eslint-disable camelcase */
'use strict';

import ElectronStore from 'electron-store';
import { v4 as uuidv4 } from 'uuid';
import { ISession } from '../models';
import type { IEzBIDSStore, IEzBIDSWithId, ISessionStore, ISessionWithId, SessionQuery } from './types';

const SESSION_STORE_NAME = 'ezbids-sessions';
const EZBIDS_STORE_NAME = 'ezbids-data';

const SESSIONS_KEY = 'sessions';
const EZBIDS_KEY = 'ezbids';

// electron-store extends Conf which has get/set, but its .d.ts doesn't re-declare them.
interface StoreLike {
    get(key: string, defaultValue?: unknown): unknown;
    set(key: string, value: unknown): void;
}

function getSessionStore(): StoreLike {
    return new ElectronStore<{ [_id: string]: ISessionWithId }>({
        name: SESSION_STORE_NAME,
        projectName: 'ezbids',
        cwd: process.env.USER_DATA_PATH,
    }) as unknown as StoreLike;
}

function getEzBIDSStore(): StoreLike {
    return new ElectronStore<{ [_id: string]: IEzBIDSWithId }>({
        name: EZBIDS_STORE_NAME,
        projectName: 'ezbids',
        cwd: process.env.USER_DATA_PATH,
    }) as unknown as StoreLike;
}

export const sessionStore: ISessionStore = {
    findById(id: string) {
        const store = getSessionStore();
        const sessions = store.get(SESSIONS_KEY, {}) as Record<string, ISessionWithId>;
        const session = sessions[id] ?? null;
        return Promise.resolve(session ? { ...session } : null);
    },
    find(query: SessionQuery) {
        console.log('find query', query);
        const store = getSessionStore();
        const sessions = store.get(SESSIONS_KEY, {}) as Record<string, ISessionWithId>;
        let list = Object.entries(sessions).map(([, s]) => ({ ...s }));
        if (query.status?.$in?.length) {
            list = list.filter((s) => query.status!.$in!.includes(s.status));
        }
        return Promise.resolve(list);
    },
    create(data: Partial<ISession>) {
        const store = getSessionStore();
        const now = new Date();
        const session: ISessionWithId = {
            _id: uuidv4(),
            create_date: now,
            update_date: now,
            ownerId: undefined,
            allowedUsers: [],
            request_headers: undefined,
            upload_finish_date: undefined,
            pre_begin_date: undefined,
            pre_finish_date: undefined,
            deface_begin_date: undefined,
            deface_finish_date: undefined,
            finalize_begin_date: undefined,
            finalize_finish_date: undefined,
            status: data.status ?? 'created',
            dicomCount: data.dicomCount ?? undefined,
            dicomDone: data.dicomDone ?? undefined,
            status_msg: data.status_msg ?? undefined,
            ...data,
        };
        const sessions = store.get(SESSIONS_KEY, {});
        sessions[session._id] = session;
        store.set(SESSIONS_KEY, sessions);
        return Promise.resolve(session);
    },
    save(session: ISessionWithId) {
        const store = getSessionStore();
        const sessions = store.get(SESSIONS_KEY, {}) as Record<string, ISessionWithId>;
        sessions[session._id] = { ...sessions[session._id], ...session, update_date: new Date() };
        store.set(SESSIONS_KEY, sessions);
        return Promise.resolve(sessions[session._id]);
    },
};

export const ezbidsStore: IEzBIDSStore = {
    findOneBySessionId(sessionId: string) {
        const store = getEzBIDSStore();
        const all = store.get(EZBIDS_KEY, {});
        const doc = all[sessionId] ?? null;
        return Promise.resolve(doc);
    },
    findOneAndUpdate(sessionId: string, update) {
        const store = getEzBIDSStore();
        const all = store.get(EZBIDS_KEY, {});
        const found = all[sessionId];

        if (!found) return Promise.resolve(null);

        all[sessionId] = {
            ...found,
            ...update.$set,
        };
        store.set(EZBIDS_KEY, all);
        return Promise.resolve(undefined);
    },
    create(data) {
        const store = getEzBIDSStore();
        const all = store.get(EZBIDS_KEY, {});
        const now = new Date();
        const newObj: IEzBIDSWithId = {
            _id: uuidv4(),
            _session_id: data._session_id,
            original: data.original,
            updated: undefined,
            create_date: now,
            update_date: now,
        };
        all[newObj._id] = newObj;
        store.set(EZBIDS_KEY, all);
        return Promise.resolve(undefined);
    },
};
