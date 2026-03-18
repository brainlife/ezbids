'use strict';

import { HydratedDocument, Types } from 'mongoose';
import { ezBIDS, ISession, Session } from '../models';
import type { IEzBIDSReturn, IEzBIDSStore, ISessionStore } from './types';

export const sessionStore: ISessionStore = {
    findById(id) {
        return Session.findById(id)
            .exec()
            .then((session) => session);
    },
    find(query) {
        return Session.find(query).exec();
    },
    create(data) {
        const session = new Session(data);
        return session.save().then((_session) => _session);
    },
    save(session: HydratedDocument<ISession>) {
        return session.save().then((_session) => _session);
    },
};

export const ezbidsStore: IEzBIDSStore = {
    findOneBySessionId(sessionId: Types.ObjectId) {
        return ezBIDS.findOne({ _session_id: sessionId }).exec() as Promise<IEzBIDSReturn | null>;
    },
    findOneAndUpdate(sessionId: Types.ObjectId, update) {
        return ezBIDS
            .findOneAndUpdate({ _session_id: sessionId }, update)
            .exec()
            .then(() => undefined);
    },
    create(data) {
        const doc = new ezBIDS(data);
        return doc.save().then(() => undefined);
    },
};
